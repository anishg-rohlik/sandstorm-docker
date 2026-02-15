"""Docker-based sandbox implementation."""
import asyncio
import logging
import tarfile
import io
from pathlib import Path, PurePosixPath
from typing import AsyncGenerator, Dict, Optional
import docker
from docker.models.containers import Container
from docker.errors import DockerException, NotFound

from .base import SandboxBase
from ..config import LimitsConfig

logger = logging.getLogger(__name__)


class DockerSandbox(SandboxBase):
    """Docker-based sandbox implementation."""

    # Class-level tracking for max_concurrent_agents
    _active_sandboxes: int = 0
    _lock = asyncio.Lock()

    def __init__(self, image: str = "sandstorm-agent:latest"):
        self.image = image
        self.container: Optional[Container] = None
        self._client: Optional[docker.DockerClient] = None
        self._timeout: int = 300
        self._cleanup_task: Optional[asyncio.Task] = None

    async def create(
        self,
        timeout: int = 300,
        env_vars: Optional[Dict[str, str]] = None,
        cpu_limit: str = "2",
        memory_limit: str = "2048m"
    ) -> None:
        """Create and start Docker container with resource limits."""

        # Load limits from config
        limits_config = LimitsConfig.load()

        # Check max concurrent agents
        async with DockerSandbox._lock:
            if DockerSandbox._active_sandboxes >= limits_config.max_concurrent_agents:
                raise RuntimeError(
                    f"Max concurrent agents ({limits_config.max_concurrent_agents}) reached. "
                    "Please wait for existing agents to complete."
                )
            DockerSandbox._active_sandboxes += 1

        try:
            # Initialize Docker client (blocking, so run in executor)
            loop = asyncio.get_event_loop()
            self._client = await loop.run_in_executor(
                None,
                lambda: docker.from_env()
            )

            # Verify image exists
            try:
                await loop.run_in_executor(None, self._client.images.get, self.image)
            except NotFound:
                logger.error(f"Image {self.image} not found. Build it with: docker build -f Dockerfile.agent -t {self.image} .")
                raise RuntimeError(f"Docker image {self.image} not found")

            # Apply resource limits from config (override if specified)
            cpu_limit = limits_config.cpu_limit or cpu_limit
            memory_limit = limits_config.memory_limit or memory_limit
            self._timeout = limits_config.session_timeout_seconds or timeout

            # Create container with resource constraints
            self.container = await loop.run_in_executor(
                None,
                lambda: self._client.containers.create(
                    image=self.image,
                    command="/bin/sleep infinity",  # Keep alive until we run commands
                    detach=True,
                    environment=env_vars or {},
                    working_dir="/home/user",
                    network_mode="bridge",
                    # Resource limits
                    cpu_count=int(float(cpu_limit)),  # Convert "2" -> 2
                    mem_limit=memory_limit,
                    # Security
                    read_only=False,  # Need write for /home/user
                    cap_drop=["ALL"],
                    cap_add=["CHOWN", "DAC_OVERRIDE", "FOWNER", "SETGID", "SETUID"],
                    security_opt=["no-new-privileges"],
                    # Cleanup
                    remove=True,  # Auto-remove on stop
                    labels={"sandstorm.managed": "true"}
                )
            )

            # Start container
            await loop.run_in_executor(None, self.container.start)
            logger.info(f"Container {self.container.id[:12]} started with {cpu_limit} CPUs, {memory_limit} memory")

            # Schedule auto-cleanup after timeout
            self._cleanup_task = asyncio.create_task(self._auto_cleanup())

        except Exception as e:
            # Release slot if creation failed
            async with DockerSandbox._lock:
                DockerSandbox._active_sandboxes -= 1
            raise RuntimeError(f"Failed to create Docker sandbox: {e}") from e

    async def _auto_cleanup(self) -> None:
        """Background task to enforce session timeout."""
        try:
            await asyncio.sleep(self._timeout)
            if self.is_alive:
                logger.warning(f"Container {self.container.id[:12]} exceeded {self._timeout}s timeout, forcing cleanup")
                await self.close()
        except asyncio.CancelledError:
            # Task was cancelled (normal shutdown)
            pass

    async def mkdir(self, remote_path: str) -> None:
        """Create directory in container."""
        if not self.container:
            raise RuntimeError("Container not created")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self.container.exec_run(
                f"mkdir -p {remote_path}",
                user="root"  # Ensure permissions
            )
        )

        exit_code, _ = result
        if exit_code != 0:
            raise RuntimeError(f"Failed to create directory {remote_path}")

    async def upload_file(
        self,
        local_path: Optional[Path],
        remote_path: str,
        content: Optional[str] = None
    ) -> None:
        """Upload file using tar stream (most efficient method)."""
        if not self.container:
            raise RuntimeError("Container not created")

        # Determine content source
        if content is not None:
            file_content = content.encode('utf-8')
        elif local_path:
            file_content = local_path.read_bytes()
        else:
            raise ValueError("Must provide either local_path or content")

        # Create tar archive in memory
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            tarinfo = tarfile.TarInfo(name=PurePosixPath(remote_path).name)
            tarinfo.size = len(file_content)
            tarinfo.mode = 0o644
            tar.addfile(tarinfo, io.BytesIO(file_content))

        tar_stream.seek(0)

        # Upload tar to container
        remote_dir = str(PurePosixPath(remote_path).parent)
        loop = asyncio.get_event_loop()

        await loop.run_in_executor(
            None,
            lambda: self.container.put_archive(remote_dir, tar_stream.read())
        )

        logger.debug(f"Uploaded file to {remote_path} ({len(file_content)} bytes)")

    async def run_command(
        self,
        command: str,
        cwd: str = "/home/user",
        timeout: int = 1800
    ) -> AsyncGenerator[str, None]:
        """Execute command and stream output line by line."""
        if not self.container:
            raise RuntimeError("Container not created")

        loop = asyncio.get_event_loop()

        # Execute command with streaming
        exec_instance = await loop.run_in_executor(
            None,
            lambda: self.container.exec_run(
                f"cd {cwd} && {command}",
                stream=True,
                demux=True,  # Separate stdout/stderr
                user="user"
            )
        )

        # Stream output
        for stdout_chunk, stderr_chunk in exec_instance.output:
            if stdout_chunk:
                yield stdout_chunk.decode('utf-8', errors='replace')
            if stderr_chunk:
                # Log stderr but don't yield (matches E2B behavior)
                logger.debug(f"stderr: {stderr_chunk.decode('utf-8', errors='replace')}")

    async def close(self) -> None:
        """Stop and remove container."""
        # Cancel cleanup task if running
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        if self.container:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self.container.stop(timeout=5)
                )
                logger.info(f"Container {self.container.id[:12]} stopped")
            except Exception as e:
                logger.warning(f"Error stopping container: {e}")
            finally:
                self.container = None

                # Release slot
                async with DockerSandbox._lock:
                    DockerSandbox._active_sandboxes = max(0, DockerSandbox._active_sandboxes - 1)

        if self._client:
            self._client.close()
            self._client = None

    @property
    def is_alive(self) -> bool:
        """Check if container is still running."""
        if not self.container:
            return False

        try:
            self.container.reload()
            return self.container.status == "running"
        except Exception:
            return False
