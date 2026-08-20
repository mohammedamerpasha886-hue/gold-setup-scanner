from __future__ import annotations

import math

from .data import Candle

NoneSeries = list[float | None]


def sma(values: list[float], period: int) -> NoneSeries:
    out: NoneSeries = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    running = sum(values[:period])
    out[period - 1] = running / period
    for i in range(period, len(values)):
        running += values[i] - values[i - period]
        out[i] = running / period
    return out


def ema(values: list[float], period: int) -> NoneSeries:
    out: NoneSeries = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    k = 2.0 / (period + 1.0)
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    for i in range(period, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1.0 - k)
    return out


def _wilder_rma(values: list[float], period: int) -> NoneSeries:
    out: NoneSeries = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    for i in range(period, len(values)):
        out[i] = (out[i - 1] * (period - 1) + values[i]) / period
    return out


def rsi(closes: list[float], period: int = 14) -> NoneSeries:
    out: NoneSeries = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = _wilder_rma(gains, period)
    avg_loss = _wilder_rma(losses, period)
    for i in range(period, len(gains) + 1):
        g = avg_gain[i - 1]
        l = avg_loss[i - 1]
        if l == 0.0:
            out[i] = 100.0
        else:
            rs = g / l
            out[i] = 100.0 - 100.0 / (1.0 + rs)
    return out


def macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    line: NoneSeries = [None] * len(closes)
    for i in range(len(closes)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            line[i] = ema_fast[i] - ema_slow[i]
    valid = [v for v in line if v is not None]
    sig_series = ema(valid, signal)
    sig: NoneSeries = [None] * len(closes)
    sig_idx = len(closes) - len(valid)
    for j, v in enumerate(sig_series):
        if v is not None:
            sig[sig_idx + j] = v
    hist: NoneSeries = [None] * len(closes)
    for i in range(len(closes)):
        if line[i] is not None and sig[i] is not None:
            hist[i] = line[i] - sig[i]
    return line, sig, hist


def atr(candles: list[Candle], period: int = 14) -> NoneSeries:
    out: NoneSeries = [None] * len(candles)
    if len(candles) < period + 1:
        return out
    trs: list[float] = []
    for i in range(1, len(candles)):
        prev = candles[i - 1].close
        h, l = candles[i].high, candles[i].low
        tr = max(h - l, abs(h - prev), abs(l - prev))
        trs.append(tr)
    rma = _wilder_rma(trs, period)
    for i in range(period, len(trs) + 1):
        out[i] = rma[i - 1]
    return out


def bollinger(closes: list[float], period: int = 20, mult: float = 2.0):
    middle = sma(closes, period)
    upper: NoneSeries = [None] * len(closes)
    lower: NoneSeries = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1 : i + 1]
        mean = middle[i]
        var = sum((x - mean) ** 2 for x in window) / period
        sd = math.sqrt(var)
        upper[i] = mean + mult * sd
        lower[i] = mean - mult * sd
    return middle, upper, lower


def adx(candles: list[Candle], period: int = 14):
    n = len(candles)
    plus_di: NoneSeries = [None] * n
    minus_di: NoneSeries = [None] * n
    adx_out: NoneSeries = [None] * n
    if n < period + 1:
        return adx_out, plus_di, minus_di

    tr_list: list[float] = []
    plus_raw: list[float] = []
    minus_raw: list[float] = []
    for i in range(1, n):
        h, l, pc = candles[i].high, candles[i].low, candles[i - 1].close
        ph, pl = candles[i - 1].high, candles[i - 1].low
        tr = max(h - l, abs(h - pc), abs(l - pc))
        up = h - ph
        down = pl - l
        plus_raw.append(up if up > down and up > 0 else 0.0)
        minus_raw.append(down if down > up and down > 0 else 0.0)
        tr_list.append(tr)

    atr_rma = _wilder_rma(tr_list, period)
    pdi_rma = _wilder_rma(plus_raw, period)
    mdi_rma = _wilder_rma(minus_raw, period)

    dx_list: list[float] = []
    dx_at: list[int] = []
    for i in range(period, n):
        a = atr_rma[i - 1]
        if a is None or a == 0:
            continue
        pdi = 100.0 * pdi_rma[i - 1] / a
        mdi = 100.0 * mdi_rma[i - 1] / a
        plus_di[i] = pdi
        minus_di[i] = mdi
        dx = 100.0 * abs(pdi - mdi) / (pdi + mdi) if pdi + mdi != 0 else 0.0
        dx_list.append(dx)
        dx_at.append(i)

    if len(dx_list) < period:
        return adx_out, plus_di, minus_di
    seed_idx = dx_at[period - 1]
    adx_out[seed_idx] = sum(dx_list[:period]) / period
    for j in range(period, len(dx_list)):
        adx_out[dx_at[j]] = (adx_out[dx_at[j - 1]] * (period - 1) + dx_list[j]) / period
    return adx_out, plus_di, minus_di


