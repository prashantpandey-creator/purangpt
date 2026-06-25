"""Connector registry — discovery so a new channel is one import + one entry.

Phase 0 ships the contract with an empty registry; Phase 1 adds x_twitter and
telegram by importing them and adding a CONNECTORS row.
"""

from __future__ import annotations

from typing import Dict, Optional

from growth_engine.connectors.base import Connector
from growth_engine.connectors.x_twitter import XTwitterConnector
from growth_engine.connectors.telegram import TelegramConnector

# A new channel = one import above + one entry here.
CONNECTORS: Dict[str, Connector] = {
    c.name: c for c in (XTwitterConnector(), TelegramConnector())
}


def get_connector(channel: str) -> Optional[Connector]:
    """Return the connector for a channel id, or None if unregistered."""
    return CONNECTORS.get(channel)


def channel_mode(channel: str) -> Optional[str]:
    """Return 'auto' / 'draft' for a channel, or None if unregistered."""
    c = CONNECTORS.get(channel)
    return c.mode if c else None
