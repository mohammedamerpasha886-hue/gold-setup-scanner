from __future__ import annotations

from dataclasses import dataclass, field

from .analysis import Analysis, analyse, unfilled_fvgs, session_range
from .data import Candle
from . import indicators as ind
from .setup import Setup, _position_size

# Strategy thresholds
FVG_EMA_MIN_RR = 2.5
SWEEP_MIN_RR = 3.0
OB_DIV_MIN_RR = 2.5
ASIAN_BREAKOUT_MIN_RR = 2.0
ZONE_FLIP_MIN_RR = 2.5
SWEEP_LOOKBACK = 8          # hours used to define the pre-sweep swing (Asian/early session)
LONDON_HOURS = (8, 9)       # 08:00-10:00 UTC
NY_HOURS = (13, 14, 15)     # 13:00-16:00 UTC
ASIAN_BREAKOUT_HOURS = (7, 8, 9)   # London open window UTC
ASIAN_HOUR_CUTOFF = 7              # Asian session = 00:00-06:59 UTC
ZONE_MAX_AGE = 80                  # max bars old for a supply/demand zone to stay fresh
ATR_BUFFER = 0.15


def macro_bias(candles_1h: list[Candle]) -> str | None:
    """1H EMA20 vs EMA50 trend filter. LONG if 20>50, SHORT if 20<50, else None."""
    closes = [c.close for c in candles_1h]
    e20 = ind.ema(closes, 20)[-1]
    e50 = ind.ema(closes, 50)[-1]
    if e20 is None or e50 is None:
        return None
    if e20 > e50:
        return "LONG"
    if e20 < e50:
        return "SHORT"
    return None


def _ema(closes: list[float], period: int) -> float | None:
    return ind.ema(closes, period)[-1]


def _rsi_reset_bullish(rsi_series: list[float | None], window: int = 12) -> bool:
    """RSI must have dipped below 50 during the retracement and crossed back above it
    within the last `window` bars."""
    vals = [r for r in rsi_series if r is not None]
    if not vals:
        return False
    if vals[-1] <= 50:
        return False
    crossed = None
    for i in range(len(vals) - 1, 0, -1):
        below = vals[i - 1] < 50
        above = vals[i] > 50
        if below and above:
            crossed = i
            break
    return crossed is not None and len(vals) - 1 - crossed < window


def _rsi_reset_bearish(rsi_series: list[float | None], window: int = 12) -> bool:
    vals = [r for r in rsi_series if r is not None]
    if not vals:
        return False
    if vals[-1] >= 50:
        return False
    crossed = None
    for i in range(len(vals) - 1, 0, -1):
        above = vals[i - 1] > 50
        below = vals[i] < 50
        if above and below:
            crossed = i
            break
    return crossed is not None and len(vals) - 1 - crossed < window


def _nearest_swing_below(a: Analysis, price: float) -> float | None:
    below = [s for s in a.liquidity_below if s < price]
    return max(below) if below else None


def _nearest_swing_above(a: Analysis, price: float) -> float | None:
    above = [s for s in a.liquidity_above if s > price]
    return min(above) if above else None


def _fvg_pullback_tested(candles: list[Candle], zone, direction: str, ema20: float | None) -> bool:
    price = candles[-1].close
    last = candles[-1]
    if ema20 is None:
        return False
    if direction == "LONG":
        tapped = last.low <= zone.hi and last.low >= zone.lo * 0.998
        at_ema = price <= ema20 * 1.002
        return tapped and at_ema
    tapped = last.high >= zone.lo and last.high <= zone.hi * 1.002
    at_ema = price >= ema20 * 0.998
    return tapped and at_ema


