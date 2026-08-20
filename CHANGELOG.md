# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0/).

## [0.6.0] - 2026-08-20
### Added
- **Two institutional scalping strategies** (`goldsetup/scalper.py`):
  - *Multi-Timeframe FVG + EMA Pullback*: 1H EMA20/EMA50 macro filter, 5M
    active unfilled-FVG pullback tapped at the 5M EMA20, RSI(14) reset through
    50, SL below the local zone swing, TP at nearest 15M/1H structural
    liquidity. **Discards setups below 1:2.5 R:R.**
  - *Session Liquidity Sweep & CHoCH*: London (08:00–10:00 UTC) or NY
    (13:00–16:00 UTC) only, wick sweep of the prior session swing + CHoCH
    micro-structure break, retracement entry into the breakout candle's
    discount/premium, SL beyond the wick tip, TP at the opposite intraday
    range edge. **Discards setups below 1:3 R:R.**
- `unfilled_fvgs()` and `session_range()` helpers in `analysis.py` (active
  FVG tracking + current-UTC-day range).
- Exact structured CLI report format (scanner banner with Strategy Matched /
  Direction / Timeframe / Entry / SL / TP / R:R / Reason-Confluence) and a
  matching JSON payload (`strategies_scanned`, per-setup levels + evidence).
### Removed
- **All legacy strategy logic**: `strategies.py`, `advisor.py`, and the
  `generate_setups` / `aggregate` / `WEIGHTS` machinery. No more guaranteed
  "always returns a BUY/SELL" advisor — setups are only emitted when they meet
  strict structural + R:R criteria.
- `--confirm` HTF-bias option (and the dashboard bias selector).
### Changed
- `cli.py` / `web.py` now fetch 5m + 15m + 1h and run `scalper.scan()`.
- Web dashboard rewritten for the scanner payload (Setup Scan card, Market
  Snapshot strip, LONG/SHORT direction).
- Tests rewritten for the scanner (legacy strategy/MTF/setup tests removed);
  48 tests passing.

## [0.5.0] - 2026-08-20
### Added
- **TwelveData fallback** data source (`XAU/USD` gold spot) when Yahoo is
  rate-limited/unavailable; key configurable via `TWELVEDATA_API_KEY`; active
  source reported in CLI/JSON/web.
- **Full market-structure analysis engine** (`goldsetup/analysis.py`): EMA
  9/21/50/200 + SMA, Bollinger, RSI + divergence, MACD, Stochastic, ADX/DMI,
  ATR, Fibonacci retracements/extensions, clustered support/resistance,
  supply/demand zones, liquidity pools (buy/sell side + equal highs/lows),
  BoS/CHoCH market structure, Donchian breakout vs fakeout, liquidity sweeps,
  fair-value gaps, and order blocks. Produces a regime classification.
- **Advisor** (`goldsetup/advisor.py`): scores both directions, selects the
  strategy whose preconditions the analysis satisfied, and **always returns a
  BUY/SELL setup** (weak-probability setups are flagged, never suppressed).
- Web dashboard: Recommended Setup card with strategy + probability + evidence,
  Full Market Analysis strip, Live mode (15s fresh-data polling).
- Data helper `higher_tf_period`/`last_completed_hi_index` moved into `data.py`.
### Removed
- All backtest machinery: `backtest.py`, `winrate.py`, `--backtest`,
  `--winrate`, `--min-score`, `/api/backtest`, and the in-page backtest panel.
- Win-rate fields (`est_win_rate`, `win_factors`) — replaced by the advisor's
  confluence probability.
### Changed
- Intervals scoped to `1m`/`5m`/`15m`/`1h` (default `5m`); higher TFs removed.
- Test suite rewritten for the new engine (50 tests passing).

## [0.4.0] - 2026-08-19
### Added
- **Web dashboard** (`--serve` / `python -m goldsetup.web`): zero-dependency
  pure-Python `http.server` app with a self-contained vanilla JS + SVG
  frontend (no CDN, no npm, no install).
  - Setup cards (entry/SL/TP, R:R, sizing, confirmation badges), candlestick
    chart with the top setup overlaid, market-context panel, and an in-page
    backtest with metrics + trade table.
  - JSON API: `/api/overview`, `/api/backtest`, `/api/health`; 60s auto-refresh.
  - Shared interval/range/confirm constants moved into `goldsetup/data.py`.
- 5 web unit tests (46 total).

## [0.3.0] - 2026-08-19
### Added
- **Multi-timeframe confirmation**: `--confirm <tf>` filters setups to those aligned with a higher-timeframe trend (EMA structure + ADX ≥ 20), using only the last completed higher-TF candle (no lookahead). Works in live mode and `--backtest`.
- `confirm_bias()` strategy classifier, no-lookahead higher-TF alignment helpers, weekly (`1wk`) data interval support.
- Confirmation badge in the live report and `use_confirm` in backtest JSON output.
- 8 MTF unit tests (41 total).
### Changed
- Backtest `generate_setups` signature now accepts `confirm_bias_value` / `require_confirm`.

## [0.2.0] - 2026-08-19
### Added
- **Walk-forward backtesting harness** (`goldsetup/backtest.py`): regenerates setups bar-by-bar with the same logic used live, simulates stop/target exits on subsequent candles (stop-first on same-bar conflicts), uses fixed-fractional equity sizing, one position at a time.
- Backtest metrics: trade count, overall + per-direction win rate, profit factor, expectancy (R), final equity, total return %, and max drawdown.
- `--backtest` CLI mode (defaults to 2y of daily data), `--verbose` trade log, and `--json` backtest output.
- 7 backtest unit tests (33 total).

## [0.1.0] - 2026-08-19
### Added
- Initialized project context infrastructure and documentation standards (`AI_CONTEXT.md`, `ARCHITECTURE.md`, `TODO.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `.gitignore`).
- Established Git and project documentation as the persistent, AI-provider-independent source of truth (ADR-001).
- **XAU/USD trade setup generator** — zero-dependency Python CLI (`goldsetup/`):
  - Live OHLCV data from the Yahoo Finance chart API (`GC=F`) with on-disk caching and per-interval TTLs (ADR-003).
  - Pure-Python indicators: EMA, RSI (Wilder), MACD, ATR (Wilder), ADX/DMI, Bollinger, Stochastic, Donchian, classic pivots, swing levels, candle patterns.
  - Three strategy engines — trend-following, breakout, mean-reversion — plus a candle-pattern signal.
  - Confluence scoring with tunable minimum agreement, and weighted aggregation of conflicting signals (ADR-004).
  - Setup generation with ATR/S-R-based stop-loss and take-profit, R:R, and USD/oz/lot position sizing from account balance and risk %.
  - ANSI terminal report and `--json` output; configurable interval, range, account, risk, and score thresholds.
- Zero-dependency test suite (`tests/`, 26 tests) covering indicators, strategies, and setup math.