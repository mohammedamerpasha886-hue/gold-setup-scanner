# AI Context & Handoff Document

## Project Identity & Purpose
- **Project Name:** MyApp
- **Purpose:** A persistent, AI-provider-independent coding workspace designed to maintain continuous context across different AI sessions, models, and coding agents via version-controlled project documentation and Git history.
- **Current Application:** A zero-dependency Python CLI + web dashboard that fetches **realtime** XAU/USD (gold) price data, runs a market-structure analysis, and scans for **five institutional scalping setups** — Multi-Timeframe FVG + EMA Pullback, Session Sweep & CHoCH, Order Block Retest + RSI Divergence, Asian Range Breakout, and Supply/Demand Zone Flip — with strict structural filters and risk-to-reward floors. It runs 24/7 and pushes qualifying setups to Telegram (locally or embedded in a hosted Railway server). Backtesting and the always-return-a-setup advisor have been removed by user request.

## Current Project Status
- **Phase:** Application Implementation
- **Status:** Active
- **Active Focus:** v0.6.0 (institutional scalping scanner). Next: optional Gemini narrative commentary, news-window filters.

## Technology Stack
- **Languages:** Python ≥ 3.10 (standard library only — no pip, pandas, numpy, or rich available in the dev environment)
- **Frameworks:** None (argparse CLI, dataclasses, urllib, http.server)
- **Databases/Storage:** On-disk JSON cache at `~/.cache/goldsetup` (TTL per interval)
- **Testing Tools:** Zero-dependency runner `tests/run_tests.py` (pytest-compatible test functions; 60 passing)

## Data Sources
- **Primary:** Yahoo Finance chart API `GC=F` (COMEX gold futures).
- **Fallback:** TwelveData `XAU/USD` (gold spot) — used automatically when Yahoo is rate-limited or fails. API key via `TWELVEDATA_API_KEY` (bundled default). Active source exposed as `data.LAST_SOURCE` and shown in every report.
- **Intervals:** `1m`, `5m`, `15m`, `1h` only (default `5m`). Higher timeframes removed by user request.
- **Ranges:** `1m`→`5d`, `5m`→`1d`, `15m`→`5d`, `1h`→`1mo` (auto).
- **Cache TTLs:** 1m 30s, 5m 60s, 15m 3m, 1h 15m. `--realtime` / `--no-cache` bypasses cache.

## Project Structure
```text
MyApp/
├── .git/
├── gold-setup.py            # executable entry point (no install needed)
├── pyproject.toml           # pip metadata + gold-setup console script
├── goldsetup/
│   ├── cli.py               # argument parsing, orchestration (fetch 5m/15m/1h, run scan, report, watch)
│   ├── data.py              # Yahoo/TwelveData fetchers + disk cache + shared constants + MTF helpers
│   ├── indicators.py        # EMA, SMA, RSI, MACD, ATR, ADX, Bollinger, Stochastic, Donchian, pivots, swings, patterns
│   ├── analysis.py          # market-structure engine + unfilled-FVG / session-range helpers
│   ├── scalper.py           # the five institutional scalping strategies + scan() orchestration
│   ├── telegram.py          # Telegram Bot API integration (alerts, config in cache dir)
│   ├── watch.py             # 24/7 scanner loop → Telegram alerts (dedup + heartbeat)
│   ├── setup.py             # Setup dataclass + position sizing
│   ├── web.py               # zero-dependency HTTP dashboard server + JSON API
│   └── report.py            # structured scanner report + JSON rendering
├── web/index.html           # self-contained dashboard UI (vanilla JS + SVG)
├── tests/
│   ├── conftest.py          # candle factories + assert helpers
│   ├── run_tests.py         # zero-dependency test runner
│   └── test_*.py            # 60 unit tests
└── *.md                     # project documentation (source of truth)
```

## Important Files
- `goldsetup/` — application source (see component map above).
- `AI_CONTEXT.md`: Primary persistent handoff document and AI agent guidelines.
- `ARCHITECTURE.md`: Component breakdown and data flow.
- `DECISIONS.md`: ADRs — docs-as-truth (001), pure-stdlib Python (002), data sources (003), confluence scoring (004), advisor design (005), institutional scalping scanner (006).
- `TODO.md`: Task tracking, backlog, and milestones.
- `CHANGELOG.md`: Chronological record of changes and releases.

## Coding Conventions
- **General:** Python standard library only; no external dependencies.
- **Indicators:** All implemented from scratch in `indicators.py`; Wilder smoothing for RSI/ATR/ADX; series are length-aligned lists with `None` padding at the start.
- **Analysis:** `analysis.py` returns a dataclass `Analysis` with all computed fields + `analysis_json()` for serialization.
- **Scalper:** `scalper.scan()` runs the five institutional strategies and returns only setups that pass strict structural filters and their R:R floor (FVG+EMA ≥1:2.5, Sweep+CHoCH ≥1:3, OB+Div ≥1:2.5, Asian Breakout ≥1:2, Zone Flip ≥1:2.5). No setup is forced when nothing qualifies.
- **Documentation:** Keep documentation synchronized with code changes and Git history.

## Running the App
- `./gold-setup.py [--interval 1m|5m|15m|1h] [--account N] [--risk P] [--realtime] [--json] [--no-color] [--verbose]`
- `./gold-setup.py --serve [--port 8080]` — web dashboard; `--serve --daemon` to detach; `--stop` to stop
- `python3 tests/run_tests.py` — run the full test suite (no install required).

## Current Known Issues / Blockers
- Yahoo Finance occasionally rate-limits (HTTP 429); TwelveData fallback covers it. Both may fail if the sandbox network is restricted.
- Setup "probability" is a deterministic confluence estimate, not a statistical win rate (backtesting was removed).

## Important Instructions for AI Agents
1. **Source of Truth:** Project documentation and Git history are the absolute source of truth. Do not rely on conversational memory.
2. **Session Initialization:** At the start of every session or when switching AI providers, read `AI_CONTEXT.md`, `ARCHITECTURE.md`, and `TODO.md` first.
3. **Task Completion:** Update relevant documentation (`AI_CONTEXT.md`, `TODO.md`, `CHANGELOG.md`) whenever a feature, refactoring task, or milestone is completed.
4. **No Assumptions:** If requirements or technology choices are unspecified, mark them as "Not yet defined" or clarify with the user.

## Last Updated
- **Date:** August 20, 2026
- **Updated By:** AI Agent (v0.8.0 five strategies + Railway hosting; 24/7 Telegram alerts)