"""Abstract base class for sandbox implementations."""
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Optional
from pathlib import Path


class SandboxBase(ABC):
    """Abstract base class for sandbox implementations (E2B, Docker, etc.)"""

    @abstractmethod
    async def create(
        self,
        timeout: int = 300,
        env_vars: Optional[Dict[str, str]] = None,
        cpu_limit: str = "2",
        memory_limit: str = "2048m"
    ) -> None:
        """
        Initialize and start the sandbox environment.

        Args:
            timeout: Maximum sandbox lifetime in seconds
            env_vars: Environment variables to set in sandbox
            cpu_limit: CPU cores allocation (e.g., "2" or "1.5")
            memory_limit: Memory limit (e.g., "2048m" or "4g")
        """
        pass

    @abstractmethod
    async def upload_file(
        self,
        local_path: Optional[Path],
        remote_path: str,
        content: Optional[str] = None
    ) -> None:
        """
        Upload a file to the sandbox.

        Args:
            local_path: Local file path to read from (if content not provided)
            remote_path: Destination path in sandbox (POSIX format)
            content: Direct string content (alternative to local_path)
        """
        pass

    @abstractmethod
    async def mkdir(self, remote_path: str) -> None:
        """Create directory in sandbox (creates parents if needed)."""
        pass

    @abstractmethod
    async def run_command(
        self,
        command: str,
        cwd: str = "/home/user",
        timeout: int = 1800
    ) -> AsyncGenerator[str, None]:
        """
        Execute command in sandbox and stream output.

        Args:
            command: Shell command to execute
            cwd: Working directory for command execution
            timeout: Command execution timeout in seconds

        Yields:
            stdout/stderr output lines as they arrive
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Cleanup and destroy the sandbox."""
        pass

    @property
    @abstractmethod
    def is_alive(self) -> bool:
        """Check if sandbox is still running."""
        pass
