"""X / Twitter connector — posts a tweet via X API v2. mode=auto.

Posting requires OAuth 1.0a user context (an app key/secret + the posting user's
access token/secret). Credentials (from the vault):
  {"consumer_key","consumer_secret","access_token","access_token_secret","handle"}
Posting to your own account is allowed automation (this is NOT scraping or
automated engagement on others' content).

publish() returns the RAW X response; the worker normalizes via
tools.connector_envelope. Media upload (v1.1 endpoint) is a Phase 2 concern —
this Phase-1 connector posts text only.
"""
from __future__ import annotations

import logging
from typing import Dict

import requests
from requests_oauthlib import OAuth1

from growth_engine.connectors.base import Connector, AUTO

logger = logging.getLogger(__name__)
_TWEETS_URL = "https://api.x.com/2/tweets"
_ME_URL = "https://api.x.com/2/users/me"
_TIMEOUT = 30


class XTwitterConnector(Connector):
    name = "x_twitter"
    mode = AUTO

    def _auth(self, keys: Dict) -> OAuth1:
        return OAuth1(
            keys["consumer_key"],
            keys["consumer_secret"],
            keys["access_token"],
            keys["access_token_secret"],
        )

    def validate(self, keys: Dict) -> bool:
        """GET /2/users/me — confirms the OAuth1 tokens authenticate."""
        try:
            resp = requests.get(_ME_URL, auth=self._auth(keys), timeout=_TIMEOUT)
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"x_twitter validate failed: {e}")
            return False

    def publish(self, asset: Dict, keys: Dict) -> Dict:
        """POST /2/tweets with the asset text. Returns the raw X response dict."""
        text = asset.get("text", "")
        resp = requests.post(
            _TWEETS_URL,
            auth=self._auth(keys),
            json={"text": text},
            timeout=_TIMEOUT,
        )
        try:
            return resp.json()
        except ValueError:
            return {"title": "non_json_response", "status": resp.status_code,
                    "detail": resp.text[:200]}
