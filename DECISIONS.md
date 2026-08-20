# Architecture Decision Records (ADRs)

This file records architectural, technical, and process decisions made for the project.

## ADR Template
```markdown
## ADR-[Number]: [Short Title]
- **Status:** [Proposed | Accepted | Rejected | Deprecated]
- **Date:** [YYYY-MM-DD]
- **Context:** [Context and problem statement]
- **Decision:** [The decision made]
- **Consequences:** [Positive and negative consequences]
```

---

## ADR-001: Project Documentation and Git as Persistent Source of Truth
- **Status:** Accepted
- **Date:** 2026-08-19
- **Context:** AI coding sessions can span different AI providers (e.g., Gemini, OpenRouter models) and chat sessions. Relying on conversational history risks context loss and fragmentation.
- **Decision:** Use local version-controlled project documentation (`AI_CONTEXT.md`, `ARCHITECTURE.md`, `TODO.md`, `DECISIONS.md`, `CHANGELOG.md`) and Git history as the absolute source of truth independent of any AI provider.
- **Consequences:** 
  - **Positive:** Seamless handoffs between any AI provider or coding agent; permanent, auditable project history; zero vendor lock-in for project context.
  - **Negative:** Requires discipline to update documentation files continuously during development.

---

## ADR-002: Zero-Dependency Python CLI
- **Status:** Accepted
- **Date:** 2026-08-19
- **Context:** The environment (Python 3.14, Node 22) has no package manager or
  data-science libraries available (no pip, pandas, numpy, or rich). A "fully
  functional" tool must run out of the box with zero install steps.
- **Decision:** Implement as a pure-stdlib Python package (`urllib`, `json`,
  `math`, `argparse`, `dataclasses`). All indicators hand-written in Python.
  Tests use a built-in zero-dependency runner (`tests/run_tests.py`) that is
  pytest-compatible.
- **Consequences:**
  - **Positive:** Runs immediately on any Python ≥ 3.10; trivially portable;
    no supply-chain surface.
  - **Negative:** Indicator implementations must be maintained manually; no
    numpy vectorization for large datasets.

## ADR-003: Live Data from Yahoo Finance Chart API (GC=F)
- **Status:** Accepted
- **Date:** 2026-08-19
- **Context:** A setup generator needs real XAU/USD candles. Stooq now serves an
  anti-bot proof-of-work challenge to non-browser clients, and Yahoo's
  `XAUUSD=X` spot symbol returns 404. A browser-style User-Agent makes Yahoo's
  chart API return clean OHLCV JSON with no key.
- **Decision:** Use `https://query1.finance.yahoo.com/v8/finance/chart/GC=F`
  (COMEX gold futures, the standard XAU/USD proxy) with a browser User-Agent.
  Cache responses to disk with per-interval TTLs to respect the API.
- **Consequences:**
  - **Positive:** Free, keyless, reliable across all timeframes (5m→1d).
  - **Negative:** Depends on Yahoo availability and their unofficial endpoint;
    GC=F is futures- not spot-priced (usually within a few dollars of spot).

## ADR-005: Analysis-Driven Advisor (backtesting removed)
- **Status:** Accepted
- **Date:** 2026-08-20
- **Context:** The user asked for a tool that always delivers a trade setup from
  realtime data, analysing "each and everything" (EMA/SMA/BB/RSI/Fib/S-R/
  supply-demand/liquidity/BoS/CHoCH/breakout/fakeout/ICT), picks whichever
  strategy the current data actually supports, and removed all backtesting.
- **Decision:**
  - Replace the confluence-signal pipeline with a full `Analysis` engine
    (`analysis.py`) that computes indicators, structure, zones, and a regime.
  - `advisor.py` scores both directions, selects the best-fitting strategy,
    and **always returns a BUY or SELL setup** — never a "no-trade" result.
    Weak setups are surfaced with an explicit warning instead of suppressed.
  - Delete backtesting and win-rate estimation entirely (`backtest.py`,
    `winrate.py`, `--backtest`, `/api/backtest`).
  - Add a TwelveData `XAU/USD` fallback (ADR-003 superseded for redundancy);
    scope intervals to `1m/5m/15m/1h`.
- **Consequences:**
  - **Positive:** A concrete setup on every request; broadest possible analysis
    with transparent per-factor evidence; resilient data fetching.
  - **Negative:** The "probability" is a heuristic confluence estimate, not a
    statistically measured win rate — labelled as such; no historical
    validation is available by user request.

---

## ADR-006: Institutional Scalping Scanner (legacy strategy logic removed)
- **Status:** Accepted
- **Date:** 2026-08-20
- **Context:** The user asked to replace all legacy strategy logic with two
  high-frequency, institutional-grade scalping strategies: a Multi-Timeframe FVG
  + EMA Pullback continuation trade and a London/NY Session Liquidity Sweep &
  CHoCH reversal trade. Setups must be strict (structural filters + risk-to-
  reward floors) rather than guaranteed; higher timeframes are not wanted.
- **Decision:**
  - Delete `strategies.py`, `advisor.py`, and the `generate_setups`/`aggregate`
    scoring machinery. The scanner no longer forces a setup — nothing is emitted
    when a candidate fails its filters or R:R floor.
  - Implement `scalper.py` with two modular strategy functions plus `scan()`:
    - **FVG + EMA Pullback:** 1H EMA20/EMA50 macro filter → 5M active
      unfilled-FVG tap at the 5M EMA20 with an RSI(14) reset through 50; SL
      below the local zone swing, TP at nearest 15M/1H structural liquidity;
      discard below 1:2.5 R:R.
    - **Session Sweep & CHoCH:** active 08:00–10:00 UTC (London) or 13:00–16:00
      UTC (NY overlap); wick sweep of the prior session swing + CHoCH close
      through nearest micro-structure; retracement entry into the breakout
      candle's discount/premium, SL beyond the wick tip, TP at the opposite
      intraday range edge; discard below 1:3 R:R.
  - Add `unfilled_fvgs()` and `session_range()` helpers to `analysis.py`.
  - Replace the CLI/web/report output with the exact scanner-report banner.
- **Consequences:**
  - **Positive:** Only high-conviction, risk-controlled setups are shown; fully
    modular and unit-tested with synthetic data; matches the user's requested
    institutional playbook.
  - **Negative:** The scanner can legitimately report "no qualifying setup";
    fewer setups than the old always-trade advisor. This supersedes the
    "no no-trade" guarantee in ADR-005.

---

## ADR-004: Multi-Strategy Confluence Scoring
- **Status:** Accepted
- **Date:** 2026-08-19
- **Context:** A single strategy produces noisy, low-conviction signals.
  Combining trend, breakout, and mean-reversion views gives setups a measurable
  confluence score and filters contradictory inputs.
- **Decision:** Three strategy engines emit direction + confidence. Signals are
  aggregated with fixed weights (trend 1.0, breakout 1.0, meanrev 0.8, candle
  0.5); a setup is emitted per direction when its share of total weighted
  signal strength meets a configurable `--min-score` (default 0.4).
- **Consequences:**
  - **Positive:** Transparent, explainable scoring; conflicting signals
    degrade agreement and are filtered by default; thresholds are tunable.
  - **Negative:** Weight selection is heuristic, not backtest-optimized.
