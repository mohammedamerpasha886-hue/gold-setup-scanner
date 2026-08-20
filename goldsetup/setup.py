from __future__ import annotations

from dataclasses import dataclass, field

from .data import Candle

OZ_PER_LOT = 100.0
ATR_STOP_MULT = 1.5
ATR_TP_MULT = 3.0
DIR = {"BUY": 1.0, "SELL": -1.0, "NEUTRAL": 0.0}


@dataclass
class Setup:
    direction: str
    confidence: float
    entry: float
    stop: float
    take_profit: float
    rr: float
    rationale: list[str] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)
    position_oz: float = 0.0
    position_lots: float = 0.0
    risk_amount: float = 0.0
    reward_amount: float = 0.0
    score_breakdown: dict[str, float] = field(default_factory=dict)
    confirmed: bool = True
    confirm_bias: str = "NEUTRAL"
    strategy: str = ""
    probability: float = 0.0
    evidence: list[str] = field(default_factory=list)


def _nearest_support(ctx: Context, price: float) -> float | None:
    candidates = [s for s in ctx.swing_lows if s < price]
    candidates.extend(v for k, v in ctx.pivots.items() if k.startswith("S") and v < price)
    if not candidates:
        return None
    return max(candidates)


def _nearest_resistance(ctx: Context, price: float) -> float | None:
    candidates = [s for s in ctx.swing_highs if s > price]
    candidates.extend(v for k, v in ctx.pivots.items() if k.startswith("R") and v > price)
    if not candidates:
        return None
    return min(candidates)


def _compute_stop(ctx: Context, direction: str, entry: float, atr_val: float) -> tuple[float, str]:
    if direction == "BUY":
        atr_stop = entry - ATR_STOP_MULT * atr_val
        support = _nearest_support(ctx, entry)
        if support is not None:
            s_level_stop = support - 0.1 * atr_val
            stop = max(atr_stop, s_level_stop)
            origin = "nearest support" if stop == s_level_stop else "ATR"
        else:
            stop = atr_stop
            origin = "ATR"
    else:
        atr_stop = entry + ATR_STOP_MULT * atr_val
        resistance = _nearest_resistance(ctx, entry)
        if resistance is not None:
            r_level_stop = resistance + 0.1 * atr_val
            stop = min(atr_stop, r_level_stop)
            origin = "nearest resistance" if stop == r_level_stop else "ATR"
        else:
            stop = atr_stop
            origin = "ATR"
    return stop, origin


def _compute_tp(ctx: Context, direction: str, entry: float, stop: float, atr_val: float) -> tuple[float, str]:
    risk = abs(entry - stop)
    atr_tp = entry + DIR[direction] * ATR_TP_MULT * atr_val
    if direction == "BUY":
        resistance = _nearest_resistance(ctx, entry)
        if resistance is not None and resistance > entry:
            level_tp = resistance
            if level_tp - entry >= risk:
                return level_tp, "resistance level"
    else:
        support = _nearest_support(ctx, entry)
        if support is not None and support < entry:
            level_tp = support
            if entry - level_tp >= risk:
                return level_tp, "support level"
    return atr_tp, f"{ATR_TP_MULT}x ATR"


def _position_size(entry: float, stop: float, balance: float, risk_pct: float) -> dict[str, float]:
    risk_amount = balance * (risk_pct / 100.0)
    risk_per_oz = abs(entry - stop)
    oz = risk_amount / risk_per_oz if risk_per_oz > 0 else 0.0
    lots = oz / OZ_PER_LOT
    return {"position_oz": oz, "position_lots": lots, "risk_amount": risk_amount}


def _position_size(entry: float, stop: float, balance: float, risk_pct: float) -> dict[str, float]:
    risk_amount = balance * (risk_pct / 100.0)
    risk_per_oz = abs(entry - stop)
    oz = risk_amount / risk_per_oz if risk_per_oz > 0 else 0.0
    lots = oz / OZ_PER_LOT
    return {"position_oz": oz, "position_lots": lots, "risk_amount": risk_amount}