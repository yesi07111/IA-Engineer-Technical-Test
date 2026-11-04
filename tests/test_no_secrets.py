import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# This is for catching keys of the providers this project can use before they get pushed
SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"AQ\.[0-9A-Za-z_\-]{40,}"),
    re.compile(r"sk-ant-[0-9A-Za-z_\-]{20,}"),
    re.compile(r"sk-[0-9A-Za-z]{32,}"),
]


def list_tracked_files() -> list[Path]:
    """Lists the files git tracks or would add, ignoring .gitignore'd ones like .env.

    Returns:
        Paths of the files, empty when git is not available.
    """
    try:
        output = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return [ROOT / line for line in output.splitlines() if line]


def test_no_api_key_in_versioned_files():
    files = list_tracked_files()
    if not files:
        pytest.skip("git is not available")

    leaks = []
    for path in files:
        if not path.is_file() or path.suffix in {".pdf", ".png", ".jpg"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            leaks.append(str(path.relative_to(ROOT)))

    assert leaks == [], f"Possible API keys in: {leaks}"


def test_env_file_is_ignored_by_git():
    files = list_tracked_files()
    if not files:
        pytest.skip("git is not available")

    assert ROOT / ".env" not in files
