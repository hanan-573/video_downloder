# YT Downloader Pro

A powerful local-network YouTube downloader that supports video downloads up to **4K @ 60fps** and **MP3 audio extraction**. Built with a Flask backend, a Node.js proxy server, and a modern 3D-animated web interface.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Node.js](https://img.shields.io/badge/Node.js-20%2B-green)
![Flask](https://img.shields.io/badge/Flask-Backend-black)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## ✨ Features

- 🎬 **Download YouTube videos** in multiple resolutions (144p up to 4K)
- 🎵 **MP3 audio-only** download (192 kbps)
- ⚡ **Real-time progress** with speed, ETA, and stage tracking (SSE)
- 📱 **QR code** to open the app on your phone (same Wi-Fi)
- 🎨 **5 color themes** (Ocean, Violet, Emerald, Sunset, Rose)
- 🌌 **3D animated background** using Three.js
- 📂 **Downloaded files list** with direct save/download links
- 🔒 **YouTube-only** URL validation for safety
- 🖥️ **Cross-platform** (Windows, Linux, macOS)

---

## 🛠️ Tech Stack

| Layer       | Technology                              |
|-------------|------------------------------------------|
| Backend     | Python 3.11, Flask, Flask-CORS          |
| Downloader  | yt-dlp, imageio-ffmpeg, FFmpeg          |
| QR Code     | segno                                   |
| Proxy       | Node.js 20+ (native `http` module)      |
| Frontend    | HTML5, TailwindCSS (CDN), Three.js      |
| Launcher    | Python (conda-based env management)     |

---

## 📂 Project Structure

```
video_downloader/
│
├── app.py              # Flask backend (API + downloader logic)
├── server.js           # Node.js HTTP server + /api proxy
├── index.html          # Frontend UI (single-file)
├── start.py            # Launcher (sets up conda env, starts servers)
├── stop.py             # Stops running servers
├── requirements.txt    # Python dependencies
├── package.json        # Node.js metadata
├── run.log             # Runtime logs (auto-generated)
├── pids.json           # Running process IDs (auto-generated)
└── README.md
```

---

## ⚙️ Installation

### Prerequisites

Make sure the following are installed on your system:

1. **Miniconda / Anaconda / Miniforge** — [Download](https://docs.conda.io/en/latest/miniconda.html)
2. **Node.js 20+** — [Download](https://nodejs.org/)
3. **FFmpeg** *(optional — `imageio-ffmpeg` provides a bundled binary)*

### Setup

1. Clone or download this project:
```bash
git clone https://github.com/your-username/video_downloader.git
cd video_downloader
```

2. Run the launcher (it will create the conda env and install everything automatically):
```bash
python start.py
```

The script will:
- Find or create a conda env named `yt-downloader-pro`
- Install all Python dependencies from `requirements.txt`
- Upgrade `yt-dlp` to the latest version
- Start the Flask backend on port `5055`
- Start the Node.js proxy on port `8080`
- Open the app in your default browser

---

## ▶️ Usage

1. **Start the app:**
   ```bash
   python start.py
   ```

2. **Paste a YouTube link** in the input field and click **Analyze**.

3. **Choose a quality** (e.g., `1080p`, `4K 2160p`, or `MP3 audio only`).

4. Click **Download** and watch the real-time progress bar.

5. **Access from your phone:** Scan the QR code shown in the app (must be on the same Wi-Fi network).

6. **Stop the app:**
   ```bash
   python stop.py
   ```

Downloaded files are saved to:
```
~/Downloads/YT-Downloader/
```

---

## 🔌 API Endpoints

| Method | Endpoint              | Description                          |
|--------|-----------------------|--------------------------------------|
| GET    | `/api/health`         | Health check                         |
| GET    | `/api/network`        | Returns LAN IP, port, and QR code    |
| POST   | `/api/info`           | Fetches video metadata + qualities   |
| POST   | `/api/download`       | Starts a download job                |
| GET    | `/api/progress/<id>`  | SSE stream for job progress          |
| GET    | `/api/files`          | Lists downloaded files               |
| GET    | `/api/files/<name>`   | Downloads a specific file            |

---

## 🎨 Themes

Click any color swatch in the header to switch themes. Your choice is saved in `localStorage`.

- 🌊 Ocean (default)
- 💜 Violet
- 💚 Emerald
- 🌅 Sunset
- 🌹 Rose

---

## ⚠️ Notes & Troubleshooting

- **4K files** play best in **VLC Media Player**.
- 4K is only available if the original video was uploaded in 4K.
- If the phone can't open the link, allow **Node.js** and **Python** through your firewall on **Private networks**.
- Slow downloads or `HTTP 403 Forbidden` errors are usually caused by YouTube rate-limiting — try updating yt-dlp:
  ```bash
  conda activate yt-downloader-pro
  pip install -U "yt-dlp[default]"
  ```

---

## 🤝 Contributing

Contributions are welcome! Feel free to fork this repo, open an issue, or submit a pull request.

---

## 📜 License

This project is licensed under the **MIT License**.

---

## 👨‍💻 Author

**Your Name**
- GitHub: [@your-username](https://github.com/your-username)
- Email: your.email@example.com

---

## ⭐ Support

If you find this project useful, please give it a **star** on GitHub!

> **Disclaimer:** This tool is intended for personal use only. Please respect YouTube's Terms of Service and copyright laws. Do not download content you do not have the rights to.
