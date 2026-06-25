"""CampaignGenerator — produces channel-ready post copy.

Follows the DeepResearchAgent.execute() pattern: an async generator yielding
(event_type, content) tuples so the dashboard/worker can stream progress. ALL
text generation goes through the backend's generic stream_llm/call_llm_once
(failover + circuit breaker for free) — NO provider-named functions.

Each generated post is validated by tools.content_policy_check before it is
emitted as a ready asset, so a non-compliant post never reaches a connector
(plan verify #5).

Event types: "status" (progress), "token" (streamed copy), "asset" (a finished,
policy-checked post), "done", "error".
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator, Dict, Tuple

from growth_engine.llm import stream_llm
from growth_engine.config import get_brand
from growth_engine.generator.prompts import (
    DAILY_VERSE_SYSTEM,
    DAILY_VERSE_USER,
    DEFAULT_THEMES,
)
from tools.content_policy_check.check import run as policy_check, LIMITS

logger = logging.getLogger(__name__)


class CampaignGenerator:
    """Generate daily-verse posts for a campaign's channels."""

    def __init__(self, app_slug: str = "purangpt"):
        self.brand = get_brand(app_slug)

    async def daily_verse(
        self, channel: str, theme: str = "", day_index: int = 0
    ) -> AsyncGenerator[Tuple[str, object], None]:
        """Generate one policy-checked daily-verse post for `channel`.

        Yields ("status",...), ("token",...) while streaming, then exactly one
        ("asset", {channel, kind, text}) on success, or ("error", {...}).
        """
        if channel not in LIMITS:
            yield "error", {"code": "unknown_channel", "message": channel}
            return

        limit = LIMITS[channel]
        theme = theme or DEFAULT_THEMES[day_index % len(DEFAULT_THEMES)]
        yield "status", f"Composing {channel} post on: {theme}"

        system = DAILY_VERSE_SYSTEM.format(
            app_name=self.brand.name,
            voice=self.brand.voice,
            channel=channel,
            max_chars=limit["max_chars"],
            max_hashtags=min(limit["max_hashtags"], len(self.brand.hashtags)),
            hashtags=" ".join(self.brand.hashtags),
            app_url=self.brand.app_url,
        )
        user = DAILY_VERSE_USER.format(theme=theme, channel=channel)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        # Stream the copy (failover/circuit-breaker handled inside stream_llm).
        parts = []
        try:
            async for chunk in stream_llm(messages, temperature=0.8):
                if isinstance(chunk, str):
                    parts.append(chunk)
                    yield "token", chunk
        except Exception as e:
            logger.error(f"daily_verse generation failed: {e}")
            yield "error", {"code": "llm_failed", "message": str(e)}
            return

        text = "".join(parts).strip().strip('"')
        if not text:
            yield "error", {"code": "empty_generation", "message": "model returned nothing"}
            return

        # Deterministic policy gate — never emit a post the platform would reject.
        check = policy_check(channel=channel, text=text)
        if not (check["success"] and check["data"]["ok"]):
            violations = (check["data"] or {}).get("violations", []) if check["data"] else check["errors"]
            yield "status", f"Post failed policy ({channel}); discarding: {violations}"
            yield "error", {"code": "policy_failed", "message": str(violations), "text": text}
            return

        yield "asset", {
            "channel": channel,
            "kind": "copy",
            "text": text,
            "theme": theme,
            "length": check["data"]["length"],
        }

    async def execute(
        self, brief: Dict
    ) -> AsyncGenerator[Tuple[str, object], None]:
        """Generate one daily-verse post per channel in the (normalized) brief.

        `brief` is expected to be already validated by
        tools.campaign_brief_validate. Yields the merged event stream; ends with
        ("done", {posts: [...]}).
        """
        channels = brief.get("channels", [])
        day_index = int(brief.get("day_index", 0))
        yield "status", f"Generating campaign across {len(channels)} channel(s)"

        posts = []
        for channel in channels:
            async for event, content in self.daily_verse(channel, day_index=day_index):
                if event == "asset":
                    posts.append(content)
                yield event, content

        yield "done", {"posts": posts}
