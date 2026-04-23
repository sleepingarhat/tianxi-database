"""Git sync helpers — writes commits and pushes to origin.

GitHub Actions provides GITHUB_TOKEN automatically (configured via action checkout).
For local dev, set GH_TOKEN env var.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .paths import (
    ENTRIES_DIR,
    HORSE_FORM_DIR,
    HORSE_INJURY_DIR,
    HORSE_PROFILES_DIR,
    HORSE_TRACKWORK_DIR,
    JOCKEY_RECORDS_DIR,
    LAST_SYNC_JSON,
    REPO_ROOT,
    TRAINER_RECORDS_DIR,
)

logger = logging.getLogger(__name__)

COMMIT_AUTHOR_NAME = os.environ.get("CAPY_GIT_NAME", "天喜 Capy")
COMMIT_AUTHOR_EMAIL = os.environ.get("CAPY_GIT_EMAIL", "capy@tianxi.ai")


def _run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run shell command, stream stdout to logger."""
    result = subprocess.run(cmd, cwd=cwd or REPO_ROOT, capture_output=True, text=True)
    if result.stdout:
        logger.debug(result.stdout.rstrip())
    if result.stderr:
        logger.debug(result.stderr.rstrip())
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result


def count_stats() -> dict[str, int]:
    """Snapshot counts for last_sync.json."""
    def count(path: Path, pattern: str = "*.csv") -> int:
        try:
            return len(list(path.glob(pattern)))
        except Exception:
            return 0

    stats: dict[str, int] = {}
    # Horse profiles: single master CSV file → count rows
    profile_file = HORSE_PROFILES_DIR / "horse_profiles.csv"
    if profile_file.exists():
        try:
            with profile_file.open(encoding="utf-8") as f:
                stats["horses"] = max(0, sum(1 for _ in f) - 1)  # minus header
        except Exception:
            stats["horses"] = 0
    else:
        stats["horses"] = 0

    stats["form_records"] = count(HORSE_FORM_DIR)
    stats["trackwork"] = count(HORSE_TRACKWORK_DIR)
    stats["injury"] = count(HORSE_INJURY_DIR)
    stats["jockey_records"] = count(JOCKEY_RECORDS_DIR)
    stats["trainer_records"] = count(TRAINER_RECORDS_DIR)
    stats["entries"] = count(ENTRIES_DIR, "*.txt")
    return stats


def write_last_sync(source: str = "capy-v2") -> dict:
    """Write last_sync.json. Extended schema vs Replit."""
    payload = {
        "synced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source,
        "stats": count_stats(),
    }
    LAST_SYNC_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def ensure_git_identity() -> None:
    _run(["git", "config", "user.name", COMMIT_AUTHOR_NAME], check=False)
    _run(["git", "config", "user.email", COMMIT_AUTHOR_EMAIL], check=False)


def _auth_remote() -> str:
    """Return authenticated origin URL. Prefer GITHUB_TOKEN (GH Actions), else GH_TOKEN."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN or GH_TOKEN env var required for git push")
    repo = os.environ.get("GITHUB_REPOSITORY", "sleepingarhat/HKJC-Horse-Racing-Results")
    return f"https://x-access-token:{token}@github.com/{repo}.git"


def commit_and_push(
    message: str,
    *,
    branch: str | None = None,
    paths: list[str] | None = None,
    allow_empty: bool = False,
) -> bool:
    """Add, commit, and push. Returns True if a commit was pushed.

    Used by orchestrator after each batch.
    """
    ensure_git_identity()
    # Stage
    if paths:
        _run(["git", "add", "--"] + paths, check=False)
    else:
        _run(["git", "add", "-A"], check=False)

    # Check if staged diff exists
    diff = _run(["git", "diff", "--cached", "--quiet"], check=False)
    if diff.returncode == 0 and not allow_empty:
        logger.info("Nothing to commit for: %s", message)
        return False

    # Commit
    commit_args = ["git", "commit", "-m", message]
    if allow_empty:
        commit_args.append("--allow-empty")
    _run(commit_args)

    # Push
    remote = _auth_remote()
    current_branch = branch or _run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], check=False
    ).stdout.strip()
    _run(["git", "push", remote, f"HEAD:{current_branch}"])
    logger.info("Pushed to %s", current_branch)
    return True


def build_commit_message(task: str, detail: str = "") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    base = f"[capy-v2][skip ci] {ts} · {task}"
    if detail:
        base += f" · {detail}"
    return base
