# Architecture

## 1. System Overview
- **Status:** Accepted (v0.6.0)
- **Description:** A zero-dependency Python CLI + web dashboard that fetches
  realtime XAU/USD data (Yahoo primary, TwelveData fallback), runs a
  market-structure analysis, and scans for two institutional scalping setups —
  Multi-Timeframe FVG + EMA Pullback and Session Liquidity Sweep & CHoCH —
  each gated by strict structural filters and a risk-to-reward floor. Setups
  are only emitted when they qualify. Data flows one-way from a price feed into
  a deterministic analysis pipeline with no persistence beyond a short-lived
  on-disk cache.

## 2. Component Breakdown
```text
Yahoo Finance chart API (GC=F) ── fallback ──► TwelveData (XAU/USD)
        │  HTTP GET (cached to ~/.cache/goldsetup, TTL per interval)
        ▼
goldsetup/data.py ── Candle list ──► goldsetup/indicators.py
                                            │  EMA, SMA, RSI, MACD, ATR, ADX,
                                            │  Bollinger, Stochastic, Donchian,
                                            │  pivots, swing levels, patterns
                                            ▼
                                    goldsetup/analysis.py
                                            │  structure analysis + unfilled-FVG
                                            │  and session-range helpers
                                            ▼
                                    goldsetup/scalper.py
                                            │  5m execution, 15m liquidity,
                                            │  1h macro filter; scan() enforces
                                            │  min R:R (1:2.5 FVG, 1:3 Sweep)
                                            ▼
                                    goldsetup/report.py (ANSI) / cli.py (JSON)
```
```text
                              goldsetup/web.py (ThreadingHTTPServer)
                                    │  /api/overview  /api/health
                                    │  /  → web/index.html (vanilla JS + SVG, no CDN)
                                    ▼
                              Browser dashboard (Live mode polls every 15s)
```

## 3. Data Flow
1. `cli.main()` parses args, resolves interval→default range.
2. `data.fetch_candles()` returns OHLCV candles for 5m (execution), 15m
   (liquidity/confluence) and 1h (macro filter) from Yahoo, falling back to
   TwelveData on failure; disk cache TTL (1m:30s, 5m:60s, 15m:180s, 1h:900s).
3. `analysis.analyse()` computes indicators + market-structure features and
   classifies the regime; `unfilled_fvgs()` and `session_range()` feed the
   strategies.
4. `scalper.scan()` runs Strategy 1 (FVG+EMA pullback) and Strategy 2 (session
   sweep + CHoCH); each returns a `Setup` only if all filters pass and the R:R
   floor is met.
5. Report is rendered to stdout as the structured scanner report or JSON.
6. `goldsetup/web.py` wraps the same pipeline in a JSON API and serves a
   self-contained dashboard UI.

## 4. Security & Authentication
- TwelveData API key (`TWELVEDATA_API_KEY`) is a data-provider credential, not
  a user secret; do not log it. All other requests are keyless.
- No user data is transmitted; candles are validated floats; no command is ever
  executed from market data.
- The dashboard binds to `127.0.0.1` by default and has no auth; expose it
  beyond localhost only behind a trusted proxy.

## 5. Deployment & Infrastructure
- Runs anywhere with Python ≥ 3.10; standard library only.
- Installed via `pip install .` (provides `gold-setup`) or run directly with
  `./gold-setup.py` / `python -m goldsetup.cli`.
- Network egress to `query1.finance.yahoo.com` and `api.twelvedata.com` are the
  only external dependencies.