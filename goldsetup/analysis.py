from __future__ import annotations

from dataclasses import dataclass, field

from .data import Candle
from . import indicators as ind

NoneSeries = ind.NoneSeries


@dataclass
class Zone:
    kind: str
    hi: float
    lo: float
    idx: int
    strength: float = 0.5


@dataclass
class Analysis:
    price: float
    atr: float | None
    atr_pct: float | None
    ema: dict[str, float | None]
    sma: dict[str, float | None]
    bb: dict[str, float | None]
    rsi: float | None
    rsi_div: str | None
    macd_hist: float | None
    macd_hist_prev: float | None
    macd_trend: str | None
    stoch_k: float | None
    stoch_d: float | None
    adx: float | None
    di_plus: float | None
    di_minus: float | None
    fib_dir: str | None
    fib: dict[str, float]
    support: list[float]
    resistance: list[float]
    supply: list[Zone]
    demand: list[Zone]
    liquidity_above: list[float]
    liquidity_below: list[float]
    equal_highs: list[float]
    equal_lows: list[float]
    structure: str
    bos: dict | None
    choch: dict | None
    breakout: dict | None
    sweep: dict | None
    fvgs: list[Zone]
    order_blocks: list[Zone]
    regime: str


def _last(series: NoneSeries) -> float | None:
    return series[-1] if series else None


def _prev(series: NoneSeries) -> float | None:
    return series[-2] if len(series) > 1 else None


def _swing_points(candles: list[Candle], window: int = 3) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    n = len(candles)
    for i in range(window, n - window):
        mid = candles[i]
        prev = candles[i - window: i]
        nxt = candles[i + 1: i + window + 1]
        if mid.high >= max(c.high for c in prev) and mid.high >= max(c.high for c in nxt):
            highs.append((i, mid.high))
        if mid.low <= min(c.low for c in prev) and mid.low <= min(c.low for c in nxt):
            lows.append((i, mid.low))
    return highs, lows


def _fib_levels(candles: list[Candle], swing_highs: list[tuple[int, float]],
                swing_lows: list[tuple[int, float]]) -> tuple[str | None, dict[str, float]]:
    if not swing_highs or not swing_lows:
        return None, {}
    h = swing_highs[-1]
    l = swing_lows[-1]
    base, extreme, direction = None, None, None
    if h[0] > l[0]:
        base, extreme, direction = h[1], l[1], "bearish"
    else:
        base, extreme, direction = l[1], h[1], "bullish"
    rng = abs(extreme - base)
    if rng <= 0:
        return None, {}
    ratios = (0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618)
    levels = {}
    for r in ratios:
        levels[str(r)] = base + rng * r
    return direction, levels


def _cluster_levels(prices: list[float], tolerance: float) -> list[float]:
    if not prices:
        return []
    levels: list[float] = []
    for p in sorted(prices):
        if levels and abs(p - levels[-1]) <= tolerance:
            levels[-1] = (levels[-1] + p) / 2.0
        else:
            levels.append(p)
    return levels


def _supply_demand(candles: list[Candle], atr: float) -> tuple[list[Zone], list[Zone]]:
    n = len(candles)
    supply: list[Zone] = []
    demand: list[Zone] = []
    if n < 5 or atr is None:
        return supply, demand
    for i in range(3, n - 1):
        move = candles[i].close - candles[i - 1].close
        if abs(move) >= 1.5 * atr:
            base = candles[i - 1]
            if move > 0:
                zone = Zone("demand", max(base.high, base.close), min(base.low, base.open),
                            i - 1, min(abs(move) / (3 * atr), 1.0))
                if zone.lo < candles[i].close:
                    demand.append(zone)
            else:
                zone = Zone("supply", max(base.high, base.open), min(base.low, base.close),
                            i - 1, min(abs(move) / (3 * atr), 1.0))
                if zone.hi > candles[i].close:
                    supply.append(zone)
    return supply, demand


def _fvgs(candles: list[Candle]) -> list[Zone]:
    fvgs: list[Zone] = []
    for i in range(2, len(candles)):
        a, b, c = candles[i - 2], candles[i - 1], candles[i]
        if c.low > a.high:  # bullish FVG
            fvgs.append(Zone("fvg", c.low, a.high, i - 1))
        elif c.high < a.low:  # bearish FVG
            fvgs.append(Zone("fvg", a.low, c.high, i - 1))
    return fvgs


