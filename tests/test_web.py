import json
import threading
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from goldsetup import data
from goldsetup.web import Handler, build_overview
from tests.conftest import candles_from_closes


def _synthetic_candles():
    return candles_from_closes([100.0 + 1.5 * i for i in range(150)])


def _start_server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, httpd.server_address[1]


def test_build_overview_shape():
    with patch.object(data, "fetch_candles", return_value=_synthetic_candles()):
        payload = build_overview("5m", 10000.0, 1.0, use_cache=False)
    assert payload["symbol"] == "GC=F"
    assert payload["interval"] == "5m"
    assert len(payload["candles"]) == 150
    assert "analysis" in payload
    assert payload["analysis"]["regime"] in ("trend-up", "trend-down", "range", "breakout", "reversal", "volatile")
    assert "strategies_scanned" in payload
    assert isinstance(payload["setups"], list)
    for s in payload["setups"]:
        assert s["direction"] in ("LONG", "SHORT")
        assert 0.0 <= s["probability"] <= 1.0
        assert s["strategy"]
        assert s["entry"] and s["stop"] and s["take_profit"]
        assert "1:" in s["risk_to_reward"]
        assert isinstance(s["evidence"], list)


def test_endpoints_serve_html_and_json():
    httpd, port = _start_server()
    try:
        import urllib.request

        def get(path):
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=10) as r:
                return r.status, r.read()

        status, body = get("/")
        assert status == 200
        assert b"XAU/USD" in body and b"candleSVG" in body

        with patch.object(data, "fetch_candles", return_value=_synthetic_candles()):
            status, body = get("/api/overview?interval=5m")
            assert status == 200
            d = json.loads(body)
            assert d["last"] == 100.0 + 1.5 * 149

        status, body = get("/api/health")
        assert status == 200
        assert json.loads(body)["status"] == "ok"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_unknown_path_returns_404():
    httpd, port = _start_server()
    try:
        import urllib.request

        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/nope", timeout=10)
            assert False, "expected HTTPError"
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_stop_daemon_missing_pid_returns_false():
    from goldsetup import web

    assert web.stop_daemon("/tmp/does-not-exist-goldsetup.pid") is False