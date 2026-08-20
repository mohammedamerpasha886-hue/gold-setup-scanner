from __future__ import annotations

import email.utils
import json
import os
import time
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36"
VALID_INTERVALS = ("1m", "5m", "15m", "1h")
VALID_RANGES = ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max")

TWELVEDATA_KEY = "9f179a78fb53412cba6181812d239689"
TWELVEDATA_URL = "https://api.twelvedata.com/time_series"
TWELVEDATA_SYMBOL = "XAU/USD"
TD_INTERVALS = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1h"}
TD_RANGE_OUTPUT = {"1d": 700, "5d": 2500, "1mo": 5000, "3mo": 5000, "6mo": 5000,
                   "1y": 5000, "2y": 5000, "5y": 5000, "max": 5000}

LAST_SOURCE = "twelvedata"

DEFAULT_CACHE_TTL = {
    "1m": 30,
    "5m": 60,
    "15m": 180,
    "1h": 900,
}

MAX_BAR_AGE_S = {
    "1m": 600,
    "5m": 900,
    "15m": 1800,
    "1h": 7200,
}

DEFAULT_RANGES = {"1m": "5d", "5m": "1d", "15m": "5d", "1h": "1mo"}
CONFIRM_RANGES = {"5m": "1d", "15m": "5d", "1h": "1mo"}
MTF_LADDER = ("1m", "5m", "15m", "1h")


@dataclass
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def dt(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp, tz=timezone.utc)


def higher_tf_period(candles: list[Candle]) -> int:
    diffs = [b.timestamp - a.timestamp for a, b in zip(candles, candles[1:]) if b.timestamp > a.timestamp]
    if not diffs:
        return 0
    return Counter(diffs).most_common(1)[0][0]


def last_completed_hi_index(hi: list[Candle], t: int, period: int) -> int:
    lo, hi_i = 0, len(hi) - 1
    result = -1
    while lo <= hi_i:
        mid = (lo + hi_i) // 2
        if hi[mid].timestamp + period <= t:
            result = mid
            lo = mid + 1
        else:
            hi_i = mid - 1
    return result


def _default_cache_dir() -> str:
    base = os.environ.get("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache"))
    path = os.path.join(base, "goldsetup")
    os.makedirs(path, exist_ok=True)
    return path


def _cache_path(cache_dir: str, interval: str, rng: str) -> str:
    return os.path.join(cache_dir, f"gc-f_{interval}_{rng}.json")


def _load_cache(cache_dir: str, interval: str, rng: str, ttl: int) -> list[Candle] | None:
    path = _cache_path(cache_dir, interval, rng)
    if not os.path.exists(path):
        return None
    if time.time() - os.path.getmtime(path) > ttl:
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return [Candle(**c) for c in data]
    except (OSError, ValueError, TypeError, KeyError):
        return None


def _save_cache(cache_dir: str, interval: str, rng: str, candles: list[Candle]) -> None:
    path = _cache_path(cache_dir, interval, rng)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump([c.__dict__ for c in candles], fh)
    except OSError:
        pass


def _parse_td_dt(stamp: str, offset_s: int = 0) -> int:
    try:
        ts = int(datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        ts = int(datetime.strptime(stamp, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    return ts + offset_s


def _td_server_ts(server_date: str | None) -> float:
    try:
        return email.utils.parsedate_to_datetime(server_date).timestamp()
    except (ValueError, TypeError):
        return 0.0


def _td_utc_offset_s(values: list[dict], server_date: str | None) -> int:
    """TwelveData may stamp bars in a non-UTC exchange timezone (this feed: +10h).

    Returns the offset to ADD to a raw stamp to convert it to UTC. Tests each
    plausible whole-hour offset and picks the one that makes the newest bar's
    corrected age fall inside 0..20 minutes (i.e. a fresh, live feed).
    Returns 0 when the feed is stale/frozen or the header is unavailable.
    """
    if not values or not server_date:
        return 0
    try:
        server_ts = email.utils.parsedate_to_datetime(server_date).timestamp()
        newest = _parse_td_dt(values[0]["datetime"])
    except (ValueError, TypeError, KeyError, IndexError):
        return 0
    best = None
    best_age = None
    for hour in range(-14, 15):
        off = hour * 3600
        age = server_ts - (newest + off)
        if -300 <= age <= 1200:  # forming bar (-300) .. completed bar (1200)
            if best_age is None or abs(age) < best_age:
                best, best_age = off, abs(age)
    return best if best is not None else 0


def _fetch_twelvedata(interval: str, rng: str) -> list[Candle]:
    td_int = TD_INTERVALS.get(interval)
    if not td_int:
        raise RuntimeError(f"TwelveData has no interval mapping for {interval}")
    outputsize = TD_RANGE_OUTPUT.get(rng, 5000)
    query = urllib.parse.urlencode({
        "symbol": TWELVEDATA_SYMBOL, "interval": td_int,
        "outputsize": outputsize, "apikey": TWELVEDATA_KEY,
    })
    req = urllib.request.Request(f"{TWELVEDATA_URL}?{query}",
                                 headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
            server_date = resp.headers.get("Date")
        if payload.get("status") != "ok" or "values" not in payload:
            raise RuntimeError(f"TwelveData error: {payload.get('message') or payload.get('error') or 'bad response'}")
        offset_s = _td_utc_offset_s(payload["values"], server_date)
        candles: list[Candle] = []
        for v in reversed(payload["values"]):  # values are newest-first; store chronological
            try:
                o, h, l, c = float(v["open"]), float(v["high"]), float(v["low"]), float(v["close"])
                vol = float(v.get("volume") or 0.0)
            except (KeyError, TypeError, ValueError):
                continue
            candles.append(Candle(_parse_td_dt(v["datetime"], offset_s), o, h, l, c, vol))
        if not candles:
            raise RuntimeError("TwelveData returned no usable candles")
        if server_date and candles[-1].timestamp > _td_server_ts(server_date) - MAX_BAR_AGE_S.get(interval, 3600):
            return candles
        time.sleep(1)
    newest_ts = candles[-1].timestamp
    age_h = (_td_server_ts(server_date) - newest_ts) / 3600.0 if server_date else float("inf")
    raise RuntimeError(
        f"TwelveData kept returning stale data (newest bar {age_h:.1f}h old) — "
        "feed frozen or demo key capped; retry later")


def _fetch_remote(interval: str, rng: str) -> list[Candle]:
    global LAST_SOURCE
    candles = _fetch_twelvedata(interval, rng)
    LAST_SOURCE = "twelvedata"
    return candles


def fetch_candles(interval: str = "1d", rng: str = "1y", cache: bool = True,
                  cache_dir: str | None = None, force: bool = False) -> list[Candle]:
    if interval not in VALID_INTERVALS:
        raise ValueError(f"interval must be one of {VALID_INTERVALS}")
    if rng not in VALID_RANGES:
        raise ValueError(f"range must be one of {VALID_RANGES}")

    cache_dir = cache_dir or _default_cache_dir()
    ttl = DEFAULT_CACHE_TTL.get(interval, 300)
    if cache and not force:
        cached = _load_cache(cache_dir, interval, rng, ttl)
        if cached is not None:
            return cached

    candles = _fetch_remote(interval, rng)
    if cache:
        _save_cache(cache_dir, interval, rng, candles)
    return candles