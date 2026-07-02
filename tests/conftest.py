"""
conftest.py — Shared pytest fixtures for MCP server integration tests.

Provides:
  • mcp_session fixture (session-scoped) — starts real server, opens ClientSession
  • Event loop fixture for async tests
"""

import pytest
import pytest_asyncio
import asyncio
import os
import sys

# Ensure src is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
