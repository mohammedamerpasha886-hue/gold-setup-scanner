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


def test_fetch_falls_back_to_twelvedata_on_yahoo_failure():
    from unittest.mock import patch

    candles = data.Candle(1700000000, 1.0, 2.0, 0.5, 1.5, 10.0)
    with patch.object(data, "_fetch_yahoo", side_effect=RuntimeError("boom")), \
            patch.object(data, "_fetch_twelvedata", return_value=[candles]):
        out = data._fetch_remote("5m", "1d")
    assert out[0].close == 1.5
    assert data.LAST_SOURCE == "twelvedata"