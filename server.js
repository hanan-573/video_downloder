const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = parseInt(process.env.PORT || "8080", 10);
const API_PORT = parseInt(process.env.API_PORT || "5055", 10);
const HOST = "0.0.0.0";
const API_HOST = "127.0.0.1";

const INDEX_FILE = path.join(__dirname, "index.html");

const server = http.createServer((req, res) => {
  const url = req.url || "/";

  if (url === "/" || url === "/index.html") {
    fs.readFile(INDEX_FILE, (err, data) => {
      if (err) {
        res.writeHead(500, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "index.html not found" }));
        return;
      }
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end(data);
    });
    return;
  }

  if (url.startsWith("/api/")) {
    const options = {
      host: API_HOST,
      port: API_PORT,
      method: req.method,
      path: url,
      headers: Object.assign({}, req.headers, {
        host: API_HOST + ":" + API_PORT,
      }),
    };

    const proxyReq = http.request(options, (proxyRes) => {
      res.writeHead(proxyRes.statusCode || 502, proxyRes.headers);
      proxyRes.pipe(res);
    });

    proxyReq.on("error", () => {
      if (!res.headersSent) {
        res.writeHead(502, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Backend is starting, try again" }));
      } else {
        res.end();
      }
    });

    res.on("close", () => {
      proxyReq.destroy();
    });

    req.pipe(proxyReq);
    return;
  }

  res.writeHead(404, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ error: "Not found" }));
});

server.listen(PORT, HOST, () => {
  console.log("YT Downloader Pro listening on http://" + HOST + ":" + PORT);
  console.log("Proxying /api/* -> http://" + API_HOST + ":" + API_PORT);
});