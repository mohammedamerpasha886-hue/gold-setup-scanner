import math

from goldsetup import indicators as ind
from tests.conftest import candles_from_closes, make_candles


def test_sma():
    out = ind.sma([1.0, 2.0, 3.0, 4.0, 5.0], 3)
    assert out[:2] == [None, None]
    assert out[2:] == [2.0, 3.0, 4.0]


def test_ema_constant_series():
    series = [42.0] * 60
    out = ind.ema(series, 10)
    assert all(v is None or math.isclose(v, 42.0) for v in out)


def test_rsi_all_gains_is_100():
    series = [float(i) for i in range(1, 40)]
    out = ind.rsi(series, 14)
    assert out[-1] == 100.0


def test_rsi_all_losses_is_0():
    series = [float(i) for i in range(39, 0, -1)]
    out = ind.rsi(series, 14)
    assert out[-1] == 0.0


def test_rsi_range():
    out = ind.rsi([float(i) for i in range(1, 40)], 14)
    assert all(v is None or 0.0 <= v <= 100.0 for v in out)


def test_macd_flat_is_zero():
    out = ind.macd([50.0] * 80)
    line, sig, hist = out
    assert line[-1] == 0.0
    assert sig[-1] == 0.0
    assert hist[-1] == 0.0


def test_atr_constant_range():
    closes = [100.0 + i for i in range(40)]
    highs = [c + 5.0 for c in closes]
    lows = [c - 5.0 for c in closes]
    out = ind.atr(make_candles(closes, highs, lows), 14)
    assert out[-1] is not None
    assert math.isclose(out[-1], 10.0, rel_tol=1e-3)


def test_bollinger_constant():
    out = ind.bollinger([25.0] * 40, 20, 2.0)
    mid, up, low = out
    assert math.isclose(mid[-1], 25.0)
    assert math.isclose(up[-1], 25.0)
    assert math.isclose(low[-1], 25.0)


def test_adx_alignment_no_none_on_last():
    closes = [100.0 + 2.0 * i for i in range(80)]
    candles = candles_from_closes(closes)
    adx, pdi, mdi = ind.adx(candles, 14)
    assert adx[-1] is not None
    assert adx[-1] > 30.0
    assert pdi[-1] > mdi[-1]


def test_stochastic_constant_is_50():
    closes = [100.0] * 40
    candles = candles_from_closes(closes)
    k, d = ind.stochastic(candles, 14, 3)
    assert math.isclose(k[-1], 50.0)


def test_donchian():
    closes = [float(i) for i in range(30)]
    highs = [c + 3 for c in closes]
    lows = [c - 3 for c in closes]
    candles = make_candles(closes, highs, lows)
    up, low = ind.donchian(candles, 20)
    assert math.isclose(up[-1], closes[-1] + 3)
    assert math.isclose(low[-1], closes[-20] - 3)


def test_classic_pivots():
    prev = ind.Candle(0, 100.0, 102.0, 98.0, 101.0, 1.0)
    cur = ind.Candle(0, 100.0, 100.0, 100.0, 100.0, 1.0)
    piv = ind.classic_pivots([prev, cur])
    p = (102.0 + 98.0 + 101.0) / 3.0
    assert math.isclose(piv["P"], p)


def test_candle_patterns():
    bear = ind.Candle(0, 101.0, 101.2, 99.8, 100.1, 1.0)
    hammer = ind.Candle(0, 100.0, 100.1, 99.4, 100.02, 1.0)
    assert ind.candle_pattern(bear, hammer) == "hammer"
    star = ind.Candle(0, 100.0, 100.6, 99.9, 99.98, 1.0)
    assert ind.candle_pattern(bear, star) == "shooting-star"
    bull = ind.Candle(0, 100.0, 102.0, 99.9, 102.0, 1.0)
    assert ind.candle_pattern(bear, bull) == "bullish-engulfing"