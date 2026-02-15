"""Configuration management for Sandstorm."""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import yaml


@dataclass
class LimitsConfig:
    """Resource limits configuration for Docker sandboxes."""

    max_concurrent_agents: int = 5
    cpu_limit: str = "2"
    memory_limit: str = "4gb"
    session_timeout_seconds: int = 600
    docker_image: str = "sandstorm-agent:latest"
    network_mode: str = "bridge"
    auto_cleanup: bool = True

    @classmethod
    def load(cls, path: Optional[Path] = None) -> 'LimitsConfig':
        """
        Load configuration from YAML file.

        Args:
            path: Path to limits.yaml file. If None, uses default location.

        Returns:
            LimitsConfig instance with loaded values or defaults.
        """
        if path is None:
            # Try to find config/limits.yaml relative to this file's location
            config_dir = Path(__file__).parent.parent.parent / "config"
            path = config_dir / "limits.yaml"

        if not path.exists():
            return cls()  # Use defaults

        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}

            # Filter to only known fields
            filtered_data = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
            return cls(**filtered_data)
        except Exception as e:
            # Log warning but return defaults
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to load config from {path}: {e}. Using defaults.")
            return cls()