def strategy_fvg_ema_pullback(candles_5m: list[Candle], candles_1h: list[Candle],
                              candles_15m: list[Candle], balance: float = 10000.0,
                              risk_pct: float = 1.0) -> Setup | None:
    """STRATEGY 1: Multi-Timeframe FVG + EMA Pullback (Continuation Scalp)."""
    bias = macro_bias(candles_1h)
    if bias is None:
        return None
    direction = "LONG" if bias == "LONG" else "SHORT"

    a5 = analyse(candles_5m)
    closes5 = [c.close for c in candles_5m]
    ema20 = _ema(closes5, 20)
    fvg = None
    wanted_kind = "fvg-bullish" if direction == "LONG" else "fvg-bearish"
    for z in unfilled_fvgs(candles_5m):
        if z.kind != wanted_kind:
            continue
        if not _fvg_pullback_tested(candles_5m, z, direction, ema20):
            continue
        fvg = z
        break
    if fvg is None:
        return None

    rsi_series = ind.rsi(closes5, 14)
    if direction == "LONG":
        if not _rsi_reset_bullish(rsi_series):
            return None
    else:
        if not _rsi_reset_bearish(rsi_series):
            return None

    atr = a5.atr or (candles_5m[-1].high - candles_5m[-1].low)
    price = candles_5m[-1].close

    # Structural SL: below the local FVG/OB zone swing (swing low for LONG, swing high for SHORT)
    if direction == "LONG":
        swing_low = _nearest_swing_below(a5, price) or (fvg.lo - atr)
        sl = min(fvg.lo, swing_low) - ATR_BUFFER * atr
    else:
        swing_high = _nearest_swing_above(a5, price) or (fvg.hi + atr)
        sl = max(fvg.hi, swing_high) + ATR_BUFFER * atr
    risk = abs(price - sl)
    if risk <= 0:
        return None

    # Structural TP: nearest 15M/1H liquidity high/low
    a15 = analyse(candles_15m)
    a1h = analyse(candles_1h)
    if direction == "LONG":
        tp_cands = [l for l in a15.liquidity_above + a1h.liquidity_above if l > price]
        tp = min(tp_cands) if tp_cands else None
        if tp is None or tp - price < FVG_EMA_MIN_RR * risk:
            return None
    else:
        tp_cands = [l for l in a15.liquidity_below + a1h.liquidity_below if l < price]
        tp = max(tp_cands) if tp_cands else None
        if tp is None or price - tp < FVG_EMA_MIN_RR * risk:
            return None

    reward = abs(tp - price)
    rr = reward / risk
    sizing = _position_size(price, sl, balance, risk_pct)
    reason = (
        f"1H EMA20>{'50' if direction == 'LONG' else '20<50'} trend {direction.lower()}; "
        f"5M price tapped unfilled FVG {fvg.lo:.2f}-{fvg.hi:.2f} at 5M EMA20 {ema20:.2f}; "
        f"RSI reset through 50; SL below zone swing {sl:.2f}, TP at structural liquidity {tp:.2f}"
    )
    return Setup(
        direction=direction,
        confidence=round(min(0.55 + 0.05 * min(rr / FVG_EMA_MIN_RR, 2.0), 0.8), 3),
        entry=price,
        stop=sl,
        take_profit=tp,
        rr=round(rr, 2),
        strategy="Multi-Timeframe FVG + EMA Pullback",
        probability=round(min(0.55 + 0.05 * min(rr / FVG_EMA_MIN_RR, 2.0), 0.8), 3),
        evidence=[
            f"1H macro filter: EMA20={_ema([c.close for c in candles_1h], 20):.2f} vs EMA50={_ema([c.close for c in candles_1h], 50):.2f}",
            f"5M unfilled {fvg.kind} at {fvg.lo:.2f}-{fvg.hi:.2f}",
            f"Pullback tapped 5M EMA20 {ema20:.2f} with RSI re-crossing 50",
            f"SL {sl:.2f} below zone swing; TP {tp:.2f} at 15M/1H liquidity",
        ],
        rationale=[
            f"{direction} via {('Multi-Timeframe FVG + EMA Pullback')}",
            f"Technical probability {0.55:.0%} (confluence estimate, not a guarantee)",
            f"Stop {sl:.2f}  |  Target {tp:.2f}  |  R:R 1:{rr:.2f}",
            f"Risk {sizing['risk_amount']:.2f} USD at {risk_pct}% of {balance:,.2f} balance",
        ],
        position_oz=round(sizing["position_oz"], 2),
        position_lots=round(sizing["position_lots"], 3),
        risk_amount=round(sizing["risk_amount"], 2),
        reward_amount=round(reward * sizing["position_oz"], 2),
        confirmed=True,
        confirm_bias=direction,
    )