def unfilled_fvgs(candles: list[Candle]) -> list[Zone]:
    """Active (unfilled) fair value gaps, newest first. A gap is filled once
    price trades back through it (bullish: low pierces the lower edge;
    bearish: high pierces the upper edge)."""
    out: list[Zone] = []
    for i in range(2, len(candles)):
        a, c = candles[i - 2], candles[i]
        if c.low > a.high:  # bullish gap
            lo, hi = a.high, c.low
            if candles[-1].close > lo and not any(x.low <= lo for x in candles[i + 1:]):
                out.append(Zone("fvg-bullish", hi, lo, i - 1))
        elif c.high < a.low:  # bearish gap
            lo, hi = c.high, a.low
            if candles[-1].close < hi and not any(x.high >= hi for x in candles[i + 1:]):
                out.append(Zone("fvg-bearish", hi, lo, i - 1))
    return out


def session_range(candles: list[Candle]) -> tuple[float, float] | None:
    """(session_high, session_low) of the current UTC trading day."""
    day = candles[-1].dt.date()
    todays = [c for c in candles if c.dt.date() == day]
    if not todays:
        return None
    return max(c.high for c in todays), min(c.low for c in todays)


def _order_blocks(candles: list[Candle]) -> list[Zone]:
    blocks: list[Zone] = []
    for i in range(2, len(candles) - 1):
        a, b, c = candles[i - 2], candles[i - 1], candles[i]
        if a.close < a.open and b.close < b.open and c.close > c.open:  # bullish OB before up move
            blocks.append(Zone("order_block", max(b.high, b.open), min(b.low, b.close), i - 1))
        if a.close > a.open and b.close > b.open and c.close < c.open:  # bearish OB before down move
            blocks.append(Zone("order_block", max(b.high, b.open), min(b.low, b.close), i - 1))
    return blocks


def _rsi_divergence(candles: list[Candle], rsi_series: NoneSeries,
                    highs: list[tuple[int, float]], lows: list[tuple[int, float]]) -> str | None:
    if len(highs) >= 2 and len(lows) >= 2:
        h1, h2 = highs[-2][1], highs[-1][1]
        r1, r2 = rsi_series[highs[-2][0]], rsi_series[highs[-1][0]]
        if None not in (r1, r2) and h2 > h1 and r2 < r1:
            return "bearish"
        l1, l2 = lows[-2][1], lows[-1][1]
        r1b, r2b = rsi_series[lows[-2][0]], rsi_series[lows[-1][0]]
        if None not in (r1b, r2b) and l2 < l1 and r2b > r1b:
            return "bullish"
    return None


def _market_structure(candles: list[Candle], highs: list[tuple[int, float]],
                      lows: list[tuple[int, float]]) -> tuple[str, dict | None, dict | None]:
    if len(highs) < 2 or len(lows) < 2:
        return "neutral", None, None
    h1, h2 = highs[-2], highs[-1]
    l1, l2 = lows[-2], lows[-1]
    state = "neutral"
    if h2[1] > h1[1] and l2[1] > l1[1]:
        state = "bullish"
    elif h2[1] < h1[1] and l2[1] < l1[1]:
        state = "bearish"

    price = candles[-1].close
    recent_high = max(h[1] for h in highs[-3:]) if highs else None
    recent_low = min(l[1] for l in lows[-3:]) if lows else None
    bos = choch = None
    if recent_high is not None and price > recent_high:
        if state == "bullish":
            bos = {"direction": "BUY", "level": recent_high, "idx": highs[-1][0]}
        else:
            choch = {"direction": "BUY", "level": recent_high, "idx": highs[-1][0]}
    if recent_low is not None and price < recent_low:
        if state == "bearish":
            bos = {"direction": "SELL", "level": recent_low, "idx": lows[-1][0]}
        else:
            choch = {"direction": "SELL", "level": recent_low, "idx": lows[-1][0]}
    return state, bos, choch


def _sweep(candles: list[Candle], highs: list[tuple[int, float]],
           lows: list[tuple[int, float]], atr: float | None) -> dict | None:
    if atr is None or len(candles) < 3:
        return None
    cur = candles[-1]
    for target, kind in ((min((l[1] for l in lows), default=None), "bullish"),
                         (max((h[1] for h in highs), default=None), "bearish")):
        if target is None:
            continue
        if kind == "bullish" and cur.low < target and cur.close > target:
            if cur.low <= target - 0.1 * atr:
                return {"direction": kind, "level": target, "idx": len(candles) - 1}
        if kind == "bearish" and cur.high > target and cur.close < target:
            if cur.high >= target + 0.1 * atr:
                return {"direction": kind, "level": target, "idx": len(candles) - 1}
    return None


def _breakout(candles: list[Candle], atr: float | None) -> dict | None:
    n = len(candles)
    if n < 25 or atr is None:
        return None
    window = candles[-21:-1]
    hi = max(c.high for c in window)
    lo = min(c.low for c in window)
    price = candles[-1].close
    atr_series = ind.atr(candles, 14)
    recent = [v for v in atr_series[-40:] if v is not None]
    atr_avg = sum(recent) / len(recent) if recent else atr
    expansion = atr / atr_avg if atr_avg else 1.0
    if price > hi:
        fake = candles[-1].low <= hi
        return {"direction": "BUY", "valid": not fake, "fakeout": fake, "level": hi,
                "expansion": round(expansion, 2)}
    if price < lo:
        fake = candles[-1].high >= lo
        return {"direction": "SELL", "valid": not fake, "fakeout": fake, "level": lo,
                "expansion": round(expansion, 2)}
    return None


def _regime(a: Analysis) -> str:
    adx = a.adx or 0
    bb_w = a.bb.get("width")
    trend_up = a.ema.get("9") and a.ema.get("21") and a.ema.get("50") and \
        a.price > a.ema["9"] > a.ema["21"] > a.ema["50"]
    trend_down = a.ema.get("9") and a.ema.get("21") and a.ema.get("50") and \
        a.price < a.ema["9"] < a.ema["21"] < a.ema["50"]
    if a.breakout and a.breakout["valid"]:
        return "breakout"
    if a.sweep and a.choch:
        return "reversal"
    if adx >= 25 and (trend_up or trend_down):
        return "trend-up" if trend_up else "trend-down"
    if adx < 20 and bb_w is not None and bb_w < 0.08:
        return "range"
    return "volatile"


def analyse(candles: list[Candle]) -> Analysis:
    closes = [c.close for c in candles]
    price = closes[-1]
    atr_series = ind.atr(candles, 14)
    atr = _last(atr_series)
    atr_pct = (atr / price * 100.0) if atr else None

    ema = {p: _last(ind.ema(closes, p)) for p in (9, 21, 50, 200)}
    sma = {p: _last(ind.sma(closes, p)) for p in (20, 50, 200)}
    bb_mid, bb_up, bb_lo = ind.bollinger(closes, 20)
    bb = {"mid": _last(bb_mid), "upper": _last(bb_up), "lower": _last(bb_lo)}
    bw = (bb["upper"] - bb["lower"]) / price if (bb["upper"] and bb["lower"]) else None
    bb["width"] = bw
    rsi_series = ind.rsi(closes, 14)
    rsi = _last(rsi_series)
    macd_line, macd_sig, macd_hist = ind.macd(closes)
    mh, mh_prev = _last(macd_hist), _prev(macd_hist)
    macd_trend = None
    if mh is not None and mh_prev is not None:
        macd_trend = "up" if mh > mh_prev else "down"
    st_k, st_d = ind.stochastic(candles)
    adx, pdi, mdi = ind.adx(candles, 14)

    highs, lows = _swing_points(candles)
    fib_dir, fib = _fib_levels(candles, highs, lows)
    sw_highs = [h[1] for h in highs]
    sw_lows = [l[1] for l in lows]
    tolerance = 0.15 * atr if atr else 1.0
    pivots = ind.classic_pivots(candles) if len(candles) >= 2 else {}
    s_vals = sw_lows + [v for k, v in pivots.items() if k.startswith("S")]
    r_vals = sw_highs + [v for k, v in pivots.items() if k.startswith("R")]
    support = sorted([lv for lv in _cluster_levels(s_vals, tolerance) if lv < price])
    resistance = sorted([lv for lv in _cluster_levels(r_vals, tolerance) if lv > price])

    supply, demand = _supply_demand(candles, atr)
    fvgs = _fvgs(candles)
    order_blocks = _order_blocks(candles)
    structure, bos, choch = _market_structure(candles, highs, lows)
    sweep = _sweep(candles, highs, lows, atr)
    breakout = _breakout(candles, atr)
    rsi_div = _rsi_divergence(candles, rsi_series, highs, lows)

    eq_h, eq_l = [], []
    for i in range(1, len(highs)):
        if abs(highs[i][1] - highs[i - 1][1]) <= tolerance:
            eq_h.append(highs[i][1])
    for i in range(1, len(lows)):
        if abs(lows[i][1] - lows[i - 1][1]) <= tolerance:
            eq_l.append(lows[i][1])

    liquidity_above = sorted(set(sw_highs))
    liquidity_below = sorted(set(sw_lows))

    a = Analysis(
        price=price, atr=atr, atr_pct=atr_pct,
        ema=ema, sma=sma, bb=bb, rsi=rsi, rsi_div=rsi_div,
        macd_hist=mh, macd_hist_prev=mh_prev, macd_trend=macd_trend,
        stoch_k=_last(st_k), stoch_d=_last(st_d),
        adx=_last(adx), di_plus=_last(pdi), di_minus=_last(mdi),
        fib_dir=fib_dir, fib=fib,
        support=support, resistance=resistance,
        supply=supply, demand=demand,
        liquidity_above=liquidity_above, liquidity_below=liquidity_below,
        equal_highs=eq_h, equal_lows=eq_l,
        structure=structure, bos=bos, choch=choch,
        breakout=breakout, sweep=sweep,
        fvgs=fvgs, order_blocks=order_blocks, regime="volatile",
    )
    a.regime = _regime(a)
    return a


def analysis_json(a: Analysis) -> dict:
    return {
        "price": round(a.price, 2),
        "atr": round(a.atr, 2) if a.atr else None,
        "atr_pct": round(a.atr_pct, 3) if a.atr_pct else None,
        "ema": {k: round(v, 2) if v is not None else None for k, v in a.ema.items()},
        "sma": {k: round(v, 2) if v is not None else None for k, v in a.sma.items()},
        "bb": {k: round(v, 2) if v is not None else None for k, v in a.bb.items()},
        "rsi": round(a.rsi, 1) if a.rsi is not None else None,
        "rsi_divergence": a.rsi_div,
        "macd_hist": round(a.macd_hist, 2) if a.macd_hist is not None else None,
        "macd_trend": a.macd_trend,
        "stoch_k": round(a.stoch_k, 1) if a.stoch_k is not None else None,
        "stoch_d": round(a.stoch_d, 1) if a.stoch_d is not None else None,
        "adx": round(a.adx, 1) if a.adx is not None else None,
        "di": {"plus": round(a.di_plus, 1) if a.di_plus is not None else None,
               "minus": round(a.di_minus, 1) if a.di_minus is not None else None},
        "fib_direction": a.fib_dir,
        "fib": {k: round(v, 2) for k, v in a.fib.items()},
        "support": [round(s, 2) for s in a.support[-4:]],
        "resistance": [round(r, 2) for r in a.resistance[:4]],
        "supply_zones": [{"hi": round(z.hi, 2), "lo": round(z.lo, 2)} for z in a.supply[-3:]],
        "demand_zones": [{"hi": round(z.hi, 2), "lo": round(z.lo, 2)} for z in a.demand[-3:]],
        "liquidity_above": [round(v, 2) for v in a.liquidity_above[-3:]],
        "liquidity_below": [round(v, 2) for v in a.liquidity_below[:3]],
        "equal_highs": [round(v, 2) for v in a.equal_highs[-3:]],
        "equal_lows": [round(v, 2) for v in a.equal_lows[:3]],
        "structure": a.structure,
        "bos": a.bos,
        "choch": a.choch,
        "breakout": a.breakout,
        "sweep": a.sweep,
        "fvgs": [{"hi": round(z.hi, 2), "lo": round(z.lo, 2)} for z in a.fvgs[-3:]],
        "order_blocks": [{"hi": round(z.hi, 2), "lo": round(z.lo, 2)} for z in a.order_blocks[-3:]],
        "regime": a.regime,
    }