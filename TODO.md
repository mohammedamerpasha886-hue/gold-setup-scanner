# Task Backlog (TODO)

## Active Milestone: Institutional Scalping Scanner (v0.6.0)
- [x] Removed all legacy strategy logic (`strategies.py`, `advisor.py`, `generate_setups`/`aggregate`/`WEIGHTS`)
- [x] Strategy 1: Multi-Timeframe FVG + EMA Pullback (1H EMA20/50 filter, 5M unfilled-FVG tap + EMA20, RSI reset, structural SL, 15M/1H liquidity TP, min 1:2.5 R:R)
- [x] Strategy 2: London/NY Session Liquidity Sweep & CHoCH (session time filter, sweep + CHoCH, discount/premium retracement entry, wick-tip SL, range-edge TP, min 1:3 R:R)
- [x] `unfilled_fvgs()` + `session_range()` helpers in `analysis.py`
- [x] Exact structured scanner report format (banner, Strategy/Direction/Timeframe, Entry/SL/TP, R:R, Reason/Confluence) + JSON payload
- [x] Web dashboard updated for the scanner payload (Setup Scan, Market Snapshot, LONG/SHORT)
- [x] Test suite rewritten for the scanner (48 passing)
- [ ] Optional Gemini/LLM narrative commentary (requires an API key from the user)
- [ ] High-impact news-window filter (FOMC/NFP) around the session window
- [ ] Optional `pip install -e .`/Docker packaging for broader portability
- [ ] Multi-user/password protection for the dashboard