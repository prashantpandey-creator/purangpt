"""App registry — brand kits keyed by app_slug, for multi-tenant from day one.

PuranGPT is tenant #1. A second app = one new entry here (Phase 4), no schema
change (ge_campaigns already carries app_slug).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class BrandKit:
    slug: str
    name: str
    tagline: str
    voice: str                       # tone guidance fed into copy prompts
    palette: List[str]               # hex colors for image/video gen
    fonts: List[str]                 # display + body font names
    hashtags: List[str] = field(default_factory=list)
    app_url: str = ""
    default_channels: List[str] = field(default_factory=list)


PURANGPT = BrandKit(
    slug="purangpt",
    name="PuranGPT",
    tagline="Ask the ancient Hindu scriptures — answers with exact verse citations.",
    voice=(
        "Reverent but accessible. Warm, never preachy. Speaks to seekers "
        "reconnecting with Vedic wisdom. Short, evocative, quotable. Sanskrit "
        "terms welcome with gentle gloss. Never clickbait, never irreverent."
    ),
    palette=["#cba455", "#e7cd84", "#b8893b", "#0e0e11", "#e2d4b2"],  # candlelit gold on deep dark
    fonts=["Marcellus", "Inter"],
    hashtags=["#BhagavadGita", "#Purana", "#VedicWisdom", "#Hinduism", "#Sanskrit", "#PuranGPT"],
    app_url="https://purangpt.com",
    default_channels=["x_twitter", "telegram"],
)


_REGISTRY = {PURANGPT.slug: PURANGPT}


def get_brand(app_slug: str = "purangpt") -> BrandKit:
    """Return the brand kit for an app_slug; falls back to PuranGPT."""
    return _REGISTRY.get(app_slug, PURANGPT)
