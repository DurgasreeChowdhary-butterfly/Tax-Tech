import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _run_alembic(*args: str, database_url: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env={"DATABASE_URL": database_url, **_inherited_env()},
        capture_output=True,
        text=True,
    )


def _inherited_env() -> dict[str, str]:
    import os

    return dict(os.environ)


def test_alembic_migrates_empty_db_up_and_down(tmp_path) -> None:
    # Uses a throwaway SQLite file so the test doesn't require a running
    # Postgres server; production configuration still targets Postgres
    # via DATABASE_URL (see app/core/config.py).
    db_url = f"sqlite:///{(tmp_path / 'phase1_test.db').as_posix()}"

    upgrade = _run_alembic("upgrade", "head", database_url=db_url)
    assert upgrade.returncode == 0, upgrade.stderr

    downgrade = _run_alembic("downgrade", "base", database_url=db_url)
    assert downgrade.returncode == 0, downgrade.stderr