def _in_session(candles: list[Candle]) -> bool:
    hour = candles[-1].dt.hour
    return hour in LONDON_HOURS or hour in NY_HOURS


def _session_swing(candles: list[Candle], lookback_hours: int) -> tuple[float | None, float | None]:
    """Prior (pre-last-bar) swing high/low within the lookback window."""
    last_ts = candles[-1].timestamp
    window = [c for c in candles if last_ts - c.timestamp <= lookback_hours * 3600 and c is not candles[-1]]
    if not window:
        return None, None
    return max(c.high for c in window), min(c.low for c in window)


def _sweep_on_last_bar(candles: list[Candle]) -> dict | None:
    """Wick spike beyond the prior session swing with a close back inside (stop hunt)."""
    last = candles[-1]
    s_hi, s_lo = _session_swing(candles, SWEEP_LOOKBACK)
    if s_hi is not None and last.high > s_hi and last.close < s_hi:
        return {"direction": "SHORT", "level": s_hi, "extreme": last.high}
    if s_lo is not None and last.low < s_lo and last.close > s_lo:
        return {"direction": "LONG", "level": s_lo, "extreme": last.low}
    return None


def _choch_after_sweep(candles: list[Candle], sweep: dict) -> bool:
    """Sharp candle closing beyond the nearest internal micro-structure, opposite the sweep."""
    last = candles[-1]
    if sweep["direction"] == "LONG":  # sell-side sweep -> bullish CHoCH
        prior = candles[-3:-1]
        micro = min(c.high for c in prior) if prior else None
        return micro is not None and last.close > micro and (last.close - last.open) > 0
    prior = candles[-3:-1]
    micro = max(c.low for c in prior) if prior else None
    return micro is not None and last.close < micro and (last.close - last.open) < 0


