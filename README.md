# MyApp — XAU/USD Institutional Setup Scanner

A zero-dependency Python CLI + web dashboard that fetches **realtime** gold
(XAU/USD) price data and runs **two institutional-grade scalping strategies**
— a Multi-Timeframe FVG + EMA Pullback continuation trade and a London/NY
Session Liquidity Sweep & CHoCH reversal trade. Every scan returns a concrete
setup (entry, stop-loss, take-profit, R:R, sizing) when a candidate satisfies
its strict structural filters and risk-to-reward floor.

**Warning: Signals are technical-analysis only. The "probability" is a
confluence estimate, not a guarantee, and not financial advice.**

## Quick Start

```bash
python3 tests/run_tests.py            # run the test suite (no deps required)
./gold-setup.py                       # default: 5m scan, structured report
./gold-setup.py --interval 15m        # timeframe: 1m / 5m / 15m / 1h
./gold-setup.py --realtime            # bypass cache, fetch the latest bar
./gold-setup.py --json                # machine-readable output
./gold-setup.py --verbose             # show every evidence line
./gold-setup.py --serve               # web dashboard at http://127.0.0.1:8080
./gold-setup.py --watch --daemon      # 24/7 scanner → Telegram alerts
./gold-setup.py --help                # all options
```

## Telegram Alerts (24/7)

Run the scanner continuously and push the **full trade setup** to Telegram the
moment a qualifying setup appears:

```bash
./gold-setup.py --telegram-setup --bot-token BOT_TOKEN --chat-id CHAT_ID   # one-time
./gold-setup.py --telegram-test        # verify the channel works
./gold-setup.py --watch --daemon       # start 24/7 scanner in the background
./gold-setup.py --stop-watch           # stop it
```

