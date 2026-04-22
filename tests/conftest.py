"""Shared test fixtures."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import backend.database as database
from backend.bootstrap import ensure_runtime_directories, register_pdf_fonts
from backend.config import settings


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def api_server(tmp_path: Path) -> str:
    database_path = tmp_path / "test.db"
    database.configure_database(f"sqlite:///{database_path.as_posix()}")
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
    port = _get_free_port()
    command = [
        "python",
        "-m",
        "uvicorn",
        "backend.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    if env.get("ENABLE_TEST_SERVER_COVERAGE") == "1":
        command = [
            "python",
            "-m",
            "coverage",
            "run",
            "--parallel-mode",
            "-m",
            "uvicorn",
            "backend.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ]

    ensure_runtime_directories()
    register_pdf_fonts()

    process = subprocess.Popen(
        command,
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"

    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            response = requests.get(f"{base_url}/", timeout=0.5)
            if response.status_code == 200:
                break
        except requests.RequestException:
            time.sleep(0.2)
    else:
        process.terminate()
        process.wait(timeout=5)
        raise RuntimeError("Timed out waiting for test API server")

    try:
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        database.configure_database(settings.database_url)


@pytest.fixture
def isolated_database(tmp_path: Path) -> Path:
    database_path = tmp_path / "unit.db"
    database.configure_database(f"sqlite:///{database_path.as_posix()}")
    database.init_db()
    ensure_runtime_directories()
    register_pdf_fonts()
    return database_path
