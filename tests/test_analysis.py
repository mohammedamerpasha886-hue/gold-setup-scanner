import math

from goldsetup.analysis import analyse, analysis_json
from tests.conftest import candles_from_closes


def _trend(direction: float) -> list:
    closes = [100.0 + direction * 0.3 * i + 1.6 * math.sin(i / 2.5) for i in range(200)]
    return candles_from_closes(closes)


def _uptrend():
    return _trend(1.0)


def _downtrend():
    return _trend(-1.0)


def _flat():
    return candles_from_closes([100.0 + 0.1 * (i % 7) for i in range(200)])


def test_analysis_uptrend_fields():
    a = analyse(_uptrend())
    assert a.price > 100.0
    assert a.atr is not None and a.atr > 0
    assert a.ema[9] is not None and a.ema[50] is not None
    assert a.rsi is not None and 0 <= a.rsi <= 100
    assert a.fib and a.fib.get("0.618") is not None
    assert isinstance(a.support, list) and isinstance(a.resistance, list)
    assert a.regime in ("trend-up", "trend-down", "range", "breakout", "reversal", "volatile")


def test_analysis_fib_levels_monotonic():
    a = analyse(_uptrend())
    vals = [a.fib[str(r)] for r in (0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0)]
    assert vals == sorted(vals) or vals == sorted(vals, reverse=True)
    assert len(set(vals)) > 3


def test_analysis_json_serializable():
    a = analyse(_downtrend())
    j = analysis_json(a)
    assert j["price"] == round(a.price, 2)
    assert "regime" in j and "fib" in j and "structure" in j


def test_unfilled_fvgs_detects_active_gap():
    from goldsetup.analysis import unfilled_fvgs
    from goldsetup.data import Candle

    candles = [
        Candle(1700000000 + i * 300, 100, 100, 100, 100, 1) for i in range(10)
    ]
    candles[2] = Candle(candles[2].timestamp, 102, 104, 101, 103, 1)   # gap up
    for i in range(3, 10):                                            # stay above the gap
        candles[i] = Candle(candles[i].timestamp, 103, 106, 102.5, 104 + i * 0.1, 1)
    gaps = unfilled_fvgs(candles)
    assert gaps
    assert all(z.kind == "fvg-bullish" for z in gaps)
    assert gaps[0].lo >= 100 and gaps[0].hi > gaps[0].lo


def test_unfilled_fvgs_marks_filled_gap():
    from goldsetup.analysis import unfilled_fvgs
    from goldsetup.data import Candle

    candles = [
        Candle(1700000000 + i * 300, 100, 100, 100, 100, 1) for i in range(10)
    ]
    candles[2] = Candle(candles[2].timestamp, 102, 104, 101, 103, 1)   # gap up
    candles[3] = Candle(candles[3].timestamp, 103, 104, 99, 100, 1)    # fills back through gap
    gaps = unfilled_fvgs(candles)
    assert not any(g.kind == "fvg-bullish" for g in gaps)


def test_session_range_tracks_current_utc_day():
    from datetime import datetime, timezone
    from goldsetup.analysis import session_range
    from goldsetup.data import Candle

    base = datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc).timestamp()
    candles = [
        Candle(int(base) + i * 300, 100 + i, 102 + i, 99 + i, 101 + i, 1)
        for i in range(5)
    ]
    s_hi, s_lo = session_range(candles)
    assert s_hi == max(c.high for c in candles)
    assert s_lo == min(c.low for c in candles)