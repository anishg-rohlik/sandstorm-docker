#!/usr/bin/env python3
"""Complete end-to-end test with full event logging."""

import asyncio
import sys
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sandstorm.orchestrator import run_agent_in_sandbox
from sandstorm.models import QueryRequest

async def test_complete_e2e():
    """Complete end-to-end test."""
    print("=" * 80)
    print("COMPLETE END-TO-END TEST - VERTEX AI AUTHENTICATION")
    print("=" * 80)
    print()

    # Verify environment
    print("Environment Configuration:")
    print(f"  CLAUDE_CODE_USE_VERTEX: {os.getenv('CLAUDE_CODE_USE_VERTEX')}")
    print(f"  ANTHROPIC_VERTEX_PROJECT_ID: {os.getenv('ANTHROPIC_VERTEX_PROJECT_ID')}")
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    print(f"  GOOGLE_APPLICATION_CREDENTIALS: {creds_path}")
    if creds_path and os.path.exists(creds_path):
        print(f"    [OK] Credentials file exists")
    else:
        print(f"    [FAIL] Credentials file not found!")
    print(f"  CLOUD_ML_REGION: {os.getenv('CLOUD_ML_REGION')}")
    print()

    request = QueryRequest(
        prompt="Write a simple 'Hello World' Python script and execute it to verify the sandbox works.",
        model="claude-sonnet-4-5",
        max_turns=10,
    )

    print(f"Test Configuration:")
    print(f"  Prompt: {request.prompt}")
    print(f"  Model: {request.model}")
    print(f"  Max Turns: {request.max_turns}")
    print()
    print("Starting agent execution...")
    print("=" * 80)
    print()

    event_count = 0
    success = False

    try:
        async for event_json in run_agent_in_sandbox(request):
            event_count += 1
            event = json.loads(event_json)
            event_type = event.get("type", "unknown")

            # Print all events for debugging
            print(f"Event #{event_count}: {event_type}")

            if event_type == "result":
                subtype = event.get("subtype", "")
                print()
                print("=" * 80)
                print(f"FINAL RESULT: {subtype}")
                print("=" * 80)

                if subtype == "success":
                    success = True
                    print()
                    print("[OK] END-TO-END TEST PASSED!")
                    print()
                    print("Summary:")
                    print(f"  - Total events: {event_count}")
                    print(f"  - Authentication: Vertex AI (GCP)")
                    print(f"  - Model: {request.model}")
                    print(f"  - Sandbox: Docker")
                    print(f"  - Status: SUCCESS")
                else:
                    print()
                    print(f"[FAIL] Test failed: {subtype}")
                    error = event.get("error", "")
                    if error:
                        print(f"  Error: {error}")

        print()
        print("=" * 80)
        if success:
            print("VERIFICATION COMPLETE - ALL SYSTEMS OPERATIONAL")
            print()
            print("Your sandstorm-docker setup is working correctly with:")
            print("  - Vertex AI authentication via GCP")
            print("  - Claude Sonnet 4.5 model")
            print("  - Docker sandbox execution")
        else:
            print("TEST DID NOT COMPLETE SUCCESSFULLY")
        print("=" * 80)

    except Exception as e:
        print()
        print(f"[FAIL] Exception during test: {e}")
        import traceback
        traceback.print_exc()
        return False

    return success

if __name__ == "__main__":
    result = asyncio.run(test_complete_e2e())
    sys.exit(0 if result else 1)
