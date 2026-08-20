from unittest.mock import patch

from goldsetup import telegram
from goldsetup.telegram import format_setup_message, format_no_setup, resolve_chat_id, send_message
from goldsetup.setup import Setup


def _fake_setup():
    return Setup(
        direction="BUY",
        confidence=0.6,
        entry=4539.7,
        stop=4534.1,
        take_profit=4552.3,
        rr=3.45,
        strategy="Multi-Timeframe FVG + EMA Pullback",
        probability=0.6,
        evidence=["1H macro filter: EMA20>EMA50",
                  "5M unfilled fvg-bullish at 4525.0-4527.0",
                  "Pullback tapped 5M EMA20 with RSI re-crossing 50"],
        rationale=["LONG via Multi-Timeframe FVG + EMA Pullback"],
        position_oz=2.0,
        position_lots=0.02,
        risk_amount=100.0,
        reward_amount=345.0,
        confirmed=True,
        confirm_bias="BUY",
    )


def test_format_setup_message_includes_full_setup():
    msg = format_setup_message(_fake_setup(), source="yahoo", utc="12:00:00")
    assert "XAU/USD TRADE SETUP FOUND" in msg
    assert "Multi-Timeframe FVG + EMA Pullback" in msg
    assert "LONG" in msg
    assert "4,539.70" in msg and "4,534.10" in msg and "4,552.30" in msg
    assert "1:3.45" in msg
    assert "0.020 lots" in msg


def test_format_no_setup():
    msg = format_no_setup(4544.5, utc="12:00:00", source="yahoo")
    assert "no qualifying setup" in msg
    assert "4,544.50" in msg


def test_send_message_uses_config_and_api():
    with patch.object(telegram, "_call", return_value={"ok": True}) as call:
        assert send_message("hello", token="tok", chat="123") is True
        call.assert_called_once_with("tok", "sendMessage",
                                     {"chat_id": "123", "text": "hello"})


def test_send_message_requires_credentials():
    with patch.object(telegram, "bot_token", return_value=None), \
            patch.object(telegram, "chat_id", return_value=None):
        try:
            send_message("hi")
            assert False, "expected RuntimeError"
        except RuntimeError as e:
            assert "token and chat id" in str(e)


def test_resolve_chat_id_from_updates():
    updates = {"ok": True, "result": [{"message": {"chat": {"id": 987654}}}]}
    with patch.object(telegram, "_call", return_value=updates):
        assert resolve_chat_id("tok") == "987654"


def test_resolve_chat_id_returns_none_when_no_chat():
    with patch.object(telegram, "_call", return_value={"ok": True, "result": []}):
        assert resolve_chat_id("tok") is None