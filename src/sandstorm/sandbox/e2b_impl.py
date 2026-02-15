"""E2B cloud sandbox implementation (legacy/optional)."""
import logging
import posixpath
import shlex
from pathlib import Path
from typing import AsyncGenerator, Dict, Optional

from e2b import AsyncSandbox, NotFoundException

from .base import SandboxBase

logger = logging.getLogger(__name__)

# Custom template with Agent SDK pre-installed (built via build_template.py).
# Falls back to E2B's "claude-code" template + runtime install if custom not found.
TEMPLATE = "work-43ca/sandstorm"
FALLBACK_TEMPLATE = "claude-code"


class E2BSandbox(SandboxBase):
    """E2B cloud sandbox implementation (legacy/optional)."""

    def __init__(
        self,
        template: str = TEMPLATE,
        fallback_template: str = FALLBACK_TEMPLATE,
        api_key: Optional[str] = None
    ):
        self.template = template
        self.fallback_template = fallback_template
        self.api_key = api_key
        self._sandbox: Optional[AsyncSandbox] = None
        self._using_fallback = False

    async def create(
        self,
        timeout: int = 300,
        env_vars: Optional[Dict[str, str]] = None,
        cpu_limit: str = "2",
        memory_limit: str = "2048m"
    ) -> None:
        """Create E2B sandbox (cpu_limit and memory_limit ignored for E2B)."""
        try:
            self._sandbox = await AsyncSandbox.create(
                template=self.template,
                api_key=self.api_key,
                timeout=timeout,
                envs=env_vars or {}
            )
            logger.info(f"E2B sandbox created with template {self.template}: {self._sandbox.sandbox_id}")
        except NotFoundException:
            # Custom template not found — fall back to default template + runtime SDK install
            logger.warning(
                f"Template {self.template!r} not found, falling back to {self.fallback_template!r} "
                "(adds ~15s overhead for npm install)"
            )
            self._sandbox = await AsyncSandbox.create(
                template=self.fallback_template,
                api_key=self.api_key,
                timeout=timeout,
                envs=env_vars or {}
            )
            self._using_fallback = True

            # Install Claude Agent SDK runtime (matches build_template.py version)
            await self._sandbox.commands.run(
                "mkdir -p /opt/agent-runner"
                " && cd /opt/agent-runner"
                " && npm init -y"
                # Pin SDK version to match Docker image
                " && npm install @anthropic-ai/claude-agent-sdk@0.2.42",
                timeout=120
            )
            logger.info(f"E2B sandbox created with fallback template: {self._sandbox.sandbox_id}")

    async def mkdir(self, remote_path: str) -> None:
        """Create directory in E2B sandbox."""
        if not self._sandbox:
            raise RuntimeError("Sandbox not created")

        await self._sandbox.commands.run(
            f"mkdir -p {shlex.quote(remote_path)}",
            timeout=5
        )

    async def upload_file(
        self,
        local_path: Optional[Path],
        remote_path: str,
        content: Optional[str] = None
    ) -> None:
        """Upload file to E2B sandbox."""
        if not self._sandbox:
            raise RuntimeError("Sandbox not created")

        # Determine content source
        if content is not None:
            file_content = content
        elif local_path:
            file_content = local_path.read_text()
        else:
            raise ValueError("Must provide either local_path or content")

        # Ensure parent directory exists
        parent_dir = posixpath.dirname(remote_path)
        if parent_dir and parent_dir != "/":
            await self.mkdir(parent_dir)

        # Upload file
        await self._sandbox.files.write(remote_path, file_content)
        logger.debug(f"Uploaded file to {remote_path} ({len(file_content)} bytes)")

    async def run_command(
        self,
        command: str,
        cwd: str = "/home/user",
        timeout: int = 1800
    ) -> AsyncGenerator[str, None]:
        """Execute command in E2B sandbox and stream output."""
        if not self._sandbox:
            raise RuntimeError("Sandbox not created")

        # E2B's commands.run() is blocking, so we need to use callbacks with a queue
        import asyncio
        queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=10_000)

        def _enqueue(data: str) -> None:
            """Put data on the queue (sync callback)."""
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                logger.warning("Queue full, dropping message")

        # Run command in background task
        async def _run():
            try:
                # Change to working directory if specified
                if cwd != "/home/user":
                    full_command = f"cd {shlex.quote(cwd)} && {command}"
                else:
                    full_command = command

                await self._sandbox.commands.run(
                    full_command,
                    timeout=timeout,
                    on_stdout=lambda data: _enqueue(data if isinstance(data, str) else str(data)),
                    on_stderr=lambda data: None,  # Ignore stderr for now
                )
            finally:
                await queue.put(None)  # Signal completion

        task = asyncio.create_task(_run())

        # Yield messages from queue
        try:
            while True:
                line = await queue.get()
                if line is None:
                    break
                if line.strip():
                    yield line.strip()
        finally:
            # Ensure task is cancelled if consumer stops early
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

    async def close(self) -> None:
        """Destroy E2B sandbox."""
        if self._sandbox:
            logger.info(f"Destroying E2B sandbox {self._sandbox.sandbox_id}")
            await self._sandbox.kill()
            self._sandbox = None

    @property
    def is_alive(self) -> bool:
        """Check if E2B sandbox is still alive."""
        return self._sandbox is not None
