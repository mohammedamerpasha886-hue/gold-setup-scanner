from __future__ import annotations

import argparse
import sys

from . import __version__, data, report
from . import scalper
from .analysis import analyse


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gold-setup",
        description="XAU/USD (gold) institutional scalping scanner: MTF FVG+EMA pullback "
                    "and Session Liquidity Sweep & CHoCH.",
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
    p.add_argument("--port", type=int, default=8080, help="dashboard port (with --serve)")
    p.add_argument("--daemon", action="store_true",
                   help="with --serve: detach and run the dashboard in the background")
    p.add_argument("--log", default=None, help="log file (with --serve --daemon)")
    p.add_argument("--pid", default=None, help="pid file (with --serve --daemon)")
    p.add_argument("--stop", action="store_true", help="stop the running dashboard daemon")
    p.add_argument("--version", action="version", version=f"gold-setup {__version__}")
    return p


def _fetch(interval: str, rng: str, use_cache: bool, cache_dir: str | None) -> list:
    return data.fetch_candles(interval, rng, cache=use_cache,
                              cache_dir=cache_dir, force=not use_cache)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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

        web_serve(args.host, args.port, daemon=args.daemon, log_file=args.log, pid_file=args.pid)
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