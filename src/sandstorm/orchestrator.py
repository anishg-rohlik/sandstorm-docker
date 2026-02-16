"""Main sandbox orchestration - provider-agnostic (Docker or E2B)."""
import asyncio
import json
import logging
import os
import posixpath
from collections.abc import AsyncGenerator
from importlib.resources import files
from pathlib import Path

from .models import QueryRequest
from .sandbox import DockerSandbox, E2BSandbox
from .config import LimitsConfig

logger = logging.getLogger(__name__)

# Load the runner script that executes inside the sandbox
_RUNNER_SCRIPT = files("sandstorm").joinpath("runner.mjs").read_text()


def _get_config_path() -> Path:
    """Resolve sandstorm.json from the current working directory."""
    return Path.cwd() / "sandstorm.json"


# Path inside the sandbox where GCP credentials are uploaded
_GCP_CREDENTIALS_SANDBOX_PATH = "/home/user/.config/gcloud/service_account.json"

# Provider env vars auto-forwarded from .env into the sandbox
_PROVIDER_ENV_KEYS = [
    # Google Vertex AI
    "CLAUDE_CODE_USE_VERTEX",
    "CLOUD_ML_REGION",
    "ANTHROPIC_VERTEX_PROJECT_ID",
    # Amazon Bedrock
    "CLAUDE_CODE_USE_BEDROCK",
    "AWS_REGION",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    # Microsoft Azure / Foundry
    "CLAUDE_CODE_USE_FOUNDRY",
    "AZURE_FOUNDRY_RESOURCE",
    "AZURE_API_KEY",
    # Custom base URL (proxy, self-hosted, OpenRouter)
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    # Model name overrides (remap SDK aliases to provider model IDs)
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
]


def _validate_sandstorm_config(raw: dict) -> dict:
    """Validate known sandstorm.json fields, drop invalid ones with warnings."""
    # Expected field types: field_name -> (allowed types tuple, human description)
    known_fields: dict[str, tuple[tuple[type, ...], str]] = {
        "system_prompt": ((str,), "str"),
        "model": ((str,), "str"),
        "max_turns": ((int,), "int"),
        "output_format": ((dict,), "dict"),
        "agents": ((dict, list), "dict or list"),
        "mcp_servers": ((dict,), "dict"),
    }

    validated: dict = {}
    for key, value in raw.items():
        if key in known_fields:
            allowed_types, type_desc = known_fields[key]
            # Reject booleans masquerading as int (isinstance(True, int) is True)
            if isinstance(value, bool) and bool not in allowed_types:
                logger.warning(
                    "sandstorm.json: field %r should be %s, got bool — skipping",
                    key,
                    type_desc,
                )
                continue
            if not isinstance(value, allowed_types):
                logger.warning(
                    "sandstorm.json: field %r should be %s, got %s — skipping",
                    key,
                    type_desc,
                    type(value).__name__,
                )
                continue
            validated[key] = value
        else:
            logger.warning("sandstorm.json: unknown field %r — ignoring", key)

    return validated


def _load_sandstorm_config() -> dict | None:
    """Load sandstorm.json from the project root if it exists."""
    config_path = _get_config_path()
    if not config_path.exists():
        return None

    try:
        raw = json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        logger.error("sandstorm.json: invalid JSON — %s", exc)
        return None

    if not isinstance(raw, dict):
        logger.error(
            "sandstorm.json: expected a JSON object, got %s", type(raw).__name__
        )
        return None

    return _validate_sandstorm_config(raw)


