# Tests

End-to-end tests for sandstorm-docker.

## Running Tests

### Prerequisites

1. **Docker** - Must be running
2. **Agent Image** - Build once:
   ```bash
   docker build -f Dockerfile.agent -t sandstorm-agent:latest .
   ```
3. **Authentication** - Configure one of:
   - Direct Anthropic: `export ANTHROPIC_API_KEY=sk-ant-...`
   - Vertex AI: Configure `.env` with GCP credentials
   - See [../.env](../.env) for other options

### Run End-to-End Test

```bash
# From repository root
python tests/test_e2e.py
```

**Expected output:**
```
================================================================================
COMPLETE END-TO-END TEST - VERTEX AI AUTHENTICATION
================================================================================

Environment Configuration:
  CLAUDE_CODE_USE_VERTEX: 1
  ...

[OK] END-TO-END TEST PASSED!

Summary:
  - Total events: 12
  - Authentication: Vertex AI (GCP)
  - Model: claude-sonnet-4-5
  - Sandbox: Docker
  - Status: SUCCESS
```

## Test Coverage

- **test_e2e.py** - Complete end-to-end workflow test
  - Environment validation
  - Sandbox creation
  - Agent execution
  - Event streaming
  - Result verification

## Adding Tests

To add new tests:

1. Create `test_*.py` in this directory
2. Use the pattern from `test_e2e.py`:
   ```python
   import asyncio
   from dotenv import load_dotenv
   from sandstorm.orchestrator import run_agent_in_sandbox
   from sandstorm.models import QueryRequest

   load_dotenv()

   async def test_my_feature():
       request = QueryRequest(
           prompt="test prompt",
           model="claude-sonnet-4-5",
           max_turns=10,
       )
       async for event in run_agent_in_sandbox(request):
           # Assertions here
           pass
   ```

3. Run with: `python tests/test_my_feature.py`

## Future: pytest Integration

To integrate with pytest:

1. Install pytest:
   ```bash
   pip install pytest pytest-asyncio
   ```

2. Create `conftest.py`:
   ```python
   import pytest

   @pytest.fixture
   def sandbox_request():
       return QueryRequest(
           prompt="test",
           model="claude-sonnet-4-5",
           max_turns=5,
       )
   ```

3. Run all tests:
   ```bash
   pytest tests/
   ```
