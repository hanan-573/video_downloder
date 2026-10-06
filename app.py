import os
import re
import shutil
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context
from flask_cors import CORS
import segno
import yt_dlp
from yt_dlp.postprocessor import FFmpegExtractAudioPP

try:
    import imageio_ffmpeg
except Exception:
    imageio_ffmpeg = None

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = Path.home() / "Downloads" / "YT-Downloader"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

API_PORT = int(os.environ.get("API_PORT", "5055"))
PUBLIC_PORT = int(os.environ.get("PUBLIC_PORT", "8080"))

JOBS = {}
JOBS_LOCK = threading.Lock()

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}


def get_ffmpeg_location():
    p = shutil.which("ffmpeg")
    if p:
        return p
    if imageio_ffmpeg is not None:
        try:
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return None
    return None


FFMPEG = get_ffmpeg_location()


def clean_error(msg):
    if not msg:
        return "Unknown error"
    msg = ANSI_RE.sub("", str(msg))
    msg = msg.replace("\n", " ").strip()
    # Keep short readable
    if "ERROR:" in msg:
        msg = msg.split("ERROR:", 1)[1].strip()
    return msg[:280]


def is_valid_youtube(url):
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    return host in ALLOWED_HOSTS


def base_ydl_opts():
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "windowsfilenames": True,
        "js_runtimes": {"node": {}},
    }
    if FFMPEG:
        opts["ffmpeg_location"] = FFMPEG
    return opts


def format_duration(seconds):
    try:
        seconds = int(seconds)
    except Exception:
        return "0:00"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return "%d:%02d:%02d" % (h, m, s)
    return "%d:%02d" % (m, s)


def human_size(num):
    try:
        num = float(num)
    except Exception:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024:
            if unit == "B":
                return "%d %s" % (int(num), unit)
            return "%.1f %s" % (num, unit)
        num /= 1024
    return "%.1f PB" % num


@app.route("/api/health")
def health():
    return jsonify({"ok": True})


@app.route("/api/network")
def network():
    import socket
    ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    url = "http://%s:%d" % (ip, PUBLIC_PORT)
    try:
        qr = segno.make(url, error="m").png_data_uri(scale=8, border=2)
    except Exception:
        qr = ""
    return jsonify({"ip": ip, "port": PUBLIC_PORT, "url": url, "qr": qr})


@app.route("/api/info", methods=["POST"])
def info():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "Missing URL"}), 400
    if not is_valid_youtube(url):
        return jsonify({"error": "Please provide a valid YouTube link."}), 400

    opts = base_ydl_opts()
    opts["skip_download"] = True

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
    except Exception as e:
        return jsonify({"error": clean_error(str(e))}), 400

    if not info_dict:
        return jsonify({"error": "Could not fetch video info."}), 400

    formats = info_dict.get("formats") or []
    height_fps = {}
    for f in formats:
        vcodec = f.get("vcodec")
        height = f.get("height")
        fps = f.get("fps") or 0
        if not vcodec or vcodec == "none":
            continue
        if not height or height < 144:
            continue
        if height not in height_fps or fps > height_fps[height]:
            height_fps[height] = fps

    qualities = []
    for h in sorted(height_fps.keys(), reverse=True):
        fps = height_fps[h]
        fps_int = int(round(fps)) if fps else 0
        if h >= 2160:
            prefix = "4K %dp" % h
        elif h >= 1440:
            prefix = "2K %dp" % h
        else:
            prefix = "%dp" % h
        label = prefix
        if fps_int > 30:
            label += " %dfps" % fps_int
        qualities.append({"height": h, "fps": fps_int, "label": label})

    return jsonify({
        "title": info_dict.get("title") or "",
        "thumbnail": info_dict.get("thumbnail") or "",
        "duration": info_dict.get("duration") or 0,
        "uploader": info_dict.get("uploader") or info_dict.get("channel") or "",
        "qualities": qualities,
    })


