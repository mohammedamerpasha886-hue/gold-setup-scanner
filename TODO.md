# Task Backlog (TODO)

## Active Milestone: 24/7 Telegram Alerts (v0.7.0)
- [x] `telegram.py`: bot API integration (send_message, resolve_chat_id, config in cache dir, env overrides)
- [x] `watch.py`: continuous scanner loop + dedup (30-min cooldown) + 4h heartbeat
- [x] CLI: `--watch`, `--watch-interval`, `--watch --daemon`, `--stop-watch`, `--telegram-setup`, `--telegram-test`
- [x] Full setup formatted in Telegram alerts (strategy/direction/entry/SL/TP/R:R/reason/size)
- [x] Tests for telegram + watch integration (54 passing)
- [x] Published publicly on GitHub (SSH deploy; TwelveData key removed from repo)

## Backlog / Next
- [ ] Provide Telegram bot token + chat id from @BotFather to enable live alerts
- [ ] High-impact news-window filter (FOMC/NFP) around the session window
- [ ] Optional Gemini/LLM narrative commentary (requires an API key from the user)
- [ ] Optional `pip install -e .`/Docker packaging for broader portability
- [ ] Multi-user/password protection for the dashboard