from goldsetup import data


def test_twelvedata_interval_mapping():
    assert data.TD_INTERVALS["1m"] == "1min"
    assert data.TD_INTERVALS["5m"] == "5min"
    assert data.TD_INTERVALS["15m"] == "15min"
    assert data.TD_INTERVALS["1h"] == "1h"


def test_parse_td_datetime():
    ts = data._parse_td_dt("2026-08-20 19:50:00")
    assert ts > 1700000000


def test_valid_intervals_scoped():
    assert set(data.VALID_INTERVALS) == {"1m", "5m", "15m", "1h"}
    assert "1d" not in data.VALID_INTERVALS
    assert "1wk" not in data.VALID_INTERVALS


def test_mtf_ladder_no_higher_timeframes():
    assert data.MTF_LADDER == ("1m", "5m", "15m", "1h")


def test_fetch_candles_uses_cache_and_source_flag():
    from unittest.mock import patch

    candles = data.Candle(1700000000, 1.0, 2.0, 0.5, 1.5, 10.0)
    with patch.object(data, "_fetch_remote", return_value=[candles]) as mock:
        out = data.fetch_candles("5m", "1d", cache=False)
    mock.assert_called_once()
    assert out[0].close == 1.5


def test_fetch_uses_twelvedata_only():
    from unittest.mock import patch

    candles = data.Candle(1700000000, 1.0, 2.0, 0.5, 1.5, 10.0)
    with patch.object(data, "_fetch_twelvedata", return_value=[candles]) as mock:
        out = data._fetch_remote("5m", "1d")
    mock.assert_called_once()
    assert out[0].close == 1.5
    assert data.LAST_SOURCE == "twelvedata"


def test_no_yahoo_module():
    assert not hasattr(data, "_fetch_yahoo")


def test_td_offset_calibration_live_feed():
    import email.utils

    server = email.utils.format_datetime(
        email.utils.parsedate_to_datetime("Thu, 20 Aug 2026 13:08:15 GMT"), usegmt=True)
    live = [{"datetime": "2026-08-20 23:05:00"}]
    assert data._td_utc_offset_s(live, server) == -36000
    stale = [{"datetime": "2026-08-18 12:30:00"}]
    assert data._td_utc_offset_s(stale, server) == 0
    assert data._td_utc_offset_s(live, None) == 0


def test_td_parse_applies_offset():
    ts_no_offset = data._parse_td_dt("2026-08-20 22:50:00")
    ts_utc = data._parse_td_dt("2026-08-20 22:50:00", -36000)
    assert ts_utc == ts_no_offset - 36000


def test_fetch_twelvedata_chronological_order_and_fresh():
    import json as _json
    from datetime import datetime, timezone
    from unittest.mock import patch

    class FakeHeaders:
        def __init__(self, date):
            self._date = date

        def get(self, key, default=None):
            return self._date if key == "Date" else default

    class FakeResp:
        def __init__(self, body, date):
            self._body = body
            self.headers = FakeHeaders(date)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return self._body

    values = [
        {"datetime": "2026-08-20 23:05:00", "open": "1", "high": "2",
         "low": "0.5", "close": "4475.47", "volume": "0"},
        {"datetime": "2026-08-20 23:00:00", "open": "1", "high": "2",
         "low": "0.5", "close": "4474.01", "volume": "0"},
        {"datetime": "2026-08-20 22:55:00", "open": "1", "high": "2",
         "low": "0.5", "close": "4472.00", "volume": "0"},
    ]
    payload = {"status": "ok", "values": values}
    resp = FakeResp(_json.dumps(payload).encode(), "Thu, 20 Aug 2026 13:08:15 GMT")
    with patch.object(data.urllib.request, "urlopen", return_value=resp):
        candles = data._fetch_twelvedata("5m", "1d")
    assert len(candles) == 3
    assert candles[0].timestamp < candles[-1].timestamp
    assert candles[0].close == 4472.00
    assert candles[-1].close == 4475.47
    newest_utc = datetime.fromtimestamp(candles[-1].timestamp, tz=timezone.utc)
    assert newest_utc.strftime("%H:%M") == "13:05"


def test_fetch_twelvedata_rejects_frozen_feed():
    import json as _json
    from unittest.mock import patch

    class FakeHeaders:
        def __init__(self, date):
            self._date = date

        def get(self, key, default=None):
            return self._date if key == "Date" else default

    class FakeResp:
        def __init__(self, body, date):
            self._body = body
            self.headers = FakeHeaders(date)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return self._body

    values = [{"datetime": "2026-08-18 12:30:00", "open": "1", "high": "2",
               "low": "0.5", "close": "4394.63", "volume": "0"}]
    payload = {"status": "ok", "values": values}
    resp = FakeResp(_json.dumps(payload).encode(), "Thu, 20 Aug 2026 13:08:15 GMT")
    try:
        with patch.object(data.urllib.request, "urlopen", return_value=resp):
            data._fetch_twelvedata("5m", "1d")
    except RuntimeError as e:
        assert "stale" in str(e).lower()
    else:
        raise AssertionError("expected RuntimeError for frozen feed")