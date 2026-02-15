# Sandstorm-Docker

Run AI agents in secure local Docker sandboxes. One command. Zero cloud dependencies.

[![Claude Agent SDK](https://img.shields.io/badge/Claude_Agent_SDK-black?logo=anthropic)](https://docs.anthropic.com/en/docs/agents-and-tools/claude-agent-sdk)
[![Docker](https://img.shields.io/badge/Docker-sandboxed-2496ED.svg?logo=docker)](https://www.docker.com)
[![OpenRouter](https://img.shields.io/badge/OpenRouter-300%2B_models-6366f1.svg)](https://openrouter.ai)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Hundreds of AI agents running in parallel. Hours-long tasks. Tool use, file access, structured output — each in its own secure Docker container. Fully local. No cloud dependencies.**

```bash
ds "Fetch all our webpages from git, analyze each for SEO, optimize them, and push the changes back"
```

That's it. Sandstorm-Docker wraps the [Claude Agent SDK](https://docs.anthropic.com/en/docs/agents-and-tools/claude-agent-sdk) in isolated Docker containers — the agent installs packages, fetches live data, generates files, and streams every step back via SSE. When it's done, the container is destroyed. Nothing persists. Nothing escapes.

**This is a public fork of [sandstorm](https://github.com/tomascupr/sandstorm) that replaces E2B cloud dependency with local Docker sandboxes.**

### Why Sandstorm-Docker?

Most companies want to use AI agents but hit the same wall: cloud dependencies, costs, and complexity. Sandstorm-Docker removes all three. It's a fork of the agent runtime from [duvo.ai](https://duvo.ai) — adapted for fully local deployment.

- **Fully Local** -- no cloud sandbox service required, runs entirely on your machine or server
- **Free** -- no per-agent costs (E2B charges $0.05-0.20 per agent), just your Anthropic API usage
- **Fast** -- 1-2s cold start vs 5-8s with E2B cloud sandboxes
- **Resource Limits** -- configure max concurrent agents, CPU, memory, and session timeouts
- **Any model via OpenRouter** -- swap in DeepSeek R1, Qwen 3, Kimi K2, or any of 300+ models
- **Full agent power** -- Bash, Read, Write, Edit, Glob, Grep, WebSearch, WebFetch -- all enabled
- **Safe by design** -- every request gets a fresh container with security hardening
- **Real-time streaming** -- watch the agent work step-by-step via SSE
- **Configure once, query forever** -- drop a `sandstorm.json` for structured output, subagents, MCP servers
- **File uploads** -- send code, data, or configs for the agent to work with
- **E2B Compatible** -- optional fallback to E2B cloud sandboxes if needed

### Get Started

```bash
# Install
pip install duvo-sandstorm

# Build agent Docker image (one-time)
docker build -f Dockerfile.agent -t sandstorm-agent:latest .

# Set API key (no E2B needed!)
export ANTHROPIC_API_KEY=sk-ant-...

# Run your first agent
ds "Find the top 10 trending Python repos on GitHub and summarize each"
```

If Sandstorm-Docker is useful, consider giving it a [star](https://github.com/anishg-rohlik/sandstorm-docker) — it helps others find it.

## Table of Contents

- [Quickstart](#quickstart)
- [CLI](#cli)
- [How It Works](#how-it-works)
- [Features](#features)
- [Resource Limits](#resource-limits)
- [OpenRouter](#openrouter)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Client Examples](#client-examples)
- [Deployment](#deployment)
- [Docker vs E2B](#docker-vs-e2b)
- [Security](#security)
- [Troubleshooting](#troubleshooting)

## Quickstart

### Prerequisites

- Python 3.11+
- Docker installed and running
- [Anthropic](https://console.anthropic.com) API key or [OpenRouter](https://openrouter.ai) API key
- [uv](https://docs.astral.sh/uv/) (only for source installs)

### Install

```bash
# From PyPI
pip install duvo-sandstorm

# Or from source
git clone https://github.com/anishg-rohlik/sandstorm-docker.git
cd sandstorm-docker
uv sync
```

### Build Agent Image

The agent runtime environment needs to be built once:

```bash
docker build -f Dockerfile.agent -t sandstorm-agent:latest .
```

This creates a Docker image with:
- Node.js 24
- Claude Agent SDK v0.2.42
- System tools (curl, git, ripgrep, python3)

### Setup

```bash
# Set your API key
export ANTHROPIC_API_KEY=sk-ant-...

# Run your first agent
ds "Create hello.py that prints a colorful greeting and run it"

# Or start the server for API access
ds serve
```

## CLI

Sandstorm provides two main commands:

### `ds query` - Run a one-off agent

```bash
# Basic usage
ds "your prompt here"

# With options
ds "analyze this code" \
  --model opus \
  --max-turns 50 \
  --timeout 600 \
  -f src/main.py \
  -f tests/test_main.py

# Upload files
ds "fix the bug" -f broken_file.py

# Different model
ds "explain this" --model haiku -f code.py
```

**Options:**
- `--model` - Model to use (sonnet, opus, haiku)
- `--max-turns` - Maximum agent turns (default: unlimited)
- `--timeout` - Timeout in seconds (5-3600, default: 300)
- `-f, --file` - Upload file(s) to sandbox (repeatable)
- `--anthropic-key` - Override ANTHROPIC_API_KEY
- `--openrouter-key` - Override OPENROUTER_API_KEY
- `--raw` - Output raw JSON instead of formatted messages

### `ds serve` - Start API server

```bash
# Start server
ds serve

# Custom host/port
ds serve --host 0.0.0.0 --port 8080

# Development mode (auto-reload)
ds serve --reload
```

## How It Works

```
Client Request
    ↓
Sandstorm API/CLI
    ↓
Docker Container Created
    ├─ Node.js 24 + Claude Agent SDK
    ├─ Python 3 + system tools
    ├─ User files uploaded
    └─ Environment variables set
    ↓
Agent Executes (runner.mjs)
    ├─ Runs commands
    ├─ Reads/writes files
    ├─ Makes web requests
    └─ Streams output as JSON
    ↓
Container Destroyed
    ↓
Results Returned
```

**Security:** Each container runs with:
- Minimal capabilities (CAP_DROP ALL)
- No new privileges allowed
- Resource limits (CPU, memory)
- Auto-cleanup after session timeout
- Network isolation

## Features

### Real-time Streaming

Watch the agent work step-by-step:

```bash
ds "Build a web scraper and test it on example.com"

# Output streams live:
# {"type":"tool_use","name":"write","path":"scraper.py"...}
# {"type":"bash","command":"python scraper.py"...}
# {"type":"result","success":true...}
```

### File Upload

```bash
# Upload single file
ds "fix the bug" -f broken.py

# Upload multiple files
ds "refactor these" -f src/a.py -f src/b.py -f tests/test.py

# Files land in /home/user/ in the container
```

### Structured Output

Configure output format in `sandstorm.json`:

```json
{
  "system_prompt": "Be concise",
  "model": "sonnet",
  "output_format": {
    "type": "json_schema",
    "schema": {
      "type": "object",
      "properties": {
        "summary": {"type": "string"},
        "files_created": {"type": "array", "items": {"type": "string"}},
        "success": {"type": "boolean"}
      },
      "required": ["summary", "files_created", "success"]
    }
  }
}
```

### Subagents

Define specialized agents in `sandstorm.json`:

```json
{
  "agents": {
    "python-expert": {
      "system_prompt": "You are a Python expert. Write clean, idiomatic code with type hints.",
      "model": "opus"
    },
    "tester": {
      "system_prompt": "You write comprehensive pytest tests.",
      "model": "sonnet"
    }
  }
}
```

### MCP Servers

Integrate Model Context Protocol servers:

```json
{
  "mcp_servers": {
    "filesystem": {
      "type": "stdio",
      "command": "mcp-server-filesystem",
      "args": ["/path/to/workspace"]
    },
    "github": {
      "type": "sse",
      "url": "http://localhost:3000/mcp"
    }
  }
}
```

## Resource Limits

Configure limits in `config/limits.yaml`:

```yaml
# Maximum concurrent agent containers
max_concurrent_agents: 5

# CPU cores per container
cpu_limit: "2"

# Memory limit per container
memory_limit: "4gb"

# Maximum container lifetime (seconds)
session_timeout_seconds: 600

# Docker image to use
docker_image: "sandstorm-agent:latest"
```

When the concurrent limit is reached, new requests will error until existing agents complete.

## OpenRouter

Use 300+ models from DeepSeek, Qwen, Kimi, and more:

```bash
export ANTHROPIC_BASE_URL=https://openrouter.ai/api/v1
export OPENROUTER_API_KEY=sk-or-...
export ANTHROPIC_DEFAULT_SONNET_MODEL=anthropic/claude-sonnet-4

ds "your query"
```

## Configuration

### sandstorm.json

Drop a `sandstorm.json` in your project root:

```json
{
  "system_prompt": "Be concise and prefer Python 3.11+",
  "model": "sonnet",
  "max_turns": 30,
  "output_format": {
    "type": "json_schema",
    "schema": {...}
  },
  "agents": {...},
  "mcp_servers": {...}
}
```

### Environment Variables

**Required:**
- `ANTHROPIC_API_KEY` - Your Anthropic API key

**Optional:**
- `ANTHROPIC_BASE_URL` - Custom API endpoint (e.g., OpenRouter)
- `OPENROUTER_API_KEY` - OpenRouter API key
- `SANDBOX_BACKEND` - Sandbox backend (default: "docker", or "e2b")
- `CORS_ORIGINS` - CORS origins (default: "*")

**Cloud Providers:**
- Vertex AI: `CLAUDE_CODE_USE_VERTEX`, `CLOUD_ML_REGION`, `ANTHROPIC_VERTEX_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS`
- Bedrock: `CLAUDE_CODE_USE_BEDROCK`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- Azure: `CLAUDE_CODE_USE_FOUNDRY`, `AZURE_FOUNDRY_RESOURCE`, `AZURE_API_KEY`

## API Reference

### POST /query

Run an agent query.

**Request:**
```json
{
  "prompt": "your task here",
  "model": "sonnet",
  "max_turns": 30,
  "timeout": 300,
  "files": {
    "src/main.py": "def main():\n    pass",
    "README.md": "# My Project"
  },
  "anthropic_api_key": "sk-ant-...",
  "openrouter_api_key": "sk-or-..."
}
```

**Response:** Server-Sent Events (SSE) stream

```
data: {"type":"assistant_message","content":"I'll help you..."}
data: {"type":"tool_use","name":"bash","command":"python main.py"}
data: {"type":"result","success":true}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "sandbox_backend": "docker",
  "api_keys": {
    "anthropic": true,
    "openrouter": false
  }
}
```

## Client Examples

### Python

```python
import requests

response = requests.post(
    "http://localhost:8000/query",
    json={"prompt": "Create hello.py and run it"},
    stream=True
)

for line in response.iter_lines():
    if line:
        print(line.decode())
```

### JavaScript

```javascript
const response = await fetch('http://localhost:8000/query', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    prompt: 'Create hello.py and run it'
  })
});

const reader = response.body.getReader();
while (true) {
  const {done, value} = await reader.read();
  if (done) break;
  console.log(new TextDecoder().decode(value));
}
```

### cURL

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Create hello.py and run it"}' \
  --no-buffer
```

## Deployment

### Docker Compose

```bash
# Set API keys in .env file
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# Build agent image
docker build -f Dockerfile.agent -t sandstorm-agent:latest .

# Start services
docker-compose up -d

# Query the API
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test"}'
```

### Production

For production deployments:

1. **Build optimized image:**
   ```dockerfile
   # Multi-stage build to reduce size
   FROM node:24-bookworm-slim AS builder
   RUN npm install -g @anthropic-ai/claude-agent-sdk@0.2.42

   FROM node:24-bookworm-slim
   COPY --from=builder /usr/local/lib/node_modules /usr/local/lib/node_modules
   # ... rest of setup
   ```

2. **Configure resource limits:**
   ```yaml
   # config/limits.yaml
   max_concurrent_agents: 10
   cpu_limit: "4"
   memory_limit: "8gb"
   session_timeout_seconds: 1800
   ```

3. **Use secrets management:**
   ```bash
   # Don't use environment variables in production
   # Use Docker secrets or vault
   docker secret create anthropic_key ./api_key.txt
   ```

4. **Enable monitoring:**
   ```bash
   # Monitor container metrics
   docker stats

   # View logs
   docker-compose logs -f sandstorm-api
   ```

## Docker vs E2B

Sandstorm-Docker supports both Docker (default) and E2B backends.

### Comparison

| Feature | Docker (Default) | E2B Cloud |
|---------|-----------------|-----------|
| **Cost** | Free (just API usage) | $0.05-0.20 per agent |
| **Speed** | 1-2s cold start | 5-8s cold start |
| **Latency** | Local (0ms) | Variable (network) |
| **Setup** | Build image once | API key only |
| **Dependencies** | Docker daemon | Internet connection |
| **Privacy** | Fully local | Data sent to E2B |
| **Scaling** | Hardware limited | API limited |

### Using E2B (Optional)

To use E2B cloud sandboxes instead of Docker:

```bash
export SANDBOX_BACKEND=e2b
export E2B_API_KEY=e2b_...
export ANTHROPIC_API_KEY=sk-ant-...

ds "your query"
```

**When to use E2B:**
- You don't want to manage Docker
- You need sandboxes in specific regions
- You're prototyping and want zero setup
- You're already invested in E2B ecosystem

**When to use Docker (default):**
- You want fully local execution
- You need to minimize costs
- You have Docker expertise
- You need custom sandbox images
- You want faster cold starts

## Security

### Docker Security

Each container is hardened with:

```python
# From docker_impl.py
container = client.containers.create(
    image="sandstorm-agent:latest",
    cap_drop=["ALL"],  # Drop all capabilities
    cap_add=["CHOWN", "DAC_OVERRIDE", "FOWNER", "SETGID", "SETUID"],  # Add only essential
    security_opt=["no-new-privileges"],  # Prevent privilege escalation
    mem_limit="4gb",  # Memory limit
    cpu_count=2,  # CPU limit
    network_mode="bridge",  # Network isolation
    remove=True  # Auto-cleanup
)
```

### Best Practices

1. **Don't commit secrets** - Use `.env` files (gitignored)
2. **Rotate API keys** - Regularly rotate Anthropic/OpenRouter keys
3. **Review agent output** - Monitor what agents are doing
4. **Limit resources** - Set appropriate CPU/memory/timeout limits
5. **Update regularly** - Keep base images and dependencies updated
6. **Scan images** - `docker scan sandstorm-agent:latest`
7. **Use read-only where possible** - Minimize container write access

## Troubleshooting

### Docker image not found

```bash
# Build the agent image
docker build -f Dockerfile.agent -t sandstorm-agent:latest .
```

### Permission denied on Docker socket

```bash
# Linux: Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Or run with sudo (not recommended)
sudo ds "your query"
```

### Containers not cleaning up

```bash
# Manual cleanup
docker ps -a --filter "label=sandstorm.managed=true" -q | xargs docker rm -f

# Check logs
docker logs <container-id>
```

### Max concurrent agents error

```
RuntimeError: Max concurrent agents (5) reached
```

Edit `config/limits.yaml` to increase `max_concurrent_agents`, or wait for existing agents to complete.

### Session timeout

```
Container exceeded 600s timeout, forcing cleanup
```

Edit `config/limits.yaml` to increase `session_timeout_seconds`:

```yaml
session_timeout_seconds: 1800  # 30 minutes
```

### Resource limits not working

**Linux:** Ensure cgroups v2 is enabled:
```bash
docker info | grep "Cgroup Version"
```

**Mac/Windows:** Check Docker Desktop resource settings.

## Development

```bash
# Clone repo
git clone https://github.com/anishg-rohlik/sandstorm-docker.git
cd sandstorm-docker

# Install with uv
uv sync

# Build agent image
docker build -f Dockerfile.agent -t sandstorm-agent:latest .

# Run tests
uv run pytest

# Run in development mode
uv run python -m sandstorm.cli serve --reload
```

## License

MIT License - see [LICENSE](LICENSE) file.

## Acknowledgments

- Original [sandstorm](https://github.com/tomascupr/sandstorm) by [@tomascupr](https://github.com/tomascupr)
- Built with [Claude Agent SDK](https://docs.anthropic.com/en/docs/agents-and-tools/claude-agent-sdk)
- Inspired by the agent runtime at [duvo.ai](https://duvo.ai)

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

- **Issues:** [GitHub Issues](https://github.com/anishg-rohlik/sandstorm-docker/issues)
- **Discussions:** [GitHub Discussions](https://github.com/anishg-rohlik/sandstorm-docker/discussions)