def strategy_session_sweep_choch(candles_5m: list[Candle], candles_15m: list[Candle],
                                 balance: float = 10000.0, risk_pct: float = 1.0) -> Setup | None:
    """STRATEGY 2: London/NY Session Liquidity Sweep & CHoCH (Reversal Scalp)."""
    if not _in_session(candles_5m):
        return None

    sweep = _sweep_on_last_bar(candles_5m)
    if sweep is None:
        return None
    if not _choch_after_sweep(candles_5m, sweep):
        return None

    a5 = analyse(candles_5m)
    atr = a5.atr or (candles_5m[-1].high - candles_5m[-1].low)
    last = candles_5m[-1]
    price = last.close

    # Entry: retracement back into the discount (LONG) / premium (SHORT) zone of the breakout candle
    if sweep["direction"] == "LONG":
        entry = last.low + 0.5 * (last.high - last.low)      # midpoint of sweep candle
        sl = sweep["extreme"] - ATR_BUFFER * atr              # beyond the sweep wick tip
    else:
        entry = last.low + 0.5 * (last.high - last.low)
        sl = sweep["extreme"] + ATR_BUFFER * atr
    if (sweep["direction"] == "LONG" and entry <= sl) or (sweep["direction"] == "SHORT" and entry >= sl):
        return None
    risk = abs(entry - sl)
    if risk <= 0:
        return None

    # TP: opposing side of the intraday session range; enforce 1:3
    srange = session_range(candles_5m)
    if srange is None:
        return None
    s_hi, s_lo = srange
    if sweep["direction"] == "LONG":
        tp = s_hi
        if tp is None or tp - entry < SWEEP_MIN_RR * risk:
            return None
    else:
        tp = s_lo
        if tp is None or entry - tp < SWEEP_MIN_RR * risk:
            return None

    # 15M confluence check for the report ("5m / 15m Confluence")
    a15 = analyse(candles_15m)
    timeframe = "5m / 15m Confluence" if a15.structure == (("bullish" if sweep["direction"] == "LONG" else "bearish")) else "5m"

    reward = abs(tp - entry)
    rr = reward / risk
    sizing = _position_size(entry, sl, balance, risk_pct)
    reason = (
        f"{'Sell-side' if sweep['direction'] == 'LONG' else 'Buy-side'} liquidity sweep at {sweep['level']:.2f} "
        f"(wick to {sweep['extreme']:.2f}) in {'London/NY' if candles_5m[-1].dt.hour in LONDON_HOURS else 'NY'} session; "
        f"CHoCH close beyond micro-structure; retracement entry into {'discount' if sweep['direction'] == 'LONG' else 'premium'}; "
        f"TP {tp:.2f} at opposite session range edge"
    )
    return Setup(
        direction=sweep["direction"],
        confidence=round(min(0.55 + 0.05 * min(rr / SWEEP_MIN_RR, 2.0), 0.8), 3),
        entry=entry,
        stop=sl,
        take_profit=tp,
        rr=round(rr, 2),
        strategy="Session Liquidity Sweep & CHoCH",
        probability=round(min(0.55 + 0.05 * min(rr / SWEEP_MIN_RR, 2.0), 0.8), 3),
        evidence=[
            f"Session filter active (UTC {candles_5m[-1].dt.strftime('%H:%M')})",
            f"{'Sell-side' if sweep['direction'] == 'LONG' else 'Buy-side'} liquidity sweep of {sweep['level']:.2f} (extreme {sweep['extreme']:.2f})",
            "CHoCH: sharp close through nearest internal micro-structure",
            f"Entry at {'discount' if sweep['direction'] == 'LONG' else 'premium'} retracement of the breakout candle",
            f"SL {sl:.2f} beyond sweep wick tip; TP {tp:.2f} at opposite session edge",
        ],
        rationale=[
            f"{sweep['direction']} via Session Liquidity Sweep & CHoCH",
            f"Technical probability {0.55:.0%} (confluence estimate, not a guarantee)",
            f"Stop {sl:.2f}  |  Target {tp:.2f}  |  R:R 1:{rr:.2f}",
            f"Risk {sizing['risk_amount']:.2f} USD at {risk_pct}% of {balance:,.2f} balance",
        ],
        position_oz=round(sizing["position_oz"], 2),
        position_lots=round(sizing["position_lots"], 3),
        risk_amount=round(sizing["risk_amount"], 2),
        reward_amount=round(reward * sizing["position_oz"], 2),
        confirmed=True,
        confirm_bias=sweep["direction"],
    )


def _assemble(direction: str, entry: float, sl: float, tp: float, strategy: str,
              reason: str, evidence: list[str], rr: float, floor: float,
              balance: float, risk_pct: float) -> Setup:
    sizing = _position_size(entry, sl, balance, risk_pct)
    prob = round(min(0.55 + 0.05 * min(rr / floor, 2.0), 0.8), 3)
    return Setup(
        direction=direction,
        confidence=prob,
        entry=entry,
        stop=sl,
        take_profit=tp,
        rr=round(rr, 2),
        strategy=strategy,
        probability=prob,
        evidence=evidence,
        rationale=[
            f"{direction} via {strategy}",
            "Technical probability ~55% (confluence estimate, not a guarantee)",
            f"Stop {sl:.2f}  |  Target {tp:.2f}  |  R:R 1:{rr:.2f}",
            f"Risk {sizing['risk_amount']:.2f} USD at {risk_pct}% of {balance:,.2f} balance",
        ],
        position_oz=round(sizing["position_oz"], 2),
        position_lots=round(sizing["position_lots"], 3),
        risk_amount=round(sizing["risk_amount"], 2),
        reward_amount=round(abs(tp - entry) * sizing["position_oz"], 2),
        confirmed=True,
        confirm_bias=direction,
    )


