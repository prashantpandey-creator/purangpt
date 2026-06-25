"""Connector interface — the pluggability contract.

A new channel = one new file implementing Connector + one import line in
registry.py. The worker looks up CONNECTORS[channel], reads .mode, and routes
'auto' -> publish now, 'draft' -> hold in ge_post_queue for 1-click approval.

publish() returns a normalized dict {external_id, external_url} on success, or
raises on failure. The deterministic tools/connector_envelope script wraps the
raw provider response into the {success,data,metadata,errors} envelope so raw
API output never enters the orchestrator's context.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict

AUTO = "auto"
DRAFT = "draft"


class Connector(ABC):
    #: short channel id, e.g. "x_twitter", "telegram", "reddit"
    name: str = ""
    #: AUTO (post automatically) or DRAFT (queue for human approval)
    mode: str = AUTO

    @abstractmethod
    def validate(self, keys: Dict) -> bool:
        """Cheap auth ping — confirm the supplied credentials work. No posting."""
        raise NotImplementedError

    @abstractmethod
    def publish(self, asset: Dict, keys: Dict) -> Dict:
        """Publish `asset` (text/media payload) using `keys`.

        Returns {"external_id": str, "external_url": str} on success.
        Raises on failure (caller normalizes via tools/connector_envelope).
        """
        raise NotImplementedError

    def fetch_metrics(self, external_id: str, keys: Dict) -> Dict:
        """Optional: fetch post metrics. Default: none."""
        return {}

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Connector {self.name} mode={self.mode}>"
