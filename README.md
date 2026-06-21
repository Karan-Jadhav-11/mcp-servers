# MCP Health & Utility Servers

A fast, modular Model Context Protocol (MCP) project built with `fastmcp`. This project hosts multiple independent MCP servers that provide health tools, live weather data, database querying, and video generation capabilities to any MCP-compatible AI client.

## Overview

This repository has been optimized into a clean `src/` structure, featuring three distinct MCP servers running via Server-Sent Events (SSE) transport:

1. **Health & Weather Server** (`health_weather_server.py`): Fetches live weather using OpenWeatherMap, calculates BMI, and provides health tips.
2. **Database Server** (`db_server.py`): Connects to a local SQLite database, allowing the AI to list tables, describe schemas, and run smart queries with LLM sampling summaries.
3. **Manim Server** (`manim_server.py`): Generates mathematical animations and videos using the Manim engine.

## Folder Structure

```text
/mcp-health-server
  ├── src/
  │    ├── servers/
  │    │    ├── health_weather_server.py  # Weather API + Health Tools
  │    │    ├── db_server.py              # SQLite MCP Server
  │    │    └── manim_server.py           # Video Generation
  │    └── scripts/
  │         └── init_db.py                # Database seed script
  ├── Dockerfile                          # Multi-server Docker setup
  ├── .env                                # Environment variables (API keys)
  └── pyproject.toml                      # Dependencies
```

## Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) (for ultra-fast dependency management)
- OpenWeatherMap API Key (for the weather server)
- Local Manim installation (for the manim server)

## Installation

1. Clone or navigate to the repository:
   ```bash
   cd mcp-health-server
   ```
2. Install dependencies via `uv`:
   ```bash
   uv sync
   ```
3. Create a `.env` file in the root directory and add your API keys:
   ```env
   OPENWEATHER_API_KEY="your_api_key_here"
   ```

## Setup & Running Locally

### 1. Initialize the Database
Before running the database server, seed the local SQLite database:
```bash
uv run python src/scripts/init_db.py
```
This creates `database.db` populated with mock health logs and user data.

### 2. Run the Servers (SSE Mode)
You can run any of the servers directly. They are configured to run as HTTP servers utilizing SSE transport:

```bash
uv run python src/servers/health_weather_server.py  # Runs on port 8000
uv run python src/servers/db_server.py              # Runs on port 8001
uv run python src/servers/manim_server.py           # Runs on port 8002
```

## Docker Support

This project includes a single `Dockerfile` that packages all three servers. You can specify which server to run by setting the `MCP_SERVER` environment variable:
- `health_weather_server` (default)
- `db_server`
- `manim_server`

To build and run via Docker:
```bash
docker build -t mcp-health-server .
docker run -p 8000:8000 --env-file .env -e MCP_SERVER=health_weather_server mcp-health-server
```

### Deploying to Render
This repository includes a `render.yaml` Blueprint file. To deploy all three servers:
1. Connect this repository to Render via the **Blueprints** dashboard.
2. Render will automatically provision three separate Web Services.
3. Don't forget to manually add your `OPENWEATHER_API_KEY` to the `mcp-health-weather` service in the Render dashboard!

## Claude Desktop Configuration

If you've deployed these servers to Render (or another remote host), you can connect Claude Desktop to them using the `mcp-remote` npx package. 

Add the following to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "remote-health-weather": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://YOUR-APP-URL.onrender.com/sse",
        "--transport",
        "sse-only"
      ]
    },
    "remote-database": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://YOUR-DB-URL.onrender.com/sse",
        "--transport",
        "sse-only"
      ]
    }
  }
}
```
*(Note: Because these FastMCP servers use SSE transport, you MUST specify `--transport sse-only` when using mcp-remote).*

## Security

All three servers are hardened with production-grade security layers, powered by FastMCP's native middleware system.

### Defence Layers (in order)
1. **🔒 Authentication** — Bearer token validation via `Authorization: Bearer <key>` header
2. **⚡ Rate Limiting** — Token bucket algorithm (10 burst, 5 req/sec sustained)
3. **🧹 Input Sanitization** — String length limits, regex patterns, path traversal prevention, SQL injection blocking
4. **🧠 Prompt Injection Defence** — Strips known injection patterns from external API/DB responses
5. **📝 Structured Logging** — JSON-formatted request/response logs (never logs sensitive arguments)
6. **🛡️ Error Handling** — Clean MCP error responses (no stack traces leaked to clients)
7. **📏 Response Limiting** — 500KB cap on tool responses to protect LLM context window

### API Key Authentication

Authentication is controlled via the `MCP_API_KEYS` environment variable:

```bash
# Generate a secure key
python -c "from src.security import generate_api_key; print(generate_api_key())"

# Set it (comma-separated for multiple keys)
export MCP_API_KEYS="mcp_Zf8k2vN3pL7mQ9xRsT6hJ4wA1yE5cB0dI"
```

**Key rotation without downtime:**
1. Generate a new key
2. Add it alongside the old key: `MCP_API_KEYS="old-key,new-key"`
3. Update all clients to use the new key
4. Remove the old key

**Local development:** Leave `MCP_API_KEYS` empty or unset — auth is disabled automatically.

### Security Checklist
- ✅ API key middleware rejects unauthenticated requests
- ✅ Keys compared with `secrets.compare_digest()` (timing-attack safe)
- ✅ Keys loaded from environment variables (never hardcoded)
- ✅ Multi-key rotation support without downtime
- ✅ Every tool argument validated (type, range, length, pattern)
- ✅ Path traversal prevention via `Path.resolve()` inside base directory
- ✅ SQL queries checked for dangerous patterns (DROP, DELETE, INSERT, etc.)
- ✅ String inputs have max-length limits
- ✅ Numeric inputs have bounds checking
- ✅ Per-server rate limiting with token bucket algorithm
- ✅ External content wrapped with `[EXTERNAL DATA]` labels
- ✅ Known prompt injection patterns detected and stripped
- ✅ Error messages don't leak internal server details
- ✅ Dockerfile runs as non-root user
- ✅ Manim code execution blocks dangerous patterns (os.system, eval, exec, etc.)

## Running Tests

Install test dependencies and run the full suite:

```bash
uv sync --extra dev
uv run pytest tests/ -v --tb=short
```

The test suite covers:
- **95 tests** across 3 test files
- Input sanitization (strings, paths, numbers, enums, SQL)
- Output sanitization (prompt injection detection & stripping)
- Authentication (key validation, local dev mode)
- SQL safety (blocked patterns, multi-statement prevention)
- BMI calculation accuracy
- Middleware factory creation
