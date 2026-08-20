from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

from . import data, report, scalper
from .analysis import analyse
from .data import _default_cache_dir
from .telegram import format_no_setup, format_setup_message, send_message

STATE_FILE = "watch_state.json"
DEFAULT_INTERVAL = 300       # seconds between scans
SAME_SETUP_COOLDOWN = 1800   # don't re-alert the same setup within 30 minutes
HEARTBEAT_EVERY = 14400      # ping "still scanning" every 4h


def _state_path(cache_dir: str | None) -> str:
    return os.path.join(cache_dir or _default_cache_dir(), STATE_FILE)


def _load_state(cache_dir: str | None) -> dict:
    path = _state_path(cache_dir)
    if not os.path.exists(path):
        return {"signatures": {}, "last_signal": 0}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"signatures": {}, "last_signal": 0}


def _save_state(state: dict, cache_dir: str | None) -> None:
    path = _state_path(cache_dir)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)


def _signature(s) -> str:
    return f"{s.strategy}|{s.direction}|{s.entry:.2f}|{s.stop:.2f}|{s.take_profit:.2f}"


def _log(line: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {line}", flush=True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def _scan_once(account: float, risk_pct: float, cache_dir: str | None) -> tuple[list, float, str]:
    exec_candles = data.fetch_candles("5m", data.DEFAULT_RANGES["5m"],
                                      cache=True, cache_dir=cache_dir)
    macro = data.fetch_candles("1h", data.DEFAULT_RANGES["1h"], cache=True, cache_dir=cache_dir)
    liq = data.fetch_candles("15m", data.DEFAULT_RANGES["15m"], cache=True, cache_dir=cache_dir)
    setups = scalper.scan(exec_candles, macro, liq, balance=account, risk_pct=risk_pct)
    return setups, exec_candles[-1].close, data.LAST_SOURCE


def stop_watch(pid_file: str | None = None) -> bool:
    import os
    import signal

    pid_file = pid_file or os.path.join(_default_cache_dir(), "watch.pid")
    try:
        with open(pid_file, "r", encoding="utf-8") as fh:
            pid = int(fh.read().strip())
        os.kill(pid, signal.SIGTERM)
        return True
    except (OSError, ValueError):
        return False


def run_watch(watch_interval: int = DEFAULT_INTERVAL, account: float = 10000.0,
              risk_pct: float = 1.0, cache_dir: str | None = None,
              alert_missing: bool = True, heartbeat: bool = True,
              status_every: int = 1) -> None:
    """Scan every watch_interval seconds and push setups + periodic status to Telegram."""
    state = _load_state(cache_dir)
    if not state.get("primed"):
        state["primed"] = True
        state["last_signal"] = time.time()
        _save_state(state, cache_dir)
    last_heartbeat = state.get("last_signal", 0)
    cycle = 0
    _log(f"XAU/USD 24/7 scanner started — every {watch_interval}s "
         f"(account {account:,.0f} @ {risk_pct}% risk)")
    while True:
        try:
            cycle += 1
            setups, price, source = _scan_once(account, risk_pct, cache_dir)
            now = time.time()
            if setups:
                for s in setups:
                    sig = _signature(s)
                    last = state["signatures"].get(sig, 0)
                    if now - last >= SAME_SETUP_COOLDOWN:
                        msg = format_setup_message(s, source=source, utc=_utc_now())
                        send_message(msg)
                        state["signatures"][sig] = now
                        _log(f"ALERT {s.direction} {s.strategy} entry {s.entry:,.2f} "
                             f"R:R 1:{s.rr:.2f}")
                state["last_signal"] = now
            elif status_every and cycle % status_every == 0:
                send_message(format_no_setup(price, utc=_utc_now(), source=source))
                state["last_signal"] = now
                _log(f"status sent — no qualifying setup, last {price:,.2f}")
            elif heartbeat and now - last_heartbeat >= HEARTBEAT_EVERY:
                _log(f"still scanning — last {price:,.2f}, no setup")
                last_heartbeat = now
            # prune stale signatures so state never grows unbounded
            cutoff = now - 6 * 3600
            state["signatures"] = {k: v for k, v in state["signatures"].items() if v >= cutoff}
            _save_state(state, cache_dir)
        except KeyboardInterrupt:
            _log("stopped by user")
            return
        except Exception as exc:
            _log(f"error: {exc}")
        try:
            time.sleep(watch_interval)
        except KeyboardInterrupt:
            _log("stopped by user")
            return