import math

from goldsetup import scalper
from goldsetup.analysis import unfilled_fvgs, session_range
from goldsetup.data import Candle
from goldsetup.scalper import (SWEEP_MIN_RR, FVG_EMA_MIN_RR, _choch_after_sweep,
                               _rsi_reset_bullish, _sweep_on_last_bar,
                               strategy_fvg_ema_pullback, strategy_session_sweep_choch)
from goldsetup import indicators as ind
from tests.conftest import candles_from_closes, make_5m


# ---------------------------------------------------------------- helpers

def _fvg_pullback_scenario():
    """Crafted 5m market: impulse up (FVG creation), deep pullback that taps the
    final unfilled FVG while RSI resets below 50, then a recovery candle."""
    c1h = candles_from_closes([100 + 1.5 * i for i in range(80)])
    closes = []
    for i in range(24):
        closes.append(100 + 0.15 * math.sin(i))
    c = 100.2
    for _ in range(6):
        closes.append(c)
        c += 0.8
    for _ in range(8):
        closes.append(c)
        c -= 0.55
    closes = closes[:-3] + [100.6, 100.55, 102.0]
    candles = make_5m(closes, hour=11)
    n = len(candles)
    candles[n - 3] = Candle(candles[n - 3].timestamp, 102.8, 103.0, 100.5, 100.6, 1000.0)
    candles[n - 2] = Candle(candles[n - 2].timestamp, 100.6, 100.8, 100.45, 100.55, 1000.0)
    candles[n - 1] = Candle(candles[n - 1].timestamp, 100.55, 102.3, 100.4, 102.0, 1000.0)
    c15 = candles_from_closes([103 + 0.4 * i for i in range(40)] + [118.0, 117.0, 116.0, 115.0, 114.0])
    return c1h, candles, c15


def _sweep_scenario():
    """Crafted 5m market: prior session swing high at ~130 swept by a wick, CHoCH
    close below micro-structure, retracement entry, TP at session low."""
    closes = []
    for i in range(24):
        closes.append(118.0 + 0.5 * i)
    for c in [127, 128, 129, 130, 129, 128, 128, 129, 130, 129, 128, 127, 128, 129]:
        closes.append(c)
    candles = make_5m(closes + [126.5], hour=11)
    last = candles[-1]
    candles[-1] = Candle(last.timestamp, 128.0, 130.6, 126.0, 126.5, 1000.0)
    candles[-2] = Candle(candles[-2].timestamp, candles[-2].open, candles[-2].high, 128.2, candles[-2].close, 1000.0)
    candles[-3] = Candle(candles[-3].timestamp, candles[-3].open, candles[-3].high, 128.4, candles[-3].close, 1000.0)
    return candles, candles[-12:]


# ---------------------------------------------------------------- macro filter

def test_macro_bias_uptrend_long():
    c1h = candles_from_closes([100 + 1.5 * i for i in range(80)])
    assert scalper.macro_bias(c1h) == "LONG"


def test_macro_bias_downtrend_short():
    c1h = candles_from_closes([200 - 1.5 * i for i in range(80)])
    assert scalper.macro_bias(c1h) == "SHORT"


def test_macro_bias_short_history_none():
    assert scalper.macro_bias(candles_from_closes([100.0] * 10)) is None


# ---------------------------------------------------------------- indicator units

def test_rsi_reset_detects_cross_below_then_above():
    closes = [100.0] * 10
    for i in range(1, 9):
        closes.append(closes[-1] - 1.0)   # sharp decline -> RSI below 50
    for i in range(1, 7):
        closes.append(closes[-1] + 1.2)   # recovery -> RSI back above 50
    assert _rsi_reset_bullish(ind.rsi(closes, 14))


def test_rsi_reset_false_without_cross():
    closes = [100.0]
    for i in range(1, 30):
        closes.append(closes[-1] + 0.8)
    assert not _rsi_reset_bullish(ind.rsi(closes, 14))


def test_sweep_detected_bearish():
    candles, _ = _sweep_scenario()
    sweep = _sweep_on_last_bar(candles)
    assert sweep is not None
    assert sweep["direction"] == "SHORT"
    assert sweep["extreme"] > sweep["level"]


def test_sweep_none_without_wick():
    candles = make_5m([100 + 0.5 * i for i in range(40)], hour=11)
    assert _sweep_on_last_bar(candles) is None


def test_choch_true_after_sweep():
    candles, _ = _sweep_scenario()
    sweep = _sweep_on_last_bar(candles)
    assert sweep is not None
    assert _choch_after_sweep(candles, sweep) is True


def test_choch_false_without_structure_break():
    candles, _ = _sweep_scenario()
    sweep = _sweep_on_last_bar(candles)
    candles[-1] = Candle(candles[-1].timestamp, 128.0, 130.6, 126.0, 129.2, 1000.0)
    assert not _choch_after_sweep(candles, sweep)


def test_unfilled_fvg_and_session_helpers():
    c1h, candles, _ = _fvg_pullback_scenario()
    gaps = unfilled_fvgs(candles)
    assert any(g.kind == "fvg-bullish" for g in gaps)
    rng = session_range(candles)
    assert rng is not None
    assert rng[0] >= max(c.high for c in candles) * 0.9999


# ---------------------------------------------------------------- strategy 1

def test_strategy1_long_setup_valid_and_rr_enforced():
    c1h, candles, c15 = _fvg_pullback_scenario()
    s = strategy_fvg_ema_pullback(candles, c1h, c15)
    assert s is not None
    assert s.direction == "LONG"
    assert s.stop is not None and s.take_profit is not None
    assert s.stop < s.entry < s.take_profit
    assert s.rr >= FVG_EMA_MIN_RR
    assert s.position_lots >= 0 and s.risk_amount > 0
    assert s.strategy == "Multi-Timeframe FVG + EMA Pullback"
    assert s.evidence and s.rationale


