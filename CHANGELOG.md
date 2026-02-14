# Changelog

All notable changes to Sandstorm will be documented in this file.

## [0.2.0] - 2026-02-14

### Bug Fixes

- explicitly cancel background task on client disconnect
- make CORS configurable and fix invalid credentials+wildcard
- bound asyncio queue to prevent memory exhaustion
- add missing request_id to task exception log line
- log suppressed task exceptions instead of silent pass
- add error context and directory creation for file uploads
- narrow template fallback to NotFoundException only
- forward stderr from sandbox agent to SSE stream
- remove unused claude-code CLI install from fallback path
- set 30-minute command timeout to prevent hung agents

### Features

- add SSE keepalive ping every 30 seconds
- health check reports API key configuration status
- add file upload limits (max 20 files, 10MB total)
- validate timeout range (5s-3600s)
- validate sandstorm.json structure on load
- add structured logging and request ID tracking

### Miscellaneous

- pin claude-agent-sdk version for deterministic builds
- add changelog via git-cliff

## [0.1.0] - 2026-02-14

### Features

- initial release of Sandstorm v0.1.0