def make_progress_hook(job_id):
    def hook(d):
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if not job:
                return
            status = d.get("status")
            info = d.get("info_dict") or {}
            vcodec = info.get("vcodec") or ""
            job["stage"] = "video" if (vcodec and vcodec != "none") else "audio"

            if status == "downloading":
                downloaded = d.get("downloaded_bytes") or 0
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                if total > 0:
                    job["percent"] = round((downloaded / total) * 100.0, 1)
                speed = d.get("speed")
                if speed:
                    job["speed"] = "%.1f MB/s" % (speed / 1024 / 1024)
                eta = d.get("eta")
                if eta is not None:
                    try:
                        eta = int(eta)
                        job["eta"] = "%02d:%02d" % (eta // 60, eta % 60)
                    except Exception:
                        pass
                job["status"] = "downloading"
            elif status == "finished":
                job["status"] = "merging"
                job["percent"] = 100.0
                job["speed"] = ""
                job["eta"] = ""
    return hook


def run_download(job_id, url, height, audio_only):
    try:
        opts = base_ydl_opts()
        opts["progress_hooks"] = [make_progress_hook(job_id)]

        if audio_only:
            opts["format"] = "bestaudio/best"
            opts["outtmpl"] = str(DOWNLOAD_DIR / "%(title).120B.%(ext)s")
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
            if FFMPEG:
                opts["ffmpeg_location"] = FFMPEG
        else:
            H = int(height)
            opts["format"] = "bestvideo[height<=%d]+bestaudio/best[height<=%d]/best" % (H, H)
            opts["outtmpl"] = str(DOWNLOAD_DIR / "%(title).120B [%(height)sp].%(ext)s")
            if H <= 1080:
                opts["format_sort"] = ["res", "fps", "vcodec:h264", "acodec:aac"]
                opts["merge_output_format"] = "mp4"
            else:
                opts["merge_output_format"] = "mkv"

        with yt_dlp.YoutubeDL(opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

        filepath = None
        try:
            requested = info_dict.get("requested_downloads") or []
            if requested:
                filepath = requested[0].get("filepath")
        except Exception:
            filepath = None

        if not filepath:
            filepath = info_dict.get("_filename")

        if filepath:
            filename = os.path.basename(filepath)
        else:
            filename = None

        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if job:
                job["status"] = "done"
                job["percent"] = 100.0
                job["filename"] = filename
                job["speed"] = ""
                job["eta"] = ""
    except Exception as e:
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if job:
                job["status"] = "error"
                job["error"] = clean_error(str(e))


@app.route("/api/download", methods=["POST"])
def download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "Missing URL"}), 400
    if not is_valid_youtube(url):
        return jsonify({"error": "Please provide a valid YouTube link."}), 400

    audio_only = bool(data.get("audio"))
    height = data.get("height")

    if not audio_only:
        if height is None:
            return jsonify({"error": "Missing height"}), 400
        try:
            height = int(height)
        except Exception:
            return jsonify({"error": "Invalid height"}), 400

    job_id = uuid.uuid4().hex
    with JOBS_LOCK:
        JOBS[job_id] = {
            "status": "starting",
            "percent": 0.0,
            "speed": "",
            "eta": "",
            "stage": "audio" if audio_only else "video",
            "filename": None,
            "error": None,
        }

    t = threading.Thread(target=run_download, args=(job_id, url, height, audio_only), daemon=True)
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/api/progress/<job_id>")
def progress(job_id):
    with JOBS_LOCK:
        if job_id not in JOBS:
            return jsonify({"error": "Unknown job"}), 404

    def generator():
        while True:
            with JOBS_LOCK:
                job = JOBS.get(job_id)
                if not job:
                    snapshot = {"status": "error", "error": "Job lost"}
                else:
                    snapshot = {
                        "status": job["status"],
                        "percent": job["percent"],
                        "speed": job["speed"],
                        "eta": job["eta"],
                        "stage": job["stage"],
                        "filename": job["filename"],
                        "error": job["error"],
                    }
            import json as _json
            yield "data: " + _json.dumps(snapshot) + "\n\n"

            if snapshot["status"] in ("done", "error"):
                break
            time.sleep(0.5)

    return Response(
        stream_with_context(generator()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


INTERMEDIATE_RE = re.compile(r"\.f\d+\.\w+$")


@app.route("/api/files")
def files():
    items = []
    try:
        entries = list(DOWNLOAD_DIR.iterdir())
    except Exception:
        entries = []

    for p in entries:
        if not p.is_file():
            continue
        name = p.name
        if name.endswith(".part") or name.endswith(".ytdl") or name.endswith(".temp"):
            continue
        if INTERMEDIATE_RE.search(name):
            continue
        try:
            st = p.stat()
            size = human_size(st.st_size)
            modified = time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
        except Exception:
            continue
        items.append({"name": name, "size": size, "modified": modified, "_mtime": st.st_mtime})

    items.sort(key=lambda x: x["_mtime"], reverse=True)
    for it in items:
        it.pop("_mtime", None)

    return jsonify({"files": items})


@app.route("/api/files/<path:name>")
def download_file(name):
    safe = os.path.basename(name)
    return send_from_directory(str(DOWNLOAD_DIR), safe, as_attachment=True)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=API_PORT, threaded=True, debug=False)