def _nearest_liquidity_target(a15: Analysis, a1h: Analysis, direction: str,
                              price: float) -> float | None:
    if direction == "LONG":
        cands = [l for l in a15.liquidity_above + a1h.liquidity_above if l > price]
        return min(cands) if cands else None
    cands = [l for l in a15.liquidity_below + a1h.liquidity_below if l < price]
    return max(cands) if cands else None


def strategy_order_block_rsi_divergence(candles_5m: list[Candle], candles_15m: list[Candle],
                                        candles_1h: list[Candle], balance: float = 10000.0,
                                        risk_pct: float = 1.0) -> Setup | None:
    """STRATEGY 3: Order Block Retest + RSI Divergence (Reversal Scalp)."""
    a5 = analyse(candles_5m)
    if a5.rsi_div not in ("bullish", "bearish"):
        return None
    direction = "LONG" if a5.rsi_div == "bullish" else "SHORT"
    if direction == "LONG" and a5.structure == "bearish":
        return None
    if direction == "SHORT" and a5.structure == "bullish":
        return None

    last = candles_5m[-1]
    price = last.close
    atr = a5.atr or (last.high - last.low)
    ob = None
    for z in a5.order_blocks:
        if len(candles_5m) - z.idx >= 120:
            continue
        if direction == "LONG":
            touched = last.low <= z.hi and last.low >= z.lo * 0.998 and price >= z.lo
            near = price - z.lo <= 2.5 * atr
        else:
            touched = last.high >= z.lo and last.high <= z.hi * 1.002 and price <= z.hi
            near = z.hi - price <= 2.5 * atr
        if touched and near:
            ob = z
            break
    if ob is None:
        return None

    if direction == "LONG":
        swing_low = _nearest_swing_below(a5, price)
        sl = (min(ob.lo, swing_low) if swing_low else ob.lo) - ATR_BUFFER * atr
    else:
        swing_high = _nearest_swing_above(a5, price)
        sl = (max(ob.hi, swing_high) if swing_high else ob.hi) + ATR_BUFFER * atr
    risk = abs(price - sl)
    if risk <= 0:
        return None

    a15 = analyse(candles_15m)
    a1h = analyse(candles_1h)
    tp = _nearest_liquidity_target(a15, a1h, direction, price)
    if tp is None or abs(tp - price) < OB_DIV_MIN_RR * risk:
        return None

    reward = abs(tp - price)
    rr = reward / risk
    reason = (
        f"5M RSI divergence ({a5.rsi_div}) with {a5.structure} structure; "
        f"price retesting order block {ob.lo:.2f}-{ob.hi:.2f}; "
        f"SL beyond zone {sl:.2f}, TP {tp:.2f} at 15M/1H liquidity"
    )
    return _assemble(direction, price, sl, tp, "Order Block Retest + RSI Divergence",
                     reason, [
                         f"5M RSI divergence: {a5.rsi_div}",
                         f"Structure: {a5.structure}" + (f", CHoCH {a5.choch['direction']}" if a5.choch else ""),
                         f"Retesting order block {ob.lo:.2f}-{ob.hi:.2f}",
                         f"SL {sl:.2f} beyond zone; TP {tp:.2f} at 15M/1H liquidity",
                     ], rr, OB_DIV_MIN_RR, balance, risk_pct)


