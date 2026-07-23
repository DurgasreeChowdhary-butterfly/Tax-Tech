#!/usr/bin/env python3
"""One-command developer startup for ITR Filing.

Starts the backend, waits until it's actually healthy, starts the frontend,
waits until it's actually healthy, then streams both processes' output
(prefixed by name) until Ctrl+C — which stops both cleanly. If either
process crashes at any point, its recent output is shown and the other
process is stopped too.

Pure developer tooling: does not change application behavior, config, or
contracts. Not part of the product API surface.

Usage:
    python scripts/dev.py
"""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"

BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
FRONTEND_HOST = "127.0.0.1"
FRONTEND_PORT = 5173

BACKEND_HEALTH_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}/docs"
FRONTEND_HEALTH_URL = f"http://{FRONTEND_HOST}:{FRONTEND_PORT}/"

HEALTH_TIMEOUT_SECONDS = 45
HEALTH_POLL_INTERVAL_SECONDS = 0.4
CRASH_TAIL_LINES = 20

# Same convenience path documented in README.md for local dev without a
# Postgres server — only used when the caller hasn't set DATABASE_URL
# themselves, so this script never touches a real/production database.
DEFAULT_DEV_DATABASE_URL = "sqlite:///./var/dev.db"

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "DemoPassword123!"


class StartupError(Exception):
    """Any condition that should stop the script with a clear, already-
    printed message — never a raw traceback for an operator-facing problem
    (missing venv, port in use, a crashed process)."""


def log(prefix: str, message: str) -> None:
    for line in message.splitlines() or [""]:
        print(f"[{prefix}] {line}", flush=True)


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def check_ports_free() -> None:
    busy = []
    if _port_in_use(BACKEND_HOST, BACKEND_PORT):
        busy.append(BACKEND_PORT)
    if _port_in_use(FRONTEND_HOST, FRONTEND_PORT):
        busy.append(FRONTEND_PORT)
    if not busy:
        return

    find_cmd = "\n".join(f"  netstat -ano | findstr :{port}" for port in busy)
    raise StartupError(
        "Port(s) already in use: " + ", ".join(str(p) for p in busy) + "\n"
        "This is almost always a previous run of this script that wasn't stopped "
        "with Ctrl+C. Find the process and stop it first:\n"
        f"{find_cmd}\n"
        "  taskkill /PID <pid> /T /F"
    )


