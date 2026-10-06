#!/usr/bin/env python3
"""YT Downloader Pro launcher. Standard library only."""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ENV_NAME = "yt-downloader-pro"
DEFAULT_PORT = 8080
DEFAULT_API_PORT = 5055
HERE = Path(__file__).resolve().parent


def log(msg):
    print(msg, flush=True)


def find_conda():
    exe = os.environ.get("CONDA_EXE")
    if exe and Path(exe).exists():
        return exe

    which = shutil.which("conda")
    if which:
        return which

    candidates = [
        Path.home() / "miniconda3",
        Path.home() / "anaconda3",
        Path.home() / "miniforge3",
        Path.home() / "mambaforge",
        Path("/opt/miniconda3"),
        Path("/opt/anaconda3"),
        Path("C:/ProgramData/miniconda3"),
        Path("C:/ProgramData/anaconda3"),
        Path(os.environ.get("USERPROFILE", "")) / "miniconda3",
        Path(os.environ.get("USERPROFILE", "")) / "anaconda3",
    ]

    for base in candidates:
        if not base or not str(base) or not base.exists():
            continue
        for rel in ("condabin/conda.bat", "Scripts/conda.exe", "bin/conda"):
            p = base / rel
            if p.exists():
                return str(p)
    return None


def run_conda(conda, args, check=True):
    if sys.platform == "win32" and conda.lower().endswith(".bat"):
        cmd = ["cmd", "/c", conda] + args
    else:
        cmd = [conda] + args
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def get_env_path(conda):
    try:
        r = run_conda(conda, ["env", "list", "--json"])
        data = json.loads(r.stdout)
    except Exception as e:
        log("Failed to list conda envs: %s" % e)
        return None

    for env_path in data.get("envs", []):
        if Path(env_path).name == ENV_NAME:
            return env_path
    return None