def _asian_range(candles: list[Candle]) -> tuple[float, float] | None:
    """(high, low) of the current UTC day's Asian session (00:00-06:59)."""
    day = candles[-1].dt.date()
    asian = [c for c in candles if c.dt.date() == day and c.dt.hour < ASIAN_HOUR_CUTOFF]
    if not asian:
        return None
    return max(c.high for c in asian), min(c.low for c in asian)


def strategy_asian_range_breakout(candles_5m: list[Candle], candles_15m: list[Candle],
                                  candles_1h: list[Candle], balance: float = 10000.0,
                                  risk_pct: float = 1.0) -> Setup | None:
    """STRATEGY 4: Asian Range Breakout on the London Open (Momentum Scalp)."""
    last = candles_5m[-1]
    if last.dt.hour not in ASIAN_BREAKOUT_HOURS:
        return None
    ar = _asian_range(candles_5m)
    if ar is None:
        return None
    a_hi, a_lo = ar
    price = last.close
    if price > a_hi:
        direction = "LONG"
    elif price < a_lo:
        direction = "SHORT"
    else:
        return None

    a5 = analyse(candles_5m)
    if a5.adx is None or a5.adx < 15:
        return None
    if direction == "LONG" and (a5.rsi is not None and a5.rsi < 50):
        return None
    if direction == "SHORT" and (a5.rsi is not None and a5.rsi > 50):
        return None

    atr = a5.atr or (last.high - last.low)
    wanted_kind = "fvg-bullish" if direction == "LONG" else "fvg-bearish"
    fvg = None
    for z in unfilled_fvgs(candles_5m):
        if z.kind != wanted_kind:
            continue
        if direction == "LONG":
            inside = last.low <= z.hi and last.low >= z.lo * 0.998
        else:
            inside = last.high >= z.lo and last.high <= z.hi * 1.002
        if inside:
            fvg = z
            break
    if fvg is None:
        return None

    range_w = a_hi - a_lo
    if direction == "LONG":
        entry, sl = price, a_hi - ATR_BUFFER * atr
        tp = a_hi + range_w
    else:
        entry, sl = price, a_lo + ATR_BUFFER * atr
        tp = a_lo - range_w
    if (direction == "LONG" and entry <= sl) or (direction == "SHORT" and entry >= sl):
        return None
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    if risk <= 0 or reward / risk < ASIAN_BREAKOUT_MIN_RR:
        return None
    rr = reward / risk
    reason = (
        f"London open breakout of the Asian range {a_lo:.2f}-{a_hi:.2f} "
        f"(width {range_w:.2f}); retest entry into unfilled FVG {fvg.lo:.2f}-{fvg.hi:.2f}; "
        f"ADX {a5.adx:.0f} with MACD {a5.macd_trend}; TP {tp:.2f} = measured move"
    )
    return _assemble(direction, entry, sl, tp, "Asian Range Breakout (London Open)",
                     reason, [
                         f"Session: London open (UTC {last.dt.strftime('%H:%M')})",
                         f"Asian range {a_lo:.2f}-{a_hi:.2f} broken {direction.lower()}",
                         f"Retest of unfilled FVG {fvg.lo:.2f}-{fvg.hi:.2f}",
                         f"ADX {a5.adx:.0f}, RSI {(f'{a5.rsi:.0f}' if a5.rsi is not None else 'n/a')}; "
                         f"TP {tp:.2f} measured move",
                     ], rr, ASIAN_BREAKOUT_MIN_RR, balance, risk_pct)


def _zone_flip_retest(candles: list[Candle], zone, direction: str) -> bool:
    last = candles[-1]
    if direction == "LONG":
        return last.low <= zone.hi and last.low >= zone.lo * 0.998 and last.close > zone.lo
    return last.high >= zone.lo and last.high <= zone.hi * 1.002 and last.close < zone.hi


