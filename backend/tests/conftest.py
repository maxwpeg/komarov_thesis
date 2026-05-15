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

os.environ.setdefault("BOOTSTRAP_DEVELOPER_USERNAME", "testdev")
os.environ.setdefault("BOOTSTRAP_DEVELOPER_FULL_NAME", "Test Developer")
os.environ.setdefault("BOOTSTRAP_DEVELOPER_PASSWORD", "test-password")

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

    login_response = requests.post(
        f"{base_url}/api/auth/login",
        json={
            "username": os.environ["BOOTSTRAP_DEVELOPER_USERNAME"],
            "password": os.environ["BOOTSTRAP_DEVELOPER_PASSWORD"],
        },
        timeout=5,
    )
    login_response.raise_for_status()
    auth_cookie = login_response.cookies.get(settings.auth_cookie_name)
    if not auth_cookie:
        process.terminate()
        process.wait(timeout=5)
        raise RuntimeError("Test auth login did not return a session cookie")

    original_request = requests.sessions.Session.request

    def authed_request(self, method, url, **kwargs):
        headers = dict(kwargs.get("headers") or {})
        skip_auth = headers.pop("X-Skip-Test-Auth", None) == "1"
        kwargs["headers"] = headers
        if isinstance(url, str) and url.startswith(base_url) and not skip_auth:
            session_cookie = None
            if getattr(self, "cookies", None) is not None:
                session_cookie = self.cookies.get(settings.auth_cookie_name)
            if not session_cookie:
                cookies = dict(kwargs.get("cookies") or {})
                cookies.setdefault(settings.auth_cookie_name, auth_cookie)
                kwargs["cookies"] = cookies
        return original_request(self, method, url, **kwargs)

    requests.sessions.Session.request = authed_request

    try:
        yield base_url
    finally:
        requests.sessions.Session.request = original_request
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
