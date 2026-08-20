from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from .data import USER_AGENT, _default_cache_dir
from .setup import Setup

API = "https://api.telegram.org/bot{token}/{method}"
CONFIG_FILE = "telegram.json"
MAX_MSG = 4096


def config_path() -> str:
    return os.path.join(_default_cache_dir(), CONFIG_FILE)


def load_config() -> dict:
    path = config_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
        return {k: v for k, v in cfg.items() if isinstance(v, str) and v}
    except (OSError, ValueError):
        return {}


def save_config(bot_token: str | None = None, chat_id: str | None = None) -> dict:
    cfg = load_config()
    if bot_token:
        cfg["bot_token"] = bot_token
    if chat_id:
        cfg["chat_id"] = chat_id
    with open(config_path(), "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
    return cfg


def bot_token() -> str | None:
    return os.environ.get("TELEGRAM_BOT_TOKEN") or load_config().get("bot_token")


def chat_id() -> str | None:
    return os.environ.get("TELEGRAM_CHAT_ID") or load_config().get("chat_id")


def _call(token: str, method: str, params: dict) -> dict:
    url = API.format(token=token, method=method)
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def resolve_chat_id(token: str) -> str | None:
    """Return the chat_id of the most recent update (the user who messaged the bot)."""
    res = _call(token, "getUpdates", {"limit": 1, "timeout": 0})
    if not res.get("ok"):
        raise RuntimeError(res.get("description", "getUpdates failed"))
    updates = res.get("result", [])
    for u in reversed(updates):
        msg = u.get("message") or u.get("channel_post") or {}
        if "chat" in msg and msg["chat"].get("id") is not None:
            return str(msg["chat"]["id"])
    return None


def send_message(text: str, token: str | None = None, chat: str | None = None) -> bool:
    token = token or bot_token()
    chat = chat or chat_id()
    if not token or not chat:
        raise RuntimeError("Telegram bot token and chat id are required "
                           "(set TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID or run --telegram-setup)")
    if len(text) > MAX_MSG:
        text = text[: MAX_MSG - 3] + "..."
    res = _call(token, "sendMessage", {"chat_id": chat, "text": text})
    if not res.get("ok"):
        raise RuntimeError(res.get("description", "sendMessage failed"))
    return True


def format_setup_message(s: Setup, source: str = "twelvedata", utc: str = "") -> str:
    dir_str = "LONG" if s.direction == "BUY" else "SHORT"
    lines = [
        f"🚀 XAU/USD TRADE SETUP FOUND [{utc}]",
        f"📊 Strategy : {s.strategy}",
        f"🎯 Direction: {dir_str}",
        f"⏱ Timeframe : 5m / 15m / 1H",
        "",
        f"▪️ Entry      : {s.entry:,.2f}",
        f"🛑 Stop Loss  : {s.stop:,.2f}",
        f"✅ Take Profit: {s.take_profit:,.2f}",
        f"⚖️ R:R        : 1:{s.rr:.2f}",
        "",
        f"💡 Reason: {'; '.join(s.evidence[:3])}",
        f"📦 Size: {s.position_lots:.3f} lots ({s.position_oz:,.1f} oz) | "
        f"Risk {s.risk_amount:,.2f} USD → Reward {s.reward_amount:,.2f} USD",
        f"🧷 Probability: {s.probability:.0%} (confluence estimate, not a guarantee)",
        "",
        "⚠️ Not financial advice. Trade with strict risk management.",
        f"🛰 data source: {source}",
    ]
    return "\n".join(lines)


def format_no_setup(price: float, utc: str = "", source: str = "twelvedata") -> str:
    return (
        f"🔎 XAU/USD scan [{utc}] — no qualifying setup (R:R floors not met).\n"
        f"Last {price:,.2f} · data {source}"
    )