def find_venv_python() -> Path:
    candidates = [
        BACKEND_DIR / ".venv" / "Scripts" / "python.exe",  # Windows
        BACKEND_DIR / ".venv" / "bin" / "python",  # macOS/Linux
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise StartupError(
        "backend/.venv not found -- one-time setup hasn't been done yet:\n"
        "  cd backend\n"
        "  python -m venv .venv\n"
        "  .venv/Scripts/activate      (.venv/bin/activate on macOS/Linux)\n"
        "  pip install -r requirements.txt -r requirements-dev.txt"
    )


def find_npm() -> str:
    npm = shutil.which("npm")
    if npm is None:
        raise StartupError("npm not found on PATH. Install Node.js (https://nodejs.org), then re-run this script.")
    return npm


class ManagedProcess:
    """A subprocess whose stdout/stderr is streamed live with a name prefix
    and retained (last CRASH_TAIL_LINES lines) so a crash can be reported
    with real context instead of just an exit code."""

    def __init__(self, name: str, args: list[str], cwd: Path, env: dict[str, str]) -> None:
        self.name = name
        self._lines: list[str] = []
        self._lock = threading.Lock()
        # On Windows, put each child in its own process group so a raw
        # Ctrl+C/Ctrl+Break at the console doesn't reach it directly (which,
        # for npm.cmd, pops up a "Terminate batch job (Y/N)?" prompt nobody
        # answers). This script is the sole thing that stops these children,
        # deliberately, via stop() below -- never by an ambient signal.
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        self.process = subprocess.Popen(
            args,
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=creationflags,
        )
        self._reader = threading.Thread(target=self._read_output, daemon=True)
        self._reader.start()

    def _read_output(self) -> None:
        assert self.process.stdout is not None
        for raw_line in self.process.stdout:
            line = raw_line.rstrip("\n")
            log(self.name, line)
            with self._lock:
                self._lines.append(line)
                del self._lines[:-CRASH_TAIL_LINES]

    def tail(self) -> str:
        with self._lock:
            return "\n".join(self._lines)

    def is_alive(self) -> bool:
        return self.process.poll() is None

    def stop(self) -> None:
        if self.process.poll() is not None:
            return
        if sys.platform == "win32":
            # taskkill /T kills the whole tree — needed because npm.cmd is a
            # wrapper around the actual node/vite process and does not
            # forward a plain terminate() to it.
            subprocess.run(
                ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        else:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()


def wait_healthy(proc: ManagedProcess, url: str, label: str) -> None:
    deadline = time.time() + HEALTH_TIMEOUT_SECONDS
    while time.time() < deadline:
        if not proc.is_alive():
            raise StartupError(
                f"{label} exited before it became healthy (exit code {proc.process.returncode}).\n"
                f"Last output:\n{proc.tail()}"
            )
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status < 400:
                    return
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        time.sleep(HEALTH_POLL_INTERVAL_SECONDS)
    raise StartupError(f"{label} did not become healthy within {HEALTH_TIMEOUT_SECONDS}s (checked {url}).")


def seed_demo_user(python_exe: Path, env: dict[str, str]) -> None:
    log("dev", "Seeding demo user (idempotent -- safe if it already exists)...")
    result = subprocess.run(
        [str(python_exe), "scripts/seed_demo_user.py"],
        cwd=str(BACKEND_DIR), env=env, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise StartupError("Seeding the demo user failed:\n" + (result.stderr or result.stdout))


def print_ready_banner(using_default_db: bool) -> None:
    print(flush=True)
    log("dev", "=" * 64)
    log("dev", "Everything is running.")
    log("dev", f"  Backend:  {BACKEND_HEALTH_URL}")
    log("dev", f"  Frontend: http://{FRONTEND_HOST}:{FRONTEND_PORT}/")
    log("dev", "  (use this exact 127.0.0.1 address -- 'localhost' can resolve to a")
    log("dev", "   different, unlisted address on some machines and refuse to connect)")
    if using_default_db:
        log("dev", f"  Demo login: {DEMO_EMAIL} / {DEMO_PASSWORD}")
    log("dev", "Press Ctrl+C to stop both.")
    log("dev", "=" * 64)
    print(flush=True)


def open_browser() -> None:
    """Best-effort only -- a browser failing to launch (headless CI, no
    default browser configured, sandboxed environment) must never take the
    running app down with it."""
    url = f"http://{FRONTEND_HOST}:{FRONTEND_PORT}/"
    try:
        opened = webbrowser.open(url)
        log("dev", f"Opened {url} in your browser." if opened else f"Could not auto-open a browser -- open {url} yourself.")
    except Exception:
        log("dev", f"Could not auto-open a browser -- open {url} yourself.")


def install_signal_handlers() -> None:
    """Ctrl+C (SIGINT) already raises KeyboardInterrupt via Python's default
    handler for a directly-attached foreground console process — this makes
    that explicit and also covers Ctrl+Break (SIGBREAK, Windows-only), so
    either one reliably reaches the same `finally` cleanup in main()."""

    def _handler(signum: int, frame) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _handler)
    if hasattr(signal, "SIGBREAK"):  # Windows only
        signal.signal(signal.SIGBREAK, _handler)


def main() -> int:
    install_signal_handlers()
    log("dev", "ITR Filing -- one-command dev startup")
    backend: ManagedProcess | None = None
    frontend: ManagedProcess | None = None
    exit_code = 0

    try:
        check_ports_free()
        python_exe = find_venv_python()
        npm = find_npm()

        backend_env = os.environ.copy()
        using_default_db = "DATABASE_URL" not in backend_env
        if using_default_db:
            (BACKEND_DIR / "var").mkdir(exist_ok=True)
            backend_env["DATABASE_URL"] = DEFAULT_DEV_DATABASE_URL
            # Needed for `python scripts/seed_demo_user.py` (a direct script
            # path, not `-m`) to resolve the `app` package from backend/.
            backend_env["PYTHONPATH"] = "."
            log("dev", f"DATABASE_URL not set -- using {DEFAULT_DEV_DATABASE_URL} for local dev.")
            seed_demo_user(python_exe, backend_env)
        else:
            log("dev", "Using DATABASE_URL from your environment (not touching migrations/seed data).")

        log("dev", f"Starting backend on {BACKEND_HOST}:{BACKEND_PORT}...")
        backend = ManagedProcess(
            "backend",
            [str(python_exe), "-m", "uvicorn", "app.main:app", "--host", BACKEND_HOST, "--port", str(BACKEND_PORT)],
            BACKEND_DIR, backend_env,
        )
        wait_healthy(backend, BACKEND_HEALTH_URL, "Backend")
        log("dev", "Backend is healthy.")

        log("dev", f"Starting frontend on {FRONTEND_HOST}:{FRONTEND_PORT}...")
        frontend_env = os.environ.copy()
        frontend_env.setdefault("VITE_BACKEND_ORIGIN", f"http://{BACKEND_HOST}:{BACKEND_PORT}")
        frontend = ManagedProcess(
            "frontend",
            [npm, "run", "dev", "--", "--host", FRONTEND_HOST, "--port", str(FRONTEND_PORT), "--strictPort"],
            FRONTEND_DIR, frontend_env,
        )
        wait_healthy(frontend, FRONTEND_HEALTH_URL, "Frontend")
        log("dev", "Frontend is healthy.")

        print_ready_banner(using_default_db)
        open_browser()

        while True:
            time.sleep(0.5)
            if not backend.is_alive():
                raise StartupError(f"Backend crashed (exit code {backend.process.returncode}).\nLast output:\n{backend.tail()}")
            if not frontend.is_alive():
                raise StartupError(f"Frontend crashed (exit code {frontend.process.returncode}).\nLast output:\n{frontend.tail()}")

    except KeyboardInterrupt:
        print(flush=True)
        log("dev", "Stopping (Ctrl+C)...")
    except StartupError as exc:
        print(flush=True)
        log("dev", f"ERROR: {exc}")
        exit_code = 1
    finally:
        if frontend is not None:
            frontend.stop()
        if backend is not None:
            backend.stop()
        log("dev", "Stopped.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