def find_free_port(preferred):
    for port in range(preferred, preferred + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    return preferred


def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def is_alive(pid):
    try:
        if sys.platform == "win32":
            r = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid],
                               capture_output=True, text=True)
            return str(pid) in r.stdout
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def main():
    os.chdir(HERE)

    conda = find_conda()
    if not conda:
        log("ERROR: conda was not found on this system.")
        log("Please install Miniconda, Anaconda or Miniforge, then run this script again.")
        log("  Miniconda: https://docs.conda.io/en/latest/miniconda.html")
        sys.exit(1)

    log("Using conda: %s" % conda)

    # Check node
    node = shutil.which("node")
    if not node:
        log("ERROR: Node.js was not found. Install Node.js 20+ and try again.")
        log("  https://nodejs.org/")
        sys.exit(1)
    try:
        r = subprocess.run(["node", "--version"], capture_output=True, text=True)
        ver = r.stdout.strip().lstrip("v")
        major = int(ver.split(".")[0])
        if major < 20:
            log("ERROR: Node.js 20+ is required. Found v%s" % ver)
            sys.exit(1)
        log("Node.js version: v%s" % ver)
    except Exception as e:
        log("ERROR checking Node.js: %s" % e)
        sys.exit(1)

    # Find or create conda env
    env_path = get_env_path(conda)
    if not env_path:
        log("Creating conda env '%s' (this may take a few minutes)..." % ENV_NAME)
        r = run_conda(conda, [
            "create", "-y", "-n", ENV_NAME,
            "-c", "conda-forge", "--override-channels",
            "python=3.11", "pip"
        ], check=False)
        if r.returncode != 0:
            log("ERROR creating conda env:")
            log(r.stdout or "")
            log(r.stderr or "")
            sys.exit(1)
        env_path = get_env_path(conda)
        if not env_path:
            log("ERROR: could not locate the newly created env.")
            sys.exit(1)

    log("Conda env path: %s" % env_path)

    if sys.platform == "win32":
        env_python = str(Path(env_path) / "python.exe")
    else:
        env_python = str(Path(env_path) / "bin" / "python")

    if not Path(env_python).exists():
        log("ERROR: env python not found at %s" % env_python)
        log("Run: conda env remove -n %s -y and then python start.py again" % ENV_NAME)
        sys.exit(1)

    # Verify python version
    try:
        r = subprocess.run([env_python, "-c",
                            "import sys; print('%d.%d' % sys.version_info[:2])"],
                           capture_output=True, text=True)
        pyver = r.stdout.strip()
    except Exception as e:
        log("ERROR checking env python: %s" % e)
        sys.exit(1)

    if pyver not in ("3.10", "3.11"):
        log("ERROR: env python version is %s, need 3.10 or 3.11." % pyver)
        log("Run: conda env remove -n %s -y and then python start.py again" % ENV_NAME)
        sys.exit(1)
    log("Env Python: %s" % pyver)

    # Install requirements
    log("Installing requirements...")
    subprocess.run([env_python, "-m", "pip", "install", "-q", "-r",
                    str(HERE / "requirements.txt")], check=False)

    # Best-effort yt-dlp upgrade
    try:
        subprocess.run([env_python, "-m", "pip", "install", "-q", "-U",
                        "yt-dlp[default]"], check=False, timeout=180)
    except Exception as e:
        log("Note: yt-dlp upgrade skipped (%s)" % e)

    # Check if already running
    pids_file = HERE / "pids.json"
    if pids_file.exists():
        try:
            data = json.loads(pids_file.read_text())
            node_alive = is_alive(data.get("node_pid", 0))
            flask_alive = is_alive(data.get("flask_pid", 0))
            if node_alive and flask_alive:
                port = data.get("port", DEFAULT_PORT)
                ip = get_lan_ip()
                url = "http://%s:%d" % (ip, port)
                log("Already running. Open on this PC or phone (same Wi-Fi): %s" % url)
                try:
                    webbrowser.open(url)
                except Exception:
                    pass
                log("Stop with: python stop.py")
                return
        except Exception:
            pass

    # Pick ports
    port = find_free_port(DEFAULT_PORT)
    api_port = find_free_port(DEFAULT_API_PORT)
    log("Using ports: Node=%d Flask=%d" % (port, api_port))

    # Start Flask
    log_file = open(HERE / "run.log", "a", encoding="utf-8")
    log_file.write("\n===== %s =====\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
    log_file.flush()

    flask_env = os.environ.copy()
    flask_env["API_PORT"] = str(api_port)
    flask_env["PUBLIC_PORT"] = str(port)
    flask_env["PYTHONUNBUFFERED"] = "1"

    node_env = os.environ.copy()
    node_env["PORT"] = str(port)
    node_env["API_PORT"] = str(api_port)

    popen_kwargs = {
        "cwd": str(HERE),
        "stdin": subprocess.DEVNULL,
        "stdout": log_file,
        "stderr": subprocess.STDOUT,
        "env": flask_env,
    }

    if sys.platform == "win32":
        flags = (subprocess.DETACHED_PROCESS |
                 subprocess.CREATE_NEW_PROCESS_GROUP |
                 subprocess.CREATE_NO_WINDOW)
        popen_kwargs["creationflags"] = flags

    flask_cmd = [env_python, str(HERE / "app.py")]
    flask_proc = subprocess.Popen(flask_cmd, **popen_kwargs)

    popen_kwargs["env"] = node_env
    node_proc = subprocess.Popen(["node", str(HERE / "server.js")], **popen_kwargs)

    # Save pids
    (HERE / "pids.json").write_text(json.dumps({
        "flask_pid": flask_proc.pid,
        "node_pid": node_proc.pid,
        "port": port,
        "api_port": api_port,
    }, indent=2))

    # Wait for health
    import urllib.request
    health_url = "http://127.0.0.1:%d/api/health" % port
    ok = False
    for _ in range(50):
        try:
            with urllib.request.urlopen(health_url, timeout=1) as resp:
                if resp.status == 200:
                    ok = True
                    break
        except Exception:
            pass
        time.sleep(0.5)

    if not ok:
        log("WARNING: server did not become healthy in time. Last log lines:")
        try:
            lines = (HERE / "run.log").read_text(encoding="utf-8",
                                                 errors="ignore").splitlines()
            for line in lines[-25:]:
                log(line)
        except Exception:
            pass

    ip = get_lan_ip()
    url = "http://%s:%d" % (ip, port)
    log("")
    log("Open on this PC or phone (same Wi-Fi): %s" % url)
    log("If the phone cannot open the link, allow Node.js/Python through the firewall on Private networks.")
    log("Stop with: python stop.py")
    try:
        webbrowser.open(url)
    except Exception:
        pass


if __name__ == "__main__":
    main()