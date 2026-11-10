"""Start the real app with uvicorn for the browser tests.

The ``page`` fixture (a fresh Chromium tab per test) comes from the
pytest-playwright plugin. The app needs PostgreSQL at DATABASE_URL; the
fixture builds the tables with the Alembic migrations before starting it.
"""

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from app.database import engine
from tests.migrations import reset_and_migrate

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def server_url():
    """Run uvicorn in a separate process for the whole test session."""
    reset_and_migrate(engine)
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=PROJECT_ROOT,
        env=os.environ.copy(),
    )
    try:
        deadline = time.monotonic() + 30
        while True:
            if process.poll() is not None:
                pytest.fail("The app exited during startup. Is DATABASE_URL set and PostgreSQL running?")
            try:
                with urllib.request.urlopen(f"{url}/health", timeout=1):
                    break
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                if time.monotonic() > deadline:
                    pytest.fail("The app did not start within 30 seconds")
                time.sleep(0.25)
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover
            process.kill()