- The bot token comes from [@BotFather](https://t.me/BotFather); the chat id can
  be auto-resolved (message your bot once, then run `--telegram-setup` without
  `--chat-id`).
- `--watch` scans every `--watch-interval` seconds (default 300) and alerts with
  the full setup (strategy, direction, entry/SL/TP, R:R, reason, position size).
- Duplicate alerts for the same setup are suppressed for 30 minutes.
- A heartbeat is sent every 4 hours when nothing qualifies, so you know the
  scanner is alive.
- Credentials are stored in `~/.cache/goldsetup/telegram.json` (or set
  `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` env vars). The file is gitignored.

## Host on Railway (24/7 web + alerts)

The repo is ready to deploy to [Railway](https://railway.app) so the dashboard
**and** the Telegram watcher run 24/7 on a hosted server (no need to keep your
own device on):

1. Push this repo to GitHub (already done for the public
   `gold-setup-scanner` repo).
2. In the Railway dashboard: **New Project → Deploy from GitHub repo** → pick the
   repo. Railway reads `Procfile` + `railway.json` automatically (no build step,
   stdlib-only).
3. Add these **Variables** in the service settings:
   - `TWELVEDATA_API_KEY` — your real key (optional; the bundled demo key is the
     fallback, switch it later)
   - `TELEGRAM_BOT_TOKEN` — your bot token (from @BotFather)
   - `TELEGRAM_CHAT_ID` — your chat id
   - `ACCOUNT` / `RISK_PCT` / `WATCH_INTERVAL` — optional sizing/tuning knobs
4. Deploy. The service starts `python3 gold-setup.py --serve --host 0.0.0.0
   --port $PORT --watch-alerts`, so the dashboard is served **and** the setup
   watcher pushes qualifying setups to Telegram. Railway checks `/api/health`.

Railway also lets you attach a domain (Settings → Networking → Generate Domain)
for a public dashboard URL.

## Data

- **Sole source:** TwelveData `XAU/USD` (gold spot). Set the key with
  `TWELVEDATA_API_KEY` (a default demo key is bundled). Use a real key for
  live data — the demo key returns delayed/capped data.
- Results are cached to disk (`~/.cache/goldsetup`) with per-timeframe TTLs
  (1m 30s, 5m 60s, 15m 3m, 1h 15m). `--realtime` bypasses the cache.

## What It Analyses (every single run)

The engine computes the full tape and prints the regime it sees:

| Group | Details |
| --- | --- |
| **Moving averages** | EMA 9/21/50/200 + SMA 20/50/200, stack state |
| **Volatility** | ATR(14), Bollinger Bands width/position |
| **Momentum** | RSI(14) + RSI divergence, MACD, Stochastic, ADX/DMI |
| **Fibonacci** | 0.236–1.618 retracements/extensions off the last swing |
| **Levels** | clustered support/resistance from swings + pivot points |
| **Supply/demand** | zones behind impulsive ATR moves, proximity check |
| **Liquidity** | buy-side/sell-side liquidity pools, equal highs/lows |
| **Structure** | BoS (break of structure), CHoCH (change of character) |
| **Breakouts** | Donchian-range break vs **fakeout** (wick, close-back-inside) |
| **Sweeps** | stop-hunts through liquidity + close back (ICT) |
| **ICT** | fair-value gaps, order blocks |

## How a Setup Is Chosen

The scanner runs five institutional scalping strategies (executed on 5m candles)
and returns every setup that satisfies all of its filters and its R:R floor.
Unlike the old always-return-a-trade advisor, **no setup is forced**: if nothing
qualifies, the report says so and shows the market snapshot instead.

**Strategy 1 — Multi-Timeframe FVG + EMA Pullback (continuation):**
1. 1H macro filter: EMA20 > EMA50 = LONG bias, EMA20 < EMA50 = SHORT bias.
2. 5M: an **active unfilled FVG**; the pullback taps the gap and touches/crosses
   the 5M EMA20.
3. RSI(14) reset: dipped below 50 on the pullback, crossed back above (longs;
   mirrored for shorts).
4. Stop just below the swing low of the local FVG/OB zone (or swing high for
   shorts) with an ATR buffer; target the nearest 15M/1H structural liquidity
   high/low. **Discard if R:R < 1:2.5.**

**Strategy 2 — London/NY Session Liquidity Sweep & CHoCH (reversal):**
1. Active only 08:00–10:00 UTC (London) or 13:00–16:00 UTC (NY overlap).
2. A wick sweeps the Asian/early-session swing high/low and closes back inside
   (stop hunt).
3. CHoCH: a sharp 5M close breaks the nearest internal micro-structure opposite
   the sweep.
4. Enter on the retracement into the discount/premium (50%) zone of the breakout
   candle; stop beyond the extreme wick tip; target the opposite side of the
   intraday range. **Discard if R:R < 1:3.**

**Strategy 3 — Order Block Retest + RSI Divergence (reversal):**
1. 5M RSI divergence: a lower low with a higher RSI print (bullish; mirrored).
2. Price retests a recent **institutional order block** from the wrong side.
3. Stop beyond the block's extreme (or the nearest swing) + ATR buffer; target
   the nearest 15M/1H liquidity pool. **Discard if R:R < 1:2.5.**

**Strategy 4 — Asian Range Breakout (London Open, momentum):**
1. Active 07:00–10:00 UTC; the Asian range = the current day's 00:00–06:59
   high/low.
2. A candle closes **outside** the range with ADX ≥ 15 and RSI beyond 50.
3. Entry on the retracement into the fresh breakout FVG; stop below the broken
   range edge; target a measured move equal to the range width.
   **Discard if R:R < 1:2.**

**Strategy 5 — Supply/Demand Zone Flip + Retest (continuation):**
1. A high-strength **demand/supply zone** is retested from the flipped side.
2. RSI ≥ 40 (longs) with bullish structure or RSI divergence (mirrored for
   shorts).
3. Stop beyond the zone + ATR buffer; target nearest 15M/1H liquidity.
   **Discard if R:R < 1:2.5.**

Each qualifying setup is sized as `oz = (balance × risk%) ÷ (entry − stop)`,
reported in lots (1 lot = 100 oz) with risk/reward USD.

## Web Dashboard

`./gold-setup.py --serve` (or `python -m goldsetup.web`) starts a
zero-dependency dashboard at `http://127.0.0.1:8080` (override with
`--host`/`--port`). Pure-Python `http.server` + self-contained vanilla
JS/SVG frontend — no CDN, no npm.

```bash
./gold-setup.py --serve                    # foreground; Ctrl+C to stop
./gold-setup.py --serve --daemon           # detach: keeps running after the shell exits
./gold-setup.py --stop                     # stop the detached dashboard
```

PID/log: `~/.cache/goldsetup/dashboard.{pid,log}`. LAN access:
`--host 0.0.0.0` (no auth — keep it behind a trusted network).

Features:
- **Setup Scan** card: each qualifying setup with direction, strategy, entry/
  SL/TP, R:R, sizing, and the full evidence list.
- **Market Snapshot** strip: regime, structure, ADX/RSI, EMA, support/
  resistance, fib, breakout/fakeout, sweep, BoS/CHoCH chips.
- Candlestick chart with the first setup's entry/stop/target overlaid.
- **Live mode** button: fetch fresh data every 15s; auto-refresh 60s otherwise.

API (same-origin JSON): `/api/overview`, `/api/health`.

## CLI Reference

| Option | Default | Description |
| --- | --- | --- |
| `--interval` | `5m` | `1m`, `5m`, `15m`, or `1h` candles |
| `--range` | auto | history range (`1d`, `5d`, `1mo`, ...) |
| `--account` | `10000` | account balance for position sizing (USD) |
| `--risk` | `1.0` | % of account risked per trade |
| `--realtime` | off | bypass cache, fetch the latest data |
| `--serve` | off | start the web dashboard (uses `--host`/`--port`) |
| `--host`, `--port` | `127.0.0.1`, `8080` | dashboard bind address |
| `--daemon` | off | with `--serve`: detach and run in the background |
| `--stop` | off | stop the running dashboard daemon |
| `--log`, `--pid` | auto | log/pid file paths for the daemon |
| `--json` | off | emit JSON instead of the colored report |
| `--no-color` | off | disable ANSI colors |
| `--no-cache` | off | force a fresh fetch (same as `--realtime`) |
| `--cache-dir` | auto | override the on-disk cache location |
| `--verbose` | off | print every evidence line |
| `--watch` | off | 24/7 scanner that alerts on Telegram |
| `--watch-interval` | `300` | seconds between scans in `--watch` mode |
| `--stop-watch` | off | stop the running watch daemon |
| `--telegram-setup` | off | save bot token + chat id to the cache dir |
| `--telegram-test` | off | send a Telegram test message |
| `--bot-token`, `--chat-id` | — | Telegram credentials (with `--telegram-setup`) |

## Project Layout

```text
goldsetup/
├── cli.py         # argparse entry point (fetch 5m/15m/1h, run scan, report)
├── data.py        # TwelveData fetcher, disk cache, shared constants
├── indicators.py  # technical indicators (stdlib only)
├── analysis.py    # market-structure engine + unfilled-FVG / session-range helpers
├── scalper.py     # the two institutional scalping strategies + scan()
├── setup.py       # Setup dataclass, position sizing
├── web.py         # zero-dependency HTTP dashboard server + JSON API
└── report.py      # structured scanner report (terminal + JSON rendering)
web/index.html     # self-contained dashboard UI (vanilla JS + SVG)
tests/             # zero-dependency test runner + unit tests
```

See `ARCHITECTURE.md` for design details and `DECISIONS.md` for the ADRs.