def test_strategy1_rejects_short_rr_when_bias_short_and_no_short_trigger():
    c1h = candles_from_closes([200 - 1.5 * i for i in range(80)])
    candles = make_5m([200 - 0.5 * i for i in range(60)], hour=11)
    c15 = candles_from_closes([150 + 0.4 * i for i in range(40)])
    s = strategy_fvg_ema_pullback(candles, c1h, c15)
    assert s is None or s.direction == "SHORT"


def test_strategy1_none_without_macro_trend():
    c1h = candles_from_closes([100.0 + 0.1 * (i % 5) for i in range(60)])
    c15 = candles_from_closes([103 + 0.4 * i for i in range(40)] + [118.0])
    c1h2, candles, _ = _fvg_pullback_scenario()
    s = strategy_fvg_ema_pullback(candles, c1h, c15)
    assert s is None


# ---------------------------------------------------------------- strategy 2

def test_strategy2_short_setup_valid_and_rr_enforced():
    candles, c15 = _sweep_scenario()
    s = strategy_session_sweep_choch(candles, c15)
    assert s is not None
    assert s.direction == "SHORT"
    assert s.stop is not None and s.take_profit is not None
    assert s.stop > s.entry > s.take_profit
    assert s.rr >= SWEEP_MIN_RR
    assert s.strategy == "Session Liquidity Sweep & CHoCH"


def test_strategy2_outside_session_returns_none():
    candles, c15 = _sweep_scenario()
    out = make_5m([x.close for x in candles], hour=3)
    n = len(out)
    last = candles[-1]
    out[-1] = Candle(out[-1].timestamp, last.open, last.high, last.low, last.close, 1000.0)
    out[-2] = Candle(out[-2].timestamp, candles[-2].open, candles[-2].high, candles[-2].low, candles[-2].close, 1000.0)
    out[-3] = Candle(out[-3].timestamp, candles[-3].open, candles[-3].high, candles[-3].low, candles[-3].close, 1000.0)
    assert scalper._in_session(out) is False
    s = strategy_session_sweep_choch(out, c15)
    assert s is None


def test_strategy2_no_sweep_returns_none():
    candles = make_5m([100 + 0.5 * i for i in range(40)], hour=14)
    assert strategy_session_sweep_choch(candles, candles[-10:]) is None


# ---------------------------------------------------------------- scan orchestrator

def test_scan_runs_both_strategies_without_error():
    c1h, candles, c15 = _fvg_pullback_scenario()
    setups = scalper.scan(candles, c1h, c15, balance=10000.0, risk_pct=1.0)
    assert isinstance(setups, list)
    for s in setups:
        assert s.stop is not None and s.take_profit is not None
        assert s.rr >= (SWEEP_MIN_RR if "Sweep" in s.strategy else FVG_EMA_MIN_RR)
        if s.direction == "LONG":
            assert s.stop < s.entry < s.take_profit
        else:
            assert s.stop > s.entry > s.take_profit


# ---------------------------------------------------------------- report format

def _fake_setup():
    from goldsetup.setup import Setup

    return Setup(
        direction="BUY",
        confidence=0.6,
        entry=4539.7,
        stop=4534.1,
        take_profit=4552.3,
        rr=3.45,
        strategy="Multi-Timeframe FVG + EMA Pullback",
        probability=0.6,
        evidence=["1H macro filter: EMA20>EMA50",
                  "5M unfilled fvg-bullish at 4525.0-4527.0",
                  "Pullback tapped 5M EMA20 with RSI re-crossing 50",
                  "SL 4534.1 below zone swing; TP 4552.3 at 15M/1H liquidity"],
        rationale=["LONG via Multi-Timeframe FVG + EMA Pullback"],
        position_oz=2.0,
        position_lots=0.02,
        risk_amount=100.0,
        reward_amount=345.0,
        confirmed=True,
        confirm_bias="BUY",
    )


def test_report_uses_exact_scanner_banner():
    from goldsetup import report
    from goldsetup.analysis import analyse

    c1h, candles, c15 = _fvg_pullback_scenario()
    a = analyse(candles)
    s = _fake_setup()
    text = report.render_report(candles, a, [s], "5m", 10000.0, 1.0,
                                source="yahoo", no_color=True)
    lines = text.splitlines()
    assert lines[0] == "=" * 50
    assert lines[1].startswith("🚀 XAU/USD SETUP SCANNER REPORT [")
    assert lines[2] == "=" * 50
    assert "[*] Strategy Matched : Multi-Timeframe FVG + EMA Pullback" in lines
    assert "[*] Direction        : LONG" in lines
    assert any(l.startswith("[*] Timeframe        : ") for l in lines)
    assert "- Entry Price        : 4,539.70" in lines
    assert "- Stop Loss          : 4,534.10" in lines
    assert "- Take Profit        : 4,552.30" in lines
    assert "- Risk-to-Reward     : 1:3.45" in lines
    assert any(l.startswith("- Reason/Confluence  : ") for l in lines)


def test_report_no_setup_message():
    from goldsetup import report
    from goldsetup.analysis import analyse

    candles = make_5m([100 + 0.5 * i for i in range(40)], hour=11)
    a = analyse(candles)
    text = report.render_report(candles, a, [], "5m", 10000.0, 1.0, no_color=True)
    assert "No qualifying setup" in text