from __future__ import annotations

import argparse
import os
import sys

from . import __version__, data, report
from . import scalper
from .analysis import analyse


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gold-setup",
        description="XAU/USD (gold) institutional scalping scanner: MTF FVG+EMA pullback, "
                    "Session Sweep & CHoCH, Order Block + RSI Divergence, Asian Range "
                    "Breakout, and Supply/Demand Zone Flip.",
        epilog="Signals are technical-analysis only and not financial advice.",
    )
    p.add_argument("--interval", choices=data.VALID_INTERVALS, default="5m",
                   help="execution timeframe (default: 5m; 5m or 15m for the sweep strategy)")
    p.add_argument("--range", choices=data.VALID_RANGES, default=None,
                   help="history range (default: auto based on interval)")
    p.add_argument("--account", type=float, default=10000.0,
                   help="account balance in USD for position sizing (default: 10000)")
    p.add_argument("--risk", type=float, default=1.0,
                   help="percent of account risked per trade (default: 1.0)")
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    p.add_argument("--no-color", action="store_true", help="disable ANSI colors")
    p.add_argument("--no-cache", action="store_true", help="always fetch fresh data")
    p.add_argument("--realtime", action="store_true",
                   help="alias for --no-cache: fetch the latest data on every run")
    p.add_argument("--cache-dir", default=None, help="override cache directory")
    p.add_argument("--verbose", action="store_true", help="show every evidence line")
    p.add_argument("--serve", action="store_true",
                   help="start the web dashboard server instead of the CLI report")
    p.add_argument("--host", default="127.0.0.1", help="dashboard bind host (with --serve)")
    p.add_argument("--port", type=int, default=None,
                   help="dashboard port (with --serve; defaults to $PORT or 8080)")
    p.add_argument("--watch-alerts", action="store_true",
                   help="with --serve: also run the 24/7 Telegram setup watcher in the background")
    p.add_argument("--daemon", action="store_true",
                   help="with --serve/--watch: detach and run in the background")
    p.add_argument("--log", default=None, help="log file (with --serve/--watch --daemon)")
    p.add_argument("--pid", default=None, help="pid file (with --serve/--watch --daemon)")
    p.add_argument("--stop", action="store_true", help="stop the running dashboard daemon")
    p.add_argument("--watch", action="store_true",
                   help="run the 24/7 scanner that alerts on Telegram when a setup appears")
    p.add_argument("--watch-interval", type=int, default=300,
                   help="seconds between scans in --watch mode (default: 300)")
    p.add_argument("--stop-watch", action="store_true", help="stop the running watch daemon")
    p.add_argument("--telegram-setup", action="store_true",
                   help="save Telegram bot token + chat id to the cache dir")
    p.add_argument("--telegram-test", action="store_true",
                   help="send a Telegram test message with the current scan result")
    p.add_argument("--bot-token", default=None, help="Telegram bot token (with --telegram-setup)")
    p.add_argument("--chat-id", default=None, help="Telegram chat id (with --telegram-setup)")
    p.add_argument("--version", action="version", version=f"gold-setup {__version__}")
    return p


def _fetch(interval: str, rng: str, use_cache: bool, cache_dir: str | None) -> list:
    return data.fetch_candles(interval, rng, cache=use_cache,
                              cache_dir=cache_dir, force=not use_cache)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.telegram_setup:
        from . import telegram

        token = args.bot_token or input("Telegram bot token: ").strip()
        chat = args.chat_id or input("Telegram chat id: ").strip()
        if not chat:
            print("resolving chat id from the latest bot update...", file=sys.stderr)
            chat = telegram.resolve_chat_id(token)
            if not chat:
                print("error: no chat found. Message your bot once on Telegram, then retry.",
                      file=sys.stderr)
                return 1
        telegram.save_config(token, chat)
        print(f"Telegram configured: chat_id={chat}")
        return 0
    if args.telegram_test:
        from . import telegram

        try:
            msg = "✅ XAU/USD scanner Telegram test — alert channel is working."
            if telegram.send_message(msg):
                print("test message sent (check Telegram)")
                return 0
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    if args.stop_watch:
        from .watch import stop_watch

        if stop_watch(args.pid):
            print("watch stop signal sent")
        else:
            print("no running watch daemon found", file=sys.stderr)
            return 1
        return 0
    if args.watch:
        from .watch import run_watch

        if args.daemon:
            from .web import _daemonize

            cache_dir = data._default_cache_dir()
            log_file = args.log or os.path.join(cache_dir, "watch.log")
            pid_file = args.pid or os.path.join(cache_dir, "watch.pid")
            _daemonize(log_file)
            with open(pid_file, "w", encoding="utf-8") as fh:
                fh.write(str(os.getpid()))
            print(f"watch daemon started pid={os.getpid()} log={log_file}", flush=True)
        run_watch(watch_interval=args.watch_interval, account=args.account,
                  risk_pct=args.risk, cache_dir=args.cache_dir)
        return 0
    if args.stop:
        from .web import stop_daemon

        if stop_daemon(args.pid):
            print("dashboard stop signal sent")
        else:
            print("no running dashboard daemon found", file=sys.stderr)
            return 1
        return 0
    if args.serve:
        from .web import serve as web_serve

        web_serve(args.host, args.port, daemon=args.daemon, log_file=args.log,
                  pid_file=args.pid, with_watch=args.watch_alerts,
                  watch_interval=args.watch_interval, account=args.account,
                  risk_pct=args.risk)
        return 0
    if not (0 < args.risk <= 100):
        print("error: --risk must be in (0, 100]", file=sys.stderr)
        return 2

    use_cache = not (args.no_cache or args.realtime)
    exec_interval = args.interval
    rng = args.range or data.DEFAULT_RANGES.get(exec_interval, "1d")
    try:
        exec_candles = _fetch(exec_interval, rng, use_cache, args.cache_dir)
        macro_candles = _fetch("1h", data.DEFAULT_RANGES["1h"], use_cache, args.cache_dir)
        liq_candles = _fetch("15m", data.DEFAULT_RANGES["15m"], use_cache, args.cache_dir)
    except Exception as exc:
        print(f"error: failed to fetch market data: {exc}", file=sys.stderr)
        return 1

    setups = scalper.scan(exec_candles, macro_candles, liq_candles,
                          balance=args.account, risk_pct=args.risk)
    snapshot = analyse(exec_candles)
    if args.json:
        print(report.render_json(exec_candles, snapshot, setups, exec_interval,
                                 args.account, args.risk, source=data.LAST_SOURCE))
    else:
        print(report.render_report(exec_candles, snapshot, setups, exec_interval,
                                   args.account, args.risk, source=data.LAST_SOURCE,
                                   no_color=args.no_color, stream=sys.stdout,
                                   verbose=args.verbose))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())