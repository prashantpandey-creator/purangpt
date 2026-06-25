"""Telegram connector — posts to a channel/chat via the Bot API. mode=auto.

Credentials (from the vault): {"bot_token": "...", "chat_id": "@purangpt" or -100...}.
Posting to your own channel via your own bot is fully allowed automation.

publish() returns the RAW Telegram response; the worker passes it through
tools.connector_envelope to get a normalized {external_id, external_url}. This
connector deliberately does not parse the response shape itself (that lives in
the tested envelope tool).
"""
from __future__ import annotations

import logging
from typing import Dict

import requests

from growth_engine.connectors.base import Connector, AUTO

logger = logging.getLogger(__name__)
_API = "https://api.telegram.org/bot{token}/{method}"
_TIMEOUT = 30


class TelegramConnector(Connector):
    name = "telegram"
    mode = AUTO

    def _call(self, token: str, method: str, payload: Dict) -> Dict:
        url = _API.format(token=token, method=method)
        resp = requests.post(url, json=payload, timeout=_TIMEOUT)
        # Telegram returns a JSON body with ok:true/false on both 2xx and 4xx.
        try:
            return resp.json()
        except ValueError:
            return {"ok": False, "error_code": resp.status_code,
                    "description": resp.text[:200]}

    def validate(self, keys: Dict) -> bool:
        """getMe is a cheap, side-effect-free auth ping."""
        token = keys.get("bot_token")
        if not token:
            return False
        try:
            return self._call(token, "getMe", {}).get("ok", False)
        except Exception as e:
            logger.warning(f"telegram validate failed: {e}")
            return False

    def publish(self, asset: Dict, keys: Dict) -> Dict:
        """Send asset['text'] (and asset['image_url'] if present) to the chat.

        Returns the raw Telegram response dict. Raises on a transport error.
        """
        token = keys["bot_token"]
        chat_id = keys["chat_id"]
        text = asset.get("text", "")
        image_url = asset.get("image_url")

        if image_url:
            payload = {"chat_id": chat_id, "photo": image_url, "caption": text}
            return self._call(token, "sendPhoto", payload)
        payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": False}
        return self._call(token, "sendMessage", payload)