async def run_agent_in_sandbox(
    request: QueryRequest, request_id: str = ""
) -> AsyncGenerator[str, None]:
    """
    Run Claude agent in sandbox (Docker or E2B).

    Yields JSON event lines from agent execution.
    """

    # Determine sandbox backend from environment variable
    backend = os.getenv("SANDBOX_BACKEND", "docker").lower()

    # Build sandbox env vars: API key + any provider env vars from .env
    sandbox_envs = {}
    if request.anthropic_api_key:
        sandbox_envs["ANTHROPIC_API_KEY"] = request.anthropic_api_key
    for key in _PROVIDER_ENV_KEYS:
        val = os.environ.get(key)
        if val:
            sandbox_envs[key] = val

    # Per-request OpenRouter key overrides env var
    if request.openrouter_api_key:
        sandbox_envs["ANTHROPIC_AUTH_TOKEN"] = request.openrouter_api_key

    # When using a custom base URL with auth token (e.g. OpenRouter, LiteLLM),
    # use the auth token as the API key for the SDK to work properly.
    # LiteLLM proxies typically accept the key in either Authorization or x-api-key header.
    if sandbox_envs.get("ANTHROPIC_BASE_URL") and sandbox_envs.get(
        "ANTHROPIC_AUTH_TOKEN"
    ):
        sandbox_envs["ANTHROPIC_API_KEY"] = sandbox_envs["ANTHROPIC_AUTH_TOKEN"]

    # Eagerly read GCP credentials file (TOCTOU fix: read now, upload later)
    gcp_creds_content = None
    if os.environ.get("CLAUDE_CODE_USE_VERTEX"):
        gcp_creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not gcp_creds_path:
            raise RuntimeError(
                "GOOGLE_APPLICATION_CREDENTIALS is required when using Vertex AI — "
                "set it in .env to the path of your GCP service account JSON key"
            )
        creds_file = Path(gcp_creds_path)
        if not creds_file.is_absolute():
            creds_file = Path.cwd() / creds_file
        try:
            gcp_creds_content = creds_file.read_text()
        except FileNotFoundError:
            raise RuntimeError(
                f"GOOGLE_APPLICATION_CREDENTIALS file not found: {gcp_creds_path}"
            )
        sandbox_envs["GOOGLE_APPLICATION_CREDENTIALS"] = _GCP_CREDENTIALS_SANDBOX_PATH

    # Load sandstorm.json configuration
    sandstorm_config = _load_sandstorm_config() or {}

    # Instantiate appropriate sandbox backend
    if backend == "e2b":
        logger.info("[%s] Creating E2B sandbox", request_id)
        sandbox = E2BSandbox(api_key=request.e2b_api_key)
    else:
        logger.info("[%s] Creating Docker sandbox", request_id)
        config = LimitsConfig.load()
        sandbox = DockerSandbox(image=config.docker_image)

    try:
        # Create sandbox with environment variables
        await sandbox.create(
            timeout=request.timeout,
            env_vars=sandbox_envs
        )

        # Write Claude Agent SDK settings to the sandbox
        settings = {
            "permissions": {"allow": [], "deny": []},
            "env": {"CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1"},
            "debug": {"enabled": False},  # Disable debug logging to avoid permission issues
        }
        await sandbox.mkdir("/home/user/.claude")
        await sandbox.upload_file(
            local_path=None,
            remote_path="/home/user/.claude/settings.json",
            content=json.dumps(settings, indent=2)
        )

        # Upload GCP credentials to the sandbox if Vertex AI is configured
        if gcp_creds_content:
            logger.info("[%s] Uploading GCP credentials to sandbox", request_id)
            await sandbox.mkdir(posixpath.dirname(_GCP_CREDENTIALS_SANDBOX_PATH))
            await sandbox.upload_file(
                local_path=None,
                remote_path=_GCP_CREDENTIALS_SANDBOX_PATH,
                content=gcp_creds_content
            )

        # Upload user files to the sandbox
        if request.files:
            logger.info("[%s] Uploading %d files", request_id, len(request.files))
            # Create parent directories for all files
            dirs_to_create: set[str] = set()
            for path in request.files:
                parent = posixpath.dirname(path)
                if parent:  # non-empty means nested path like "src/main.py"
                    dirs_to_create.add(f"/home/user/{parent}")

            for dir_path in sorted(dirs_to_create):
                await sandbox.mkdir(dir_path)

            # Upload all files
            for path, content in request.files.items():
                sandbox_path = f"/home/user/{path}"
                try:
                    await sandbox.upload_file(
                        local_path=None,
                        remote_path=sandbox_path,
                        content=content
                    )
                except Exception as exc:
                    raise RuntimeError(
                        f"Failed to upload file {path!r} to sandbox: {exc}"
                    ) from exc

        # Upload runner script
        await sandbox.upload_file(
            local_path=None,
            remote_path="/opt/agent-runner/runner.mjs",
            content=_RUNNER_SCRIPT
        )

        # Build agent config: sandstorm.json (base) + request overrides
        agent_config = {
            "prompt": request.prompt,
            "cwd": "/home/user",
            # Request overrides sandstorm.json
            "model": request.model or sandstorm_config.get("model"),
            "max_turns": request.max_turns or sandstorm_config.get("max_turns"),
            # These come from sandstorm.json only
            "system_prompt": sandstorm_config.get("system_prompt"),
            "output_format": sandstorm_config.get("output_format"),
            "agents": sandstorm_config.get("agents"),
            "mcp_servers": sandstorm_config.get("mcp_servers"),
        }
        await sandbox.upload_file(
            local_path=None,
            remote_path="/opt/agent-runner/agent_config.json",
            content=json.dumps(agent_config)
        )

        # Run the SDK query() via the runner script
        logger.info(
            "[%s] Starting agent (backend=%s, model=%s, max_turns=%s)",
            request_id,
            backend,
            agent_config.get("model"),
            agent_config.get("max_turns"),
        )

        # Execute runner and stream output
        command = "node --no-warnings /opt/agent-runner/runner.mjs"
        async for output_line in sandbox.run_command(command, cwd="/home/user"):
            line = output_line.strip()
            if line:
                yield line

        logger.info("[%s] Agent completed successfully", request_id)

    except asyncio.CancelledError:
        logger.warning("[%s] Request cancelled", request_id)
        raise
    except Exception as e:
        logger.error("[%s] Sandbox error: %s", request_id, e)
        yield json.dumps({
            "type": "error",
            "error": str(e),
            "request_id": request_id
        })
    finally:
        # Always cleanup sandbox
        await sandbox.close()
