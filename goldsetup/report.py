from __future__ import annotations

import json

from .analysis import Analysis, analysis_json
from .data import Candle
from .setup import Setup

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
GRAY = "\033[90m"


def _use_color(no_color: bool, stream) -> bool:
    if no_color:
        return False
    try:
        return stream.isatty()
    except Exception:
        return False


def _c(color: str, text: str, on: bool) -> str:
    return f"{color}{text}{RESET}" if on else text


def _latest_change(candles: list[Candle]) -> tuple[float | None, float | None]:
    if len(candles) < 2:
        return None, None
    last = candles[-1].close
    prev = candles[-2].close
    chg = last - prev
    pct = (chg / prev * 100.0) if prev else None
    return chg, pct


def _dir_long_short(direction: str) -> str:
    return "LONG" if direction == "BUY" else "SHORT"


def _timeframe_label(strategy: str) -> str:
    if "FVG" in strategy:
        return "5m / 1H Macro + 15M/1H Liquidity"
    if "Sweep" in strategy or "CHoCH" in strategy:
        return "5m / 15m Confluence"
    return "5m"


def render_report(candles: list[Candle], a: Analysis, setups: list[Setup],
                  interval: str, account: float, risk_pct: float,
                  source: str = "yahoo", no_color: bool = False, stream=None,
                  verbose: bool = False) -> str:
    color = _use_color(no_color, stream)
    lines: list[str] = []

    last = candles[-1]
    chg, pct = _latest_change(candles)
    ts = last.dt.strftime("%H:%M:%S")

    banner = "=" * 50
    lines.append(banner)
    lines.append(f"🚀 XAU/USD SETUP SCANNER REPORT [{ts}]")
    lines.append(banner)

    if not setups:
        lines.append("[*] No qualifying setup meets the strict structural criteria "
                     "right now (R:R floors not satisfied).")
        lines.append("    Snapshot: %s | ADX %s | RSI %s | Last %s | data %s" % (
            a.regime.upper(), f"{a.adx:.0f}" if a.adx is not None else "n/a",
            f"{a.rsi:.0f}" if a.rsi is not None else "n/a", f"{last.close:,.2f}", source))
        lines.append("    Tip: wait for a 5M FVG pullback with RSI reset, or a "
                     "session liquidity sweep + CHoCH during London/NY hours.")
        return "\n".join(lines)

    for i, s in enumerate(setups, 1):
        reason = "; ".join(s.evidence[:3])
        dir_str = _dir_long_short(s.direction)
        lines.append(f"[*] Strategy Matched : {s.strategy}")
        lines.append(f"[*] Direction        : {dir_str}")
        lines.append(f"[*] Timeframe        : {_timeframe_label(s.strategy)}")
        lines.append(f"- Entry Price        : {s.entry:,.2f}")
        lines.append(f"- Stop Loss          : {s.stop:,.2f}")
        lines.append(f"- Take Profit        : {s.take_profit:,.2f}")
        lines.append(f"- Risk-to-Reward     : 1:{s.rr:.2f}")
        lines.append(f"- Reason/Confluence  : {reason}")
        if verbose:
            for e in s.evidence:
                lines.append(f"  * {e}")
            lines.append(f"  * Position {s.position_lots:.3f} lots ({s.position_oz:,.1f} oz) | "
                         f"Risk {s.risk_amount:,.2f} USD | Reward {s.reward_amount:,.2f} USD")
        if i < len(setups):
            lines.append("-" * 50)

    lines.append(banner)
    lines.append(f"Account {account:,.2f} USD @ {risk_pct}% risk/trade | "
                 f"probability is a confluence estimate, not a guarantee | "
                 f"not financial advice")
    return "\n".join(lines)


def render_json(candles: list[Candle], a: Analysis, setups: list[Setup], interval: str,
                account: float, risk_pct: float, source: str = "yahoo") -> str:
    last = candles[-1]
    payload = {
        "symbol": "GC=F",
        "instrument": "XAU/USD",
        "interval": interval,
        "source": source,
        "timestamp": last.timestamp,
        "last": round(last.close, 2),
        "previous_close": round(candles[-2].close, 2) if len(candles) > 1 else None,
        "account": account,
        "risk_pct": risk_pct,
        "analysis": analysis_json(a),
        "strategies_scanned": ["Multi-Timeframe FVG + EMA Pullback",
                               "Session Liquidity Sweep & CHoCH"],
        "setups": [
            {
                "strategy": s.strategy,
                "direction": _dir_long_short(s.direction),
                "timeframe": _timeframe_label(s.strategy),
                "entry": round(s.entry, 2),
                "stop": round(s.stop, 2),
                "take_profit": round(s.take_profit, 2),
                "rr": s.rr,
                "risk_to_reward": f"1:{s.rr:.2f}",
                "probability": s.probability,
                "position_lots": s.position_lots,
                "position_oz": round(s.position_oz, 2),
                "risk_amount": round(s.risk_amount, 2),
                "reward_amount": round(s.reward_amount, 2),
                "evidence": s.evidence,
                "rationale": s.rationale,
            }
            for s in setups
        ],
    }
    return json.dumps(payload, indent=2)