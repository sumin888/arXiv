"""Sandboxed Python execution via E2B Code Interpreter."""
from __future__ import annotations

from app.config import settings

SCHEMA = {
    "name": "execute_python",
    "description": (
        "Execute Python code in an isolated E2B sandbox and return stdout/stderr. "
        "Use for reproducing paper results, computing statistics, verifying formulas, "
        "running model snippets, or any numerical experiment. "
        "Install packages with `!pip install <pkg>` at the top of the code block. "
        "Requires E2B_API_KEY to be configured."
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
                "description": "Execution timeout in seconds (default 30, max 120)",
                "default": 30,
            },
        },
        "required": ["code"],
    },
}


async def execute_python(code: str, timeout: int = 30) -> str:
    timeout = min(int(timeout), 120)

    try:
        from e2b_code_interpreter import AsyncSandbox  # type: ignore
    except ImportError:
        return (
            "E2B is not installed. "
            "Run `pip install e2b-code-interpreter` and set E2B_API_KEY in backend/.env."
        )

    if not settings.e2b_api_key:
        return "E2B_API_KEY is not set in backend/.env. Code execution is disabled."

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
