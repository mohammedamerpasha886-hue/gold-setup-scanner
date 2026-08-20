from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36"
SYMBOL = "GC=F"
BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}"
VALID_INTERVALS = ("1m", "5m", "15m", "1h")
VALID_RANGES = ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max")

TWELVEDATA_KEY = os.environ.get("TWELVEDATA_API_KEY", "d25b1c102bb147059449547d724cd9ec")
TWELVEDATA_URL = "https://api.twelvedata.com/time_series"
TWELVEDATA_SYMBOL = "XAU/USD"
TD_INTERVALS = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1h"}
TD_RANGE_OUTPUT = {"1d": 700, "5d": 2500, "1mo": 5000, "3mo": 5000, "6mo": 5000,
                   "1y": 5000, "2y": 5000, "5y": 5000, "max": 5000}

LAST_SOURCE = "yahoo"

DEFAULT_CACHE_TTL = {
    "1m": 30,
    "5m": 60,
    "15m": 180,
    "1h": 900,
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


def _fetch_yahoo(interval: str, rng: str) -> list[Candle]:
    url = f"{BASE_URL.format(SYMBOL)}?range={rng}&interval={interval}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)

    result = payload["chart"]["result"]
    if not result:
        raise RuntimeError("No chart data returned")
    meta = result[0]["meta"]
    timestamps = result[0].get("timestamp") or []
    quote = result[0]["indicators"]["quote"][0]

    candles: list[Candle] = []
    for i, ts in enumerate(timestamps):
        try:
            o = quote["open"][i]
            h = quote["high"][i]
            l = quote["low"][i]
            c = quote["close"][i]
            v = quote["volume"][i]
        except (TypeError, IndexError, KeyError):
            continue
        if None in (o, h, l, c):
            continue
        candles.append(Candle(int(ts), float(o), float(h), float(l), float(c), float(v or 0.0)))

    if not candles:
        raise RuntimeError("Chart payload contained no usable candles")
    return candles


def _parse_td_dt(stamp: str) -> int:
    try:
        return int(datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        return int(datetime.strptime(stamp, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


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
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("status") != "ok" or "values" not in payload:
        raise RuntimeError(f"TwelveData error: {payload.get('message') or payload.get('error') or 'bad response'}")
    candles: list[Candle] = []
    for v in payload["values"]:  # newest first
        try:
            o, h, l, c = float(v["open"]), float(v["high"]), float(v["low"]), float(v["close"])
            vol = float(v.get("volume") or 0.0)
        except (KeyError, TypeError, ValueError):
            continue
        candles.append(Candle(_parse_td_dt(v["datetime"]), o, h, l, c, vol))
    if not candles:
        raise RuntimeError("TwelveData returned no usable candles")
    return candles


def _fetch_remote(interval: str, rng: str) -> list[Candle]:
    global LAST_SOURCE
    try:
        candles = _fetch_yahoo(interval, rng)
        LAST_SOURCE = "yahoo"
        return candles
    except Exception as yahoo_err:
        try:
            candles = _fetch_twelvedata(interval, rng)
            LAST_SOURCE = "twelvedata"
            return candles
        except Exception as td_err:
            raise RuntimeError(
                f"Yahoo failed ({yahoo_err}); TwelveData fallback failed ({td_err})") from td_err


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