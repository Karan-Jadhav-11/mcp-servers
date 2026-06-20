import aiosqlite
import re
from fastmcp import FastMCP, Context
from mcp.types import CreateMessageRequestParams, SamplingMessage
import mcp.types as types
import os
import sys
import threading
import time
import urllib.request
import logging

# Ensure we can import from src.scripts
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from src.scripts.init_db import seed_database  # type: ignore

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "database.db"))
logger = logging.getLogger("db_server")

mcp = FastMCP("sqlite-db-server")


# ── @mcp.prompt() — one decorator replaces list_prompts + get_prompt ─
@mcp.prompt()
def analyze_table(table_name: str, focus: str = "general insights") -> str:
    """Analyze a database table: inspect structure, sample rows, and suggest insights."""
    # Return a string → FastMCP wraps it as a user message automatically
    return f"""Please analyze the database table '{table_name}' with a focus on: {focus}.

Steps:
1. Use describe_table(table_name="{table_name}") to see the schema
2. Use query_database(sql="SELECT * FROM {table_name} LIMIT 10") to see sample data
3. Use query_database(sql="SELECT COUNT(*) FROM {table_name}") to see total size
4. Report: column descriptions, data patterns, key statistics, and actionable {focus} insights."""

# ── SAFETY: block dangerous SQL patterns ────────────────────

READ_ONLY_PATTERN = re.compile(
    r'^\s*(SELECT|WITH|PRAGMA)\b',
    re.IGNORECASE
)

BLOCKED_PATTERNS = [
    r'\bDROP\b',
    r'\bDELETE\b',
    r'\bUPDATE\b',
    r'\bINSERT\b',
    r'\bALTER\b',
    r'\bCREATE\b',
    r'\bATTACH\b',
    r'\bDETACH\b',
    r'\bREPLACE\b',
    r'\bVACUUM\b',
]

def is_safe_query(sql : str) -> tuple[bool , str]:
    sql = sql.upper().strip()

    if ";" in sql.rstrip(";"):
        return False, "Multiple SQL statements are not allowed"

    if not READ_ONLY_PATTERN.match(sql):
        return False, (
            "Only read-only queries (SELECT, WITH, PRAGMA) "
            "are allowed via query_database"
        )

    for pattern in BLOCKED_PATTERNS:
        match = re.search(pattern, sql, re.IGNORECASE)
        if match:
            return False, f"Blocked keyword: {match.group()}"

    return True,""

# ── TOOL: query_database ─────────────────────────────────────

@mcp.tool()
async def query_database(sql: str, ctx: Context, limit: int = 50) -> str:
    """Run a SELECT SQL query on the database. Returns formatted table results. Max 100 rows."""
    await ctx.info(f"Executing query: {sql[:80]}")
    limit = min(limit,100)

    safe, reason = is_safe_query(sql)

    if not safe:
        await ctx.warning(f"Query blocked: {reason}")
        return f"❌ Query blocked: {reason}"

    if "LIMIT" not in sql:
        sql += f" LIMIT {limit}"

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql) as cursor:
                rows = await cursor.fetchall()
                cols = [d[0] for d in cursor.description] if cursor.description else []

        if not rows:
            await ctx.info("Query completed successfully, 0 rows returned.")
            return "✓ Query ran, 0 rows returned."

        header = " | ".join(cols)
        sep    = "-+-".join(["-" * len(c) for c in cols])
        data_rows = [" | ".join(str(r[c]) for c in cols) for r in rows]
        table = f"{header}\n{sep}\n" + "\n".join(data_rows)
        await ctx.info("Query completed successfully")
        return f"✓ {len(rows)} row(s) returned:\n\n{table}"

    except aiosqlite.OperationalError as e:
        await ctx.error(f"Query failed: {e}")
        return f"❌ SQL error: {e}"

@mcp.tool()
async def smart_query_summary(sql: str, ctx: Context) -> str:
    """Ask the Host's LLM to summarize raw query results in bullet points."""
    raw_data = await query_database(sql, ctx=ctx)
    result = await ctx.request_sampling(
        CreateMessageRequestParams(
            messages=[
                SamplingMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"""
Summarize this database query result in 2-3 bullet points.
Focus on key trends and anomalies. Be concise.

Data:
{raw_data}
"""
                    )
                )
            ],
            maxTokens=300,
        )
    )
    return result.content.text

# ── TOOL: describe_table ─────────────────────────────────────

@mcp.tool()
async def list_tables() -> str:
    """List all tables in the SQLite database."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ) as cur:
            tables = [r[0] async for r in cur]
    return "📋 Tables in database:\n" + "\n".join(f"  • {t}" for t in tables)

# ── TOOL: describe_table ─────────────────────────────────────


@mcp.tool()
async def describe_table(table_name:str) -> str:
    """Show schema for a table: column names, types, and constraints."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(f"PRAGMA table_info ({table_name})") as tbl:
            cols = [ r async for r in tbl]

        if not cols:
            return f"❌ Table '{table_name}' not found."

        lines = [f"📐 Schema for '{table_name}':"]
        for c in cols:
            pk = " 🔑 PRIMARY KEY" if c[5] else ""
            nn = " NOT NULL" if c[3] else ""
            df = f" DEFAULT {c[4]}" if c[4] else ""
            lines.append(f"  {c[1]:20} {c[2]:12}{nn}{df}{pk}")
        return "\n".join(lines)    


# ── RESOURCE: full schema ────────────────────────────────────
@mcp.resource("resource://db/schema")
async def db_schema() -> str:
    """Full database schema — all table CREATE statements."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table'") as cur:
            schemas = [r[0] async for r in cur if r[0]]
    return "-- DATABASE SCHEMA\n" + "\n".join(schemas)

def _keep_alive(port: int):
    """Background task to ping the health endpoint every 10 minutes."""
    while True:
        time.sleep(600)
        try:
            urllib.request.urlopen(f"http://localhost:{port}/health", timeout=5)
            logger.info("Keep-alive ping successful")
        except Exception as e:
            logger.warning(f"Keep-alive ping failed: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    
    # Auto-seed database if it doesn't exist or is empty
    if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0:
        logger.info(f"Database {DB_PATH} not found or empty, running auto-seed...")
        seed_database()
    
    # Start keep-alive daemon thread
    threading.Thread(target=_keep_alive, args=(port,), daemon=True).start()
    
    mcp.run(
        transport="sse",
        host="0.0.0.0",
        port=port,
    )