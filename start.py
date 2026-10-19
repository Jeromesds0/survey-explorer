"""Runs the whole app with one command:

    uv run start.py

Rebuilds the warehouse from data/raw, starts the API and the Streamlit app, then opens the app
in a browser. Ctrl+C stops everything.
"""

import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import httpx

from pipeline.build import main as build_warehouse

ROOT = Path(__file__).parent
# 127.0.0.1 for the API: "localhost" can add ~2 seconds per request on Windows (IPv6 first)
API_URL = "http://127.0.0.1:8000"
UI_URL = "http://localhost:8501"


def is_up(url: str) -> bool:
    try:
        return httpx.get(url, timeout=1).status_code == 200
    except httpx.TransportError:
        return False


def wait_until_up(url: str, process: subprocess.Popen, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while not is_up(url):
        if process.poll() is not None:
            raise RuntimeError(f"Process stopped before {url} came up")
        if time.monotonic() > deadline:
            raise RuntimeError(f"Timed out waiting for {url}")
        time.sleep(0.5)


def main() -> None:
    os.chdir(ROOT)
    for url in (f"{API_URL}/health", f"{UI_URL}/_stcore/health"):
        if is_up(url):
            sys.exit(f"Something is already running at {url}. Stop it and try again.")

    # Rebuilding takes about a second and guarantees the app matches the raw data
    build_warehouse()

    processes: list[subprocess.Popen] = []
    try:
        api = subprocess.Popen([sys.executable, "-m", "uvicorn", "api.main:app", "--port", "8000"])
        processes.append(api)
        wait_until_up(f"{API_URL}/health", api)

        ui = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "frontend/app.py", "--server.port", "8501"],
            env=os.environ | {"SURVEY_API_URL": API_URL},
        )
        processes.append(ui)
        wait_until_up(f"{UI_URL}/_stcore/health", ui)

        print(f"\nSurvey Explorer is running at {UI_URL} (API docs at {API_URL}/docs)")
        print("Press Ctrl+C to stop.\n")
        webbrowser.open(UI_URL)
        ui.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            process.wait()


if __name__ == "__main__":
    main()
