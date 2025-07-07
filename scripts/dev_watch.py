#!/usr/bin/env python3
"""Launch Streamlit and tail runtime log.

Usage: python3 scripts/dev_watch.py

Automatically restarts Streamlit when code changes (via --server.runOnSave) and
prints new log lines so they appear in the dev console for ChatGPT iteration.
"""
import subprocess
import threading
import time
from pathlib import Path
import os

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_PATH = LOG_DIR / "dashboard_runtime.log"


def tail_log(path: Path):
    """Continuously print appended lines from *path*."""
    path.touch(exist_ok=True)
    with path.open() as fp:
        fp.seek(0, os.SEEK_END)
        while True:
            line = fp.readline()
            if line:
                print("[LOG]", line.rstrip())
            else:
                time.sleep(0.5)


def main():
    # 1) Fast smoke-test to catch syntax errors before launching Streamlit
    smoke = subprocess.run(["python3", "scripts/quick_smoke.py"], check=False)
    if smoke.returncode != 0:
        print("[dev_watch] Smoke-test failed – fix the above errors before Streamlit reloads.")
        return

    # 2) Headless UI smoke-test (Playwright)
    ui_smoke = subprocess.run(["python3", "scripts/ui_smoke.py"], check=False)
    if ui_smoke.returncode != 0:
        print("[dev_watch] UI smoke-test failed – see errors above.")
        return

    # Start Streamlit in separate process
    cmd = ["streamlit", "run", "dashboard/Home.py", "--server.runOnSave", "true"]
    proc = subprocess.Popen(cmd)

    # Tail thread
    t = threading.Thread(target=tail_log, args=(LOG_PATH,), daemon=True)
    t.start()

    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()


if __name__ == "__main__":
    main() 