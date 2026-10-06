#!/usr/bin/env python3
"""Stop YT Downloader Pro. Standard library only."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIDS_FILE = HERE / "pids.json"


def kill_pid(pid):
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, text=True)
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except Exception:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                return
        for _ in range(20):
            try:
                os.kill(pid, 0)
            except Exception:
                return
            time.sleep(0.2)
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass


def main():
    if not PIDS_FILE.exists():
        print("Not running")
        return

    try:
        data = json.loads(PIDS_FILE.read_text())
    except Exception:
        print("Not running")
        PIDS_FILE.unlink(missing_ok=True)
        return

    for key in ("node_pid", "flask_pid"):
        pid = data.get(key)
        if pid:
            kill_pid(pid)

    PIDS_FILE.unlink(missing_ok=True)
    print("Stopped")


if __name__ == "__main__":
    main()