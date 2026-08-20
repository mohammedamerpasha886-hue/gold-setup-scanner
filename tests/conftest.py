import math
from datetime import datetime, timedelta, timezone

from goldsetup.data import Candle


def candles_from_closes(closes: list[float]) -> list[Candle]:
    out = []
    for i, c in enumerate(closes):
        o = closes[i - 1] if i > 0 else c
        h = max(o, c) * 1.001
        l = min(o, c) * 0.999
        out.append(Candle(1700000000 + i * 86400, round(o, 4), round(h, 4), round(l, 4), round(c, 4), 1000.0))
    return out


def make_candles(closes: list[float], highs: list[float] | None = None, lows: list[float] | None = None) -> list[Candle]:
    out = []
    for i, c in enumerate(closes):
        o = closes[i - 1] if i > 0 else c
        h = highs[i] if highs else max(o, c) * 1.001
        l = lows[i] if lows else min(o, c) * 0.999
        out.append(Candle(1700000000 + i * 86400, round(o, 4), round(h, 4), round(l, 4), round(c, 4), 1000.0))
    return out


def assert_close(a: float, b: float, tol: float = 1e-6) -> None:
    assert math.isclose(a, b, rel_tol=tol, abs_tol=tol), f"{a} != {b}"


def make_5m(closes: list[float], highs: list[float] | None = None,
            lows: list[float] | None = None, hour: int = 9) -> list[Candle]:
    """Synthetic 5-minute candles anchored to a chosen UTC hour (same UTC day)."""
    base = datetime(2026, 1, 2, hour, 0, tzinfo=timezone.utc)
    step = int(timedelta(minutes=5).total_seconds())
    out = []
    for i, c in enumerate(closes):
        o = closes[i - 1] if i > 0 else c
        h = highs[i] if highs else max(o, c) * 1.001
        l = lows[i] if lows else min(o, c) * 0.999
        out.append(Candle(int(base.timestamp()) + i * step,
                          round(o, 4), round(h, 4), round(l, 4), round(c, 4), 1000.0))
    return out