def strategy_supply_demand_zone_flip(candles_5m: list[Candle], candles_15m: list[Candle],
                                     candles_1h: list[Candle], balance: float = 10000.0,
                                     risk_pct: float = 1.0) -> Setup | None:
    """STRATEGY 5: Broken Supply/Demand Zone Flip + Retest (Continuation Scalp)."""
    a5 = analyse(candles_5m)
    last = candles_5m[-1]
    price = last.close
    atr = a5.atr or (last.high - last.low)
    n = len(candles_5m)
    zones: list[tuple] = []
    zones += [(z, "LONG") for z in a5.demand if z.strength >= 0.35 and n - z.idx < ZONE_MAX_AGE]
    zones += [(z, "SHORT") for z in a5.supply if z.strength >= 0.35 and n - z.idx < ZONE_MAX_AGE]
    for zone, direction in zones:
        if not _zone_flip_retest(candles_5m, zone, direction):
            continue
        if direction == "LONG":
            if a5.rsi is not None and a5.rsi < 40:
                continue
            if not (a5.structure == "bullish" or a5.rsi_div == "bullish"):
                continue
        else:
            if a5.rsi is not None and a5.rsi > 60:
                continue
            if not (a5.structure == "bearish" or a5.rsi_div == "bearish"):
                continue
        if direction == "LONG":
            swing_low = _nearest_swing_below(a5, price)
            sl = (min(zone.lo, swing_low) if swing_low else zone.lo) - ATR_BUFFER * atr
        else:
            swing_high = _nearest_swing_above(a5, price)
            sl = (max(zone.hi, swing_high) if swing_high else zone.hi) + ATR_BUFFER * atr
        risk = abs(price - sl)
        if risk <= 0:
            continue
        a15 = analyse(candles_15m)
        a1h = analyse(candles_1h)
        tp = _nearest_liquidity_target(a15, a1h, direction, price)
        if tp is None or abs(tp - price) < ZONE_FLIP_MIN_RR * risk:
            continue
        reward = abs(tp - price)
        rr = reward / risk
        reason = (
            f"{direction.lower()} retest of flipped {'demand' if direction == 'LONG' else 'supply'} "
            f"zone {zone.lo:.2f}-{zone.hi:.2f} (strength {zone.strength:.2f}); "
            f"SL beyond zone {sl:.2f}, TP {tp:.2f} at 15M/1H liquidity"
        )
        return _assemble(direction, price, sl, tp,
                         "Supply/Demand Zone Flip + Retest",
                         reason, [
                             f"Flipped {'demand' if direction == 'LONG' else 'supply'} zone {zone.lo:.2f}-{zone.hi:.2f}",
                             f"Retest with RSI {(f'{a5.rsi:.1f}' if a5.rsi is not None else 'n/a')} / "
                             f"divergence {a5.rsi_div or 'none'} / structure {a5.structure}",
                             f"SL {sl:.2f} beyond zone; TP {tp:.2f} at 15M/1H liquidity",
                         ], rr, ZONE_FLIP_MIN_RR, balance, risk_pct)
    return None


def scan(candles_5m: list[Candle], candles_1h: list[Candle], candles_15m: list[Candle],
         balance: float = 10000.0, risk_pct: float = 1.0) -> list[Setup]:
    """Run all strategies. Results strictly respect their R:R floors."""
    setups: list[Setup] = []
    strategies = (
        lambda: strategy_fvg_ema_pullback(candles_5m, candles_1h, candles_15m, balance, risk_pct),
        lambda: strategy_session_sweep_choch(candles_5m, candles_15m, balance, risk_pct),
        lambda: strategy_order_block_rsi_divergence(candles_5m, candles_15m, candles_1h, balance, risk_pct),
        lambda: strategy_asian_range_breakout(candles_5m, candles_15m, candles_1h, balance, risk_pct),
        lambda: strategy_supply_demand_zone_flip(candles_5m, candles_15m, candles_1h, balance, risk_pct),
    )
    for fn in strategies:
        try:
            s = fn()
            if s is not None:
                setups.append(s)
        except Exception:
            pass
    return setups