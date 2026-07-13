import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
POSTGRES_TEST_URL = os.environ.get("PHASE2_POSTGRES_TEST_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="Set PHASE2_POSTGRES_TEST_URL to a real PostgreSQL DSN to run this migration check.",
)


def _run_alembic(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": POSTGRES_TEST_URL},
        capture_output=True,
        text=True,
    )


def test_alembic_migrates_up_and_down_on_real_postgres() -> None:
    upgrade = _run_alembic("upgrade", "head")
    assert upgrade.returncode == 0, upgrade.stderr

    downgrade = _run_alembic("downgrade", "base")
    assert downgrade.returncode == 0, downgrade.stderr

    restore = _run_alembic("upgrade", "head")
    assert restore.returncode == 0, restore.stderr