def stochastic(candles: list[Candle], k_period: int = 14, d_period: int = 3):
    n = len(candles)
    raw_k: NoneSeries = [None] * n
    for i in range(k_period - 1, n):
        window = candles[i - k_period + 1 : i + 1]
        hi = max(c.high for c in window)
        lo = min(c.low for c in window)
        if hi == lo:
            raw_k[i] = 50.0
        else:
            raw_k[i] = 100.0 * (candles[i].close - lo) / (hi - lo)
    valid = [v for v in raw_k if v is not None]
    k_vals = sma(valid, d_period)
    slow_k: NoneSeries = [None] * n
    idx = n - len(valid)
    for j, v in enumerate(k_vals):
        if v is not None:
            slow_k[idx + j] = v
    slow_d = [None] * n
    valid2 = [v for v in slow_k if v is not None]
    d_vals = sma(valid2, d_period)
    idx2 = n - len(valid2)
    for j, v in enumerate(d_vals):
        if v is not None:
            slow_d[idx2 + j] = v
    return slow_k, slow_d


def donchian(candles: list[Candle], period: int = 20):
    n = len(candles)
    upper: NoneSeries = [None] * n
    lower: NoneSeries = [None] * n
    for i in range(period - 1, n):
        window = candles[i - period + 1 : i + 1]
        upper[i] = max(c.high for c in window)
        lower[i] = min(c.low for c in window)
    return upper, lower


def rate_of_change(closes: list[float], period: int = 10) -> NoneSeries:
    out: NoneSeries = [None] * len(closes)
    for i in range(period, len(closes)):
        prev = closes[i - period]
        if prev != 0:
            out[i] = 100.0 * (closes[i] - prev) / prev
    return out


def classic_pivots(candles: list[Candle]) -> dict[str, float]:
    if len(candles) < 2:
        raise ValueError("not enough candles for pivots")
    prev = candles[-2]
    p = (prev.high + prev.low + prev.close) / 3.0
    rng = prev.high - prev.low
    return {
        "P": p,
        "R1": 2 * p - prev.low,
        "S1": 2 * p - prev.high,
        "R2": p + rng,
        "S2": p - rng,
        "R3": prev.high + 2 * (p - prev.low),
        "S3": prev.low - 2 * (prev.high - p),
    }


def swing_levels(candles: list[Candle], window: int = 5, lookback: int = 20) -> tuple[list[float], list[float]]:
    highs: list[float] = []
    lows: list[float] = []
    start = max(window, len(candles) - lookback)
    for i in range(start, len(candles) - window):
        mid = candles[i]
        prev = candles[i - window : i]
        nxt = candles[i + 1 : i + window + 1]
        if mid.high >= max(c.high for c in prev) and mid.high >= max(c.high for c in nxt):
            highs.append(mid.high)
        if mid.low <= min(c.low for c in prev) and mid.low <= min(c.low for c in nxt):
            lows.append(mid.low)
    highs.sort(reverse=True)
    lows.sort()
    return highs, lows


def nearest_levels(price: float, levels: list[float], top: int = 3) -> list[float]:
    above = sorted(lv for lv in levels if lv > price)
    below = sorted((lv for lv in levels if lv < price), reverse=True)
    return above[:top] + below[:top]


def candle_pattern(prev: Candle, cur: Candle) -> str | None:
    body = cur.close - cur.open
    rng = cur.high - cur.low
    if rng == 0:
        return None
    upper = cur.high - max(cur.open, cur.close)
    lower = min(cur.open, cur.close) - cur.low
    p_body = prev.close - prev.open
    p_rng = prev.high - prev.low

    if abs(body) / rng < 0.1 and upper > 0.6 * rng and lower < 0.2 * rng:
        return "shooting-star"
    if abs(body) / rng < 0.1 and lower > 0.6 * rng and upper < 0.2 * rng:
        return "hammer"
    if abs(body) / rng < 0.1:
        return "doji"
    if p_rng > 0 and body > 0 and p_body < 0 and cur.open <= prev.close and cur.close > prev.open and body > 0.6 * p_rng:
        return "bullish-engulfing"
    if p_rng > 0 and body < 0 and p_body > 0 and cur.open >= prev.close and cur.close < prev.open and abs(body) > 0.6 * p_rng:
        return "bearish-engulfing"
    return None