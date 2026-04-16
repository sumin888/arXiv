"""Experiment runner: clone a GitHub repo, install deps, find entry point, run it."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from app.config import settings

SCHEMA = {
    "name": "run_experiment",
    "description": (
        "Clone a GitHub repository, install its dependencies, locate the experiment "
        "entry point (train.py, main.py, etc.), and run it to capture output. "
        "Use this to reproduce results from a paper's official code implementation. "
        "Returns stdout/stderr from the run."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "Repository in 'owner/name' format (e.g. 'huggingface/transformers')",
            },
            "entry_point": {
                "type": "string",
                "description": (
                    "Relative path to the script to run (e.g. 'train.py' or 'src/main.py'). "
                    "If omitted, the tool auto-detects a common entry point."
                ),
            },
            "args": {
                "type": "string",
                "description": "Command-line arguments to pass to the entry point (e.g. '--epochs 1 --batch-size 32')",
            },
            "timeout": {
                "type": "integer",
                "description": "Run timeout in seconds (default 120, max 600)",
                "default": 120,
            },
        },
        "required": ["repo"],
    },
}

# Common entry point candidates, checked in order
_ENTRY_CANDIDATES = [
    "main.py",
    "train.py",
    "run.py",
    "run_experiment.py",
    "experiment.py",
    "eval.py",
    "evaluate.py",
    "demo.py",
    "src/main.py",
    "src/train.py",
    "src/run.py",
    "scripts/train.py",
    "scripts/run.py",
    "examples/run.py",
]

# Dependency file candidates
_DEP_FILES = [
    ("requirements.txt", "requirements"),
    ("requirements-dev.txt", "requirements"),
    ("pyproject.toml", "pyproject"),
    ("setup.py", "setup"),
    ("setup.cfg", "setup"),
]


def _repo_cache_dir() -> Path:
    d = settings.data_dir / "repos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_name(repo: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", repo)


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s: {' '.join(cmd)}"
    except FileNotFoundError as e:
        return -1, "", str(e)


def _clone_or_update(repo: str, clone_dir: Path) -> str | None:
    """Clone repo if not cached, or fast-forward. Returns error string or None."""
    if (clone_dir / ".git").exists():
        # Already cloned — just pull latest
        rc, _, err = _run(["git", "pull", "--ff-only", "--quiet"], cwd=clone_dir, timeout=60)
        if rc != 0:
            return f"git pull failed: {err.strip()}"
        return None

    url = f"https://github.com/{repo}.git"
    rc, _, err = _run(
        ["git", "clone", "--depth=1", "--quiet", url, str(clone_dir)],
        timeout=120,
    )
    if rc != 0:
        return f"git clone failed: {err.strip()}"
    return None


def _install_deps(clone_dir: Path, timeout: int) -> list[str]:
    """Install dependencies. Returns list of messages."""
    messages: list[str] = []
    installed_any = False

    for fname, kind in _DEP_FILES:
        dep_path = clone_dir / fname
        if not dep_path.exists():
            continue

        if kind == "requirements":
            cmd = [sys.executable, "-m", "pip", "install", "--quiet", "-r", str(dep_path)]
        else:
            # pyproject.toml / setup.py / setup.cfg — install as editable package
            cmd = [sys.executable, "-m", "pip", "install", "--quiet", "-e", str(clone_dir)]

        rc, _, err = _run(cmd, timeout=timeout)
        if rc != 0:
            messages.append(f"[dep install warning] {fname}: {err.strip()[:300]}")
        else:
            messages.append(f"[deps installed from {fname}]")
            installed_any = True
            if kind != "requirements":
                break  # one package-level install is enough

    if not installed_any and not messages:
        messages.append("[no dependency files found — skipping install]")

    return messages


def _find_entry_point(clone_dir: Path, hint: str | None) -> Path | None:
    """Return the path to the best entry point."""
    if hint:
        p = clone_dir / hint
        return p if p.exists() else None

    for candidate in _ENTRY_CANDIDATES:
        p = clone_dir / candidate
        if p.exists():
            return p

    # Last resort: any .py file at top level that looks like a runner
    for p in sorted(clone_dir.glob("*.py")):
        if p.name not in ("setup.py", "conf.py", "conftest.py"):
            return p

    return None


async def run_experiment(
    repo: str,
    entry_point: str | None = None,
    args: str | None = None,
    timeout: int = 120,
) -> str:
    timeout = min(int(timeout), 600)
    # Reserve time for deps install
    run_timeout = max(30, timeout - 90)

    parts: list[str] = []

    # ── 1. Clone ─────────────────────────────────────────────────────────────
    clone_dir = _repo_cache_dir() / _safe_name(repo)
    parts.append(f"[cloning {repo}]")
    err = _clone_or_update(repo, clone_dir)
    if err:
        return f"[clone error] {err}"
    parts.append(f"[cloned to {clone_dir}]")

    # ── 2. Install deps ───────────────────────────────────────────────────────
    dep_msgs = _install_deps(clone_dir, timeout=min(90, timeout - 10))
    parts.extend(dep_msgs)

    # ── 3. Find entry point ───────────────────────────────────────────────────
    ep = _find_entry_point(clone_dir, entry_point)
    if ep is None:
        # List what's in the repo so the LLM can retry with an explicit entry_point
        py_files = [str(p.relative_to(clone_dir)) for p in clone_dir.rglob("*.py") if not any(
            part.startswith(".") or part == "__pycache__" for part in p.parts
        )][:20]
        return "\n".join(parts) + (
            "\n\n[error] Could not find an entry point. "
            f"Python files in repo:\n" + "\n".join(f"  {f}" for f in py_files)
        )

    ep_rel = ep.relative_to(clone_dir)
    parts.append(f"[entry point: {ep_rel}]")

    # ── 4. Run ────────────────────────────────────────────────────────────────
    cmd = [sys.executable, str(ep)]
    if args:
        import shlex
        cmd.extend(shlex.split(args))

    rc, stdout, stderr = _run(cmd, cwd=clone_dir, timeout=run_timeout)

    if stdout:
        parts.append(stdout.rstrip())
    if stderr:
        parts.append("[stderr]\n" + stderr.rstrip())
    if rc == -1 and not stderr:
        parts.append(f"[timed out after {run_timeout}s]")
    elif rc != 0 and rc != -1:
        parts.append(f"[exited with code {rc}]")

    return "\n".join(parts).strip() or "(no output)"
