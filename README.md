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

This project includes a `Dockerfile` that packages all servers. By default, it runs the `health_weather_server.py`. 

To build and run via Docker:
```bash
docker build -t mcp-health-server .
docker run -p 8000:8000 --env-file .env mcp-health-server
```

*(You can easily set up a `docker-compose.yml` to run all three servers simultaneously on their respective ports).*

## Claude Desktop Configuration

If you are using Claude Desktop, you can configure it to launch these servers automatically. Add the following to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "health-weather": {
      "command": "C:\\path\\to\\uv.exe",
      "args": ["run", "python", "src/servers/health_weather_server.py"],
      "cwd": "C:\\path\\to\\mcp-health-server",
      "env": {
        "OPENWEATHER_API_KEY": "your_api_key"
      }
    },
    "my-database": {
      "command": "C:\\path\\to\\uv.exe",
      "args": ["run", "python", "src/servers/db_server.py"],
      "cwd": "C:\\path\\to\\mcp-health-server"
    }
  }
}
```
*(Note: Since these scripts are hardcoded to use SSE transport, you may need to switch them to `stdio` in the python scripts if you want Claude Desktop to run them via `command` properly).*
