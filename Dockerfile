# ── Base image ────────────────────────────────────────────────
FROM python:3.11-slim

# Install curl (for health check) and uv 
RUN apt-get update && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv

WORKDIR /app

# ── Copy lockfile + project config FIRST for Docker layer caching ─
# If only code changes, this layer is cached → faster rebuilds
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# ── Copy application code ─────────────────────────────────────
COPY . .

# ── Security: don't run as root ───────────────────────────────
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# ── Runtime configuration ─────────────────────────────────────
# Expose the ports for all our SSE servers
EXPOSE 8000 8001 8002

# Health check — FastMCP exposes /health automatically (if configured/available)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default server if not specified
ENV MCP_SERVER=health_weather_server
ENV DB_PATH=/app/database.db

# Start with uv run — uses the .venv created by uv sync above
# We use shell form so $MCP_SERVER expands correctly
CMD ["sh", "-c", "uv run python src/servers/${MCP_SERVER}.py"]