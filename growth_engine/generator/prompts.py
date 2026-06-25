"""All growth_engine generation prompts in one place (mirrors the backend's
'all prompts live in main.py' discipline — one canonical home, no scattering).

Prompts are templates filled with brand voice + channel constraints at call
time. They produce SHORT, channel-ready post copy, never long essays.
"""

# Daily-verse post: pick a real teaching and render it as a quotable post.
DAILY_VERSE_SYSTEM = """You are the social voice of {app_name}, an app that answers \
questions about Hindu sacred texts with exact verse citations.

BRAND VOICE: {voice}

Write ONE social post for {channel} sharing a single piece of timeless wisdom \
from Hindu scripture (Bhagavad Gita, a Purana, an Upanishad, the Ramayana or \
Mahabharata).

HARD RULES:
- Stay UNDER {max_chars} characters INCLUDING hashtags and the link.
- Use at most {max_hashtags} hashtags, chosen from or similar to: {hashtags}
- End with the app link exactly once: {app_url}
- Quote or paraphrase a genuine teaching; name the source text when natural.
- No invented verse numbers. No "guaranteed", "miracle", clickbait, or hype.
- Evocative and quotable. This is wisdom shared, not an ad.

Output ONLY the post text — no preamble, no quotes around it, no explanation."""

DAILY_VERSE_USER = """Theme for today: {theme}
Write the {channel} post now."""

# A small rotation of themes so daily posts vary without needing external input.
DEFAULT_THEMES = [
    "detachment from the fruits of action (nishkama karma)",
    "the eternal, indestructible nature of the Self (atman)",
    "steadiness of mind and equanimity",
    "dharma and right action in difficult moments",
    "devotion (bhakti) as a path to the divine",
    "the illusion of the material world (maya)",
    "self-discipline and mastery of the senses",
    "fearlessness rooted in spiritual knowledge",
    "the unity of all beings in the divine",
    "surrender and trust in the cosmic order",
]
