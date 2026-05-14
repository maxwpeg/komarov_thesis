"""Quick start helper for the backend and sibling frontend project."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_ROOT.parent
FRONTEND_ROOT = REPO_ROOT / "frontend"


def check_python_version() -> bool:
    """Check if Python version is 3.10+."""
    if sys.version_info < (3, 10):
        print("Python 3.10 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    print(f"Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True


def install_backend_dependencies() -> bool:
    """Install Python dependencies from requirements.txt."""
    print("\nInstalling backend dependencies...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=BACKEND_ROOT,
        )
        print("Backend dependencies installed")
        return True
    except subprocess.CalledProcessError:
        print("Failed to install backend dependencies")
        return False


def initialize_database() -> bool:
    """Initialize the backend database."""
    print("\nInitializing database...")
    try:
        from backend.database import init_db

        init_db()
        print("Database initialized")
        return True
    except Exception as exc:
        print(f"Failed to initialize database: {exc}")
        return False


def check_tesseract() -> bool:
    """Check if Tesseract OCR is installed."""
    print("\nChecking for Tesseract OCR...")
    try:
        result = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            print("Tesseract OCR is installed")
            return True
    except FileNotFoundError:
        pass

    print("Tesseract OCR not found")
    print("Download from: https://github.com/UB-Mannheim/tesseract/wiki")
    return False


def install_frontend_dependencies() -> bool:
    """Install Node.js dependencies in ../frontend when it exists."""
    if not FRONTEND_ROOT.exists():
        print("\nFrontend directory not found; skipping npm install")
        return False

    print("\nInstalling frontend dependencies...")
    try:
        subprocess.check_call(["npm", "install"], cwd=FRONTEND_ROOT)
        print("Frontend dependencies installed")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Could not install frontend dependencies")
        print("Make sure Node.js is installed, then run `npm install` in ../frontend")
        return False


def create_directories() -> bool:
    """Create backend runtime directories."""
    print("\nCreating backend runtime directories...")
    for directory in ("uploads", "outputs", "debug_output", "storage_objects"):
        path = BACKEND_ROOT / directory
        os.makedirs(path, exist_ok=True)
        print(f"Created {path.relative_to(BACKEND_ROOT)}/")
    return True


def print_instructions() -> None:
    """Print final launch instructions."""
    print("\nSetup complete")
    print("\nBackend:")
    print("  cd backend")
    print("  uvicorn backend.app:app --host 127.0.0.1 --port 8000")
    print("\nFrontend:")
    print("  cd frontend")
    print("  npm start")
    print("\nFrontend URL: http://localhost:3000")
    print("API docs: http://localhost:8000/docs")


def main() -> None:
    """Run the local setup helper."""
    print("Floor Plan Management System setup")

    if not check_python_version():
        sys.exit(1)

    create_directories()

    if not install_backend_dependencies():
        print("\nBackend setup incomplete, but you can continue manually")

    try:
        initialize_database()
    except Exception as exc:
        print(f"Could not initialize database: {exc}")

    check_tesseract()
    install_frontend_dependencies()
    print_instructions()


if __name__ == "__main__":
    main()
