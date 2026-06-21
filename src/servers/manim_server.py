import subprocess
import tempfile
import os
import shutil
import threading
import time
import urllib.request
import logging
from fastmcp import FastMCP
import sys
import re as regex_module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
# pyrefly: ignore [missing-import]
from src.security import create_auth_provider, create_security_middleware, InputSanitizer

logger = logging.getLogger("manim_server")

mcp = FastMCP("manim-server", auth=create_auth_provider())

# ── Security middleware stack ────────────────────────────────
for middleware in create_security_middleware():
    mcp.add_middleware(middleware)

import shutil

# Get Manim executable path from environment variables or assume it's in the system PATH
default_manim = shutil.which("manim") or r"C:\Users\ACEAR\AppData\Local\Programs\Python\Python311\Scripts\manim.exe"
MANIM_EXECUTABLE = os.getenv("MANIM_EXECUTABLE", default_manim)

TEMP_DIRS = {}
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media")
os.makedirs(BASE_DIR, exist_ok=True)  # Ensure the media folder exists

# Blocked patterns in manim code — prevent arbitrary code execution
BLOCKED_CODE_PATTERNS = [
    r'\bos\.system\b',
    r'\bsubprocess\b',
    r'\b__import__\b',
    r'\beval\s*\(',
    r'\bexec\s*\(',
    r'\bopen\s*\(',
    r'\bcompile\s*\(',
    r'\bgetattr\s*\(',
    r'\bglobals\s*\(',
    r'\bimport\s+os\b',
    r'\bimport\s+sys\b',
    r'\bimport\s+shutil\b',
    r'\bfrom\s+os\b',
    r'\bfrom\s+subprocess\b',
]

@mcp.tool()
def execute_manim_code(manim_code: str) -> str:
    """Execute the Manim code. Only Manim-related imports are allowed."""
    # ── Input validation ────────────────────────────────────
    try:
        manim_code = InputSanitizer.sanitize_string(
            manim_code, name="manim_code", max_length=10000, strip_html=False
        )
    except ValueError as e:
        return f"❌ {e}"

    # Check for dangerous code patterns
    for pattern in BLOCKED_CODE_PATTERNS:
        if regex_module.search(pattern, manim_code):
            return f"❌ Blocked: code contains dangerous pattern ({pattern}). Only Manim-related code is allowed."

    tmpdir = os.path.join(BASE_DIR, "manim_tmp")  
    os.makedirs(tmpdir, exist_ok=True)  # Ensure the temp folder exists
    script_path = os.path.join(tmpdir, "scene.py")
    
    try:
        # Write the Manim script to the temp directory
        with open(script_path, "w") as script_file:
            script_file.write(manim_code)
        
        # Execute Manim with the correct path
        result = subprocess.run(
            [MANIM_EXECUTABLE, "-p", script_path],
            capture_output=True,
            text=True,
            cwd=tmpdir
        )

        if result.returncode == 0:
            TEMP_DIRS[tmpdir] = True
            print(f"Check the generated video at: {tmpdir}")

            return "Execution successful. Video generated."
        else:
            return f"Execution failed: {result.stderr}"

    except Exception as e:
        return f"Error during execution: {str(e)}"



@mcp.tool()
def cleanup_manim_temp_dir(directory: str) -> str:
    """Clean up the specified Manim temporary directory after execution."""
    try:
        # Prevent path traversal — only allow cleanup inside BASE_DIR
        safe_path = InputSanitizer.sanitize_path(directory, BASE_DIR)
        if safe_path.exists():
            shutil.rmtree(safe_path)
            return f"Cleanup successful for directory: {safe_path}"
        else:
            return f"Directory not found: {safe_path}"
    except ValueError as e:
        return f"❌ Security error: {e}"
    except Exception as e:
        return f"Failed to clean up directory. Error: {str(e)}"

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
    port = int(os.environ.get("PORT", 8002))
    
    # Start keep-alive daemon thread
    threading.Thread(target=_keep_alive, args=(port,), daemon=True).start()
    
    mcp.run(
        transport="sse",
        host="0.0.0.0",
        port=port,
    )
