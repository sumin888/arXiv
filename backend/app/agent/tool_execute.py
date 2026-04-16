"""Sandboxed Python execution — E2B cloud sandbox or local subprocess fallback."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile

from app.config import settings

SCHEMA = {
    "name": "execute_python",
    "description": (
        "Execute Python code and return stdout/stderr. "
        "Use for reproducing paper results, computing statistics, verifying formulas, "
        "running model snippets, or any numerical experiment. "
        "Prefix lines with `!pip install <pkg>` to install packages. "
        "Uses E2B cloud sandbox when E2B_API_KEY is set; otherwise runs locally via subprocess."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute. May include `!pip install` lines.",
            },
            "timeout": {
                "type": "integer",
                "description": "Execution timeout in seconds (default 60, max 300)",
                "default": 60,
            },
        },
        "required": ["code"],
    },
}


# ── E2B cloud executor ───────────────────────────────────────────────────────

async def _e2b_execute(code: str, timeout: int) -> str:
    from e2b_code_interpreter import AsyncSandbox  # type: ignore

    async with AsyncSandbox(api_key=settings.e2b_api_key) as sandbox:
        execution = await sandbox.run_code(code, timeout=timeout)

    parts: list[str] = []
    if execution.logs.stdout:
        parts.append("".join(execution.logs.stdout))
    if execution.logs.stderr:
        parts.append("[stderr]\n" + "".join(execution.logs.stderr))
    if execution.error:
        parts.append(f"[error] {execution.error.name}: {execution.error.value}")
    for result in execution.results or []:
        if hasattr(result, "text") and result.text:
            parts.append(result.text)

    return "\n".join(parts).strip() or "(no output)"


# ── Local subprocess executor ────────────────────────────────────────────────

def _run_pip_install(packages: list[str], timeout: int) -> str | None:
    """Install packages locally. Returns error string or None on success."""
    cmd = [sys.executable, "-m", "pip", "install", "--quiet"] + packages
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return f"[pip install failed]\n{result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return f"[pip install timed out after {timeout}s]"
    return None


async def _local_execute(code: str, timeout: int) -> str:
    """Run code via local subprocess, handling !pip install lines."""
    # Separate !pip install lines from regular code
    pip_pkgs: list[str] = []
    code_lines: list[str] = []
    for line in code.splitlines():
        stripped = line.strip()
        m = re.match(r"^!pip\s+install\s+(.+)$", stripped, re.IGNORECASE)
        if m:
            pip_pkgs.extend(m.group(1).split())
        else:
            code_lines.append(line)

    parts: list[str] = []

    # Install packages first
    if pip_pkgs:
        err = _run_pip_install(pip_pkgs, timeout=min(timeout, 120))
        if err:
            parts.append(err)

    # Write remaining code to a temp file and run
    actual_code = "\n".join(code_lines).strip()
    if not actual_code:
        return "\n".join(parts).strip() or "(no output)"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(actual_code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.stdout:
            parts.append(result.stdout.rstrip())
        if result.stderr:
            parts.append("[stderr]\n" + result.stderr.rstrip())
        if result.returncode != 0 and not result.stderr:
            parts.append(f"[exited with code {result.returncode}]")
    except subprocess.TimeoutExpired:
        parts.append(f"[error] Execution timed out after {timeout}s")
    finally:
        os.unlink(tmp_path)

    return "\n".join(parts).strip() or "(no output)"


# ── Public entry point ───────────────────────────────────────────────────────

async def execute_python(code: str, timeout: int = 60) -> str:
    timeout = min(int(timeout), 300)

    # Prefer E2B if available
    if settings.e2b_api_key:
        try:
            from e2b_code_interpreter import AsyncSandbox  # noqa: F401
            return await _e2b_execute(code, timeout)
        except ImportError:
            pass  # fall through to local executor

    return await _local_execute(code, timeout)
