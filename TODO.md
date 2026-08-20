# Task Backlog (TODO)

## Active Milestone: 5 Strategies + Railway Hosting (v0.8.0)
- [x] Strategy 3: Order Block Retest + RSI Divergence (reversal, min 1:2.5)
- [x] Strategy 4: Asian Range Breakout on the London Open (momentum, min 1:2)
- [x] Strategy 5: Supply/Demand Zone Flip + Retest (continuation, min 1:2.5)
- [x] All strategies run in `scan()` and feed the Telegram watcher + dashboard
- [x] `--watch-alerts`: embedded watcher thread inside `--serve` (hosted 24/7 alerts)
- [x] Railway support: `Procfile`, `railway.json`, `$PORT` env, `/api/health`
- [x] TwelveData demo key bundled again (env-overridable for Railway)
- [x] Tests for all new strategies (60 passing)
- [ ] Deploy the repo to Railway (needs the user's Railway account/token)

## Completed Milestones
- [x] v0.7.0 24/7 Telegram alerts (watch.py, telegram.py, cache-dir config)
- [x] v0.6.0 institutional scalping scanner (2 strategies, exact report format)
- [x] Published publicly on GitHub (SSH deploy; key removed from repo)

## Backlog / Next
- [ ] Switch the bundled demo key to a real TwelveData key (env var / data.py)
- [ ] High-impact news-window filter (FOMC/NFP) around the session window
- [ ] Optional Gemini/LLM narrative commentary (requires an API key)
- [ ] Multi-user/password protection for the dashboard