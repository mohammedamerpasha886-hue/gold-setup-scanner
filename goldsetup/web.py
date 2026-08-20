from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import data, report, scalper
from .analysis import analyse

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
CHART_CANDLES = 180


def _range_for(interval: str) -> str:
    return data.DEFAULT_RANGES.get(interval, "1y")


def build_overview(interval: str, account: float, risk: float,
                   use_cache: bool = True) -> dict:
    exec_candles = data.fetch_candles(interval, _range_for(interval), cache=use_cache)
    macro_candles = data.fetch_candles("1h", data.DEFAULT_RANGES["1h"], cache=use_cache)
    liq_candles = data.fetch_candles("15m", data.DEFAULT_RANGES["15m"], cache=use_cache)

    a = analyse(exec_candles)
    setups = scalper.scan(exec_candles, macro_candles, liq_candles,
                          balance=account, risk_pct=risk)

    payload = json.loads(report.render_json(exec_candles, a, setups, interval, account, risk,
                                            source=data.LAST_SOURCE))
    payload["realtime"] = not use_cache
    payload["candles"] = [
        {"t": c.timestamp, "o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume}
        for c in exec_candles[-CHART_CANDLES:]
    ]
    return payload


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload).encode("utf-8"))

    def _json_error(self, code: int, message: str) -> None:
        self._send_json(code, {"error": message})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        try:
            if path in ("/", "/index.html"):
                self._serve_static("index.html")
                return
            if path == "/api/overview":
                interval = query.get("interval", ["5m"])[0]
                account = float(query.get("account", ["10000"])[0])
                risk = float(query.get("risk", ["1"])[0])
                realtime = query.get("realtime", ["0"])[0] in ("1", "true", "yes")
                self._send_json(200, build_overview(interval, account, risk,
                                                    use_cache=not realtime))
                return
            if path == "/api/health":
                self._send_json(200, {"status": "ok"})
                return
            self._json_error(404, f"not found: {path}")
        except ValueError:
            self._json_error(400, "invalid query parameter")
        except Exception as exc:
            self._json_error(500, str(exc))

    def _serve_static(self, name: str) -> None:
        target = (WEB_DIR / name).resolve()
        if WEB_DIR.resolve() not in target.parents:
            self._json_error(403, "forbidden")
            return
        if not target.is_file():
            self._json_error(404, "missing static file")
            return
        ctype = "text/html; charset=utf-8" if name.endswith(".html") else "text/plain"
        self._send(200, target.read_bytes(), ctype)


def serve(host: str = "127.0.0.1", port: int | None = None, daemon: bool = False,
          log_file: str | None = None, pid_file: str | None = None,
          with_watch: bool = False, watch_interval: int = 300,
          account: float = 10000.0, risk_pct: float = 1.0) -> None:
    import threading

    port = port or int(os.environ.get("PORT") or 8080)
    if daemon:
        log_file = log_file or str(Path(data._default_cache_dir()) / "dashboard.log")
        pid_file = pid_file or str(Path(data._default_cache_dir()) / "dashboard.pid")
        _daemonize(log_file)
        with open(pid_file, "w", encoding="utf-8") as fh:
            fh.write(str(os.getpid()))
        print(f"daemon started pid={os.getpid()} log={log_file}", flush=True)
    if with_watch:
        from .watch import run_watch

        def _watch_loop() -> None:
            run_watch(watch_interval=watch_interval, account=account, risk_pct=risk_pct)

        threading.Thread(target=_watch_loop, name="gold-watch", daemon=True).start()
        print("Telegram watcher embedded — setup alerts active while the server runs", flush=True)
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"XAU/USD dashboard running at http://{host}:{port}  (Ctrl+C to stop)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down", flush=True)
    finally:
        httpd.server_close()
        if daemon and pid_file:
            try:
                os.remove(pid_file)
            except OSError:
                pass


def _daemonize(log_path: str) -> None:
    import os

    pid = os.fork()
    if pid > 0:
        os._exit(0)
    os.setsid()
    pid = os.fork()
    if pid > 0:
        os._exit(0)
    os.chdir("/")
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    os.dup2(fd, 0)
    os.dup2(fd, 1)
    os.dup2(fd, 2)
    if fd > 2:
        os.close(fd)


def stop_daemon(pid_file: str | None = None) -> bool:
    import os

    pid_file = pid_file or str(Path(data._default_cache_dir()) / "dashboard.pid")
    try:
        with open(pid_file, "r", encoding="utf-8") as fh:
            pid = int(fh.read().strip())
        os.kill(pid, 15)
        return True
    except (OSError, ValueError):
        return False


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(prog="gold-setup-web", description="XAU/USD dashboard server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--daemon", action="store_true", help="detach and run in the background")
    p.add_argument("--log", default=None, help="log file (with --daemon)")
    p.add_argument("--pid", default=None, help="pid file (with --daemon)")
    p.add_argument("--stop", action="store_true", help="stop the running daemon")
    p.add_argument("--watch-alerts", action="store_true",
                   help="also run the 24/7 Telegram setup watcher in the background")
    args = p.parse_args()
    if args.stop:
        if stop_daemon(args.pid):
            print("daemon stop signal sent")
        else:
            print("no running daemon found", file=__import__("sys").stderr)
        return
    serve(args.host, args.port, daemon=args.daemon, log_file=args.log, pid_file=args.pid,
          with_watch=args.watch_alerts)


if __name__ == "__main__":
    main()