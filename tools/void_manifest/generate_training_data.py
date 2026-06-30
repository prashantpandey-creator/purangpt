"""Training data generator for Approach 2 — fine-tuning the Puranic LLM.

Generates (intent → clean ArchitecturalGraph) pairs by:
1. Creating diverse app descriptions across domains
2. Running each through the PoC with a strong LLM (DeepSeek)
3. Collecting only pairs that pass the Witness in ≤max_refine rounds
4. Augmenting: varying descriptions to increase dataset size
5. Outputting in chat-format JSONL ready for fine-tuning

Usage:
  venv/bin/python -m tools.void_manifest.generate_training_data --count 50 --json
  venv/bin/python -m tools.void_manifest.generate_training_data --count 5000 --output data/finetune_pairs.jsonl
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from typing import Any, Dict, List, Optional

from tools.void_manifest.check import _call_llm, _extract_json, conceive
from tools.void_manifest.arch_schema import ArchitecturalGraph, validate

# ─── Seed app descriptions ────────────────────────────────────────────────────
# Diverse across domains. The LLM will also generate variations.

SEED_APPS = [
    # SaaS / Productivity
    "A todo list app where users create tasks with due dates, priorities, and tags. Tasks can be organized into projects.",
    "A note-taking app with markdown support, folders, and full-text search. Users can share notes with others.",
    "A habit tracker where users define daily habits and check them off each day. Shows streaks and statistics.",
    "A time tracking app where users log hours against projects and clients. Generates weekly reports.",
    "A document collaboration tool where multiple users edit documents in real-time with comments and version history.",
    "A meeting scheduler where users share availability and others book time slots. Integrates with calendars.",
    "A CRM system where salespeople track leads, contacts, deals, and pipeline stages. Shows revenue forecasts.",
    "A project management tool with boards, lists, cards, assignees, due dates, and activity feeds.",
    "An employee directory with profiles, departments, reporting lines, and search.",
    "A help desk ticketing system where users submit tickets and agents resolve them with status tracking.",

    # E-commerce / Marketplace
    "A marketplace where sellers list products with images, prices, and categories. Buyers browse, cart, and checkout.",
    "A food delivery app where restaurants list menu items, users order, and drivers deliver.",
    "A booking platform for services like cleaning, tutoring, or repairs. Providers set availability and rates.",
    "A rental marketplace where owners list items for rent by the day. Renters book, pay, and review.",
    "A digital product store selling ebooks, courses, and templates with instant download after purchase.",
    "An auction site where sellers list items with starting bids and end times. Buyers place bids.",
    "A subscription box service where users subscribe to monthly curated products by category.",
    "A ticketing platform for events where organizers create events and attendees purchase tickets.",
    "A classifieds site where users post ads with photos, descriptions, and contact info by category.",
    "A group buying platform where deals activate when enough buyers commit.",

    # Social / Community
    "A social network for photographers with portfolios, galleries, likes, comments, and following.",
    "A forum where users create topics in categories, post replies, upvote, and earn reputation.",
    "A blogging platform where authors write posts with tags, readers comment, and followers get updates.",
    "A recipe sharing community where users post recipes with ingredients, steps, photos, and ratings.",
    "A fitness community where members log workouts, share routines, and follow each other's progress.",
    "A book review site where readers review books, create reading lists, and follow reviewers.",
    "A Q&A platform where users ask questions, answer with upvotes, and the best answers rise to top.",
    "A local events platform where organizers post events and attendees RSVP with comments.",
    "A pet owner community where users create pet profiles, share photos, and join breed groups.",
    "A travel journal site where travelers log trips with locations, photos, and tips.",

    # Tools / Utilities
    "A URL shortener where users create short links with custom slugs and track click analytics.",
    "A form builder where users drag-and-drop fields, publish forms, and view submissions in a dashboard.",
    "A file hosting service where users upload files, organize in folders, and share with expiring links.",
    "A poll creator where users create polls with options, share links, and view live results.",
    "An invoice generator where freelancers create and send invoices, track payment status.",
    "A newsletter platform where authors write issues, manage subscribers, and track open rates.",
    "A code snippet manager where developers save, tag, search, and share code snippets.",
    "A bookmark manager where users save URLs with tags, categories, and notes.",
    "A password manager where users store credentials in vaults with categories and search.",
    "A weather dashboard showing forecasts, alerts, and historical data for saved locations.",

    # Content / Media
    "A podcast hosting platform where creators upload episodes, manage shows, and track listens.",
    "A video sharing site where users upload, transcode, and share videos with comments and playlists.",
    "A music library where users upload tracks, create playlists, and share with followers.",
    "A digital asset manager where teams upload, tag, search, and share images, videos, and documents.",
    "A CMS for publishing articles with authors, categories, scheduled publishing, and SEO metadata.",
    "A newsletter curation tool that aggregates articles from RSS feeds and lets editors curate issues.",

    # Education
    "A learning management system where instructors create courses with lessons, quizzes, and student progress tracking.",
    "A flashcard app where users create decks, study with spaced repetition, and track mastery.",
    "A tutoring marketplace where tutors list subjects and availability, and students book sessions.",
    "A coding challenge platform where users solve problems, submit solutions, and see test results.",
    "A language learning app with vocabulary lists, practice exercises, and progress tracking.",

    # Finance / Business
    "A personal finance tracker where users log income and expenses by category with budgets and charts.",
    "An expense reporting tool where employees submit expenses with receipts and managers approve.",
    "A donation platform where nonprofits create campaigns and donors contribute with payment processing.",
    "A billing system where businesses create recurring invoices, track payments, and send reminders.",
    "A payroll system where employers manage employee salaries, deductions, and generate payslips.",

    # Health / Wellness
    "A telemedicine platform where doctors set availability and patients book video consultations.",
    "A medication tracker where users log doses, set reminders, and track adherence.",
    "A therapy booking platform where therapists list specialties and clients book sessions.",
    "A fitness class scheduler where studios list classes, members book spots, and instructors are assigned.",

    # Logistics / Operations
    "An inventory management system where staff track stock levels, receive shipments, and fulfill orders.",
    "A delivery tracking system where dispatchers assign drivers and customers track packages in real-time.",
    "A facility booking system where users reserve rooms, equipment, or desks with time slots.",
    "A maintenance request tracker where tenants submit issues and maintenance staff resolve them.",

    # Vertical SaaS
    "A restaurant table reservation system where diners book tables and restaurants manage seating.",
    "A salon booking app where clients book appointments with stylists and services.",
    "A veterinary practice manager with pet records, appointments, and treatment history.",
    "A real estate listing platform where agents list properties with photos, details, and inquiry forms.",
    "A legal case management system where lawyers track cases, clients, documents, and billable hours.",
    "A church management system with member directory, events, donations, and small groups.",
    "A farm management tool tracking crops, livestock, equipment, and harvests.",
    "A library management system with book catalog, member checkouts, holds, and fines.",
]

# Augmentation templates for varying descriptions
AUGMENT_TEMPLATES = [
    "Add {feature} to the app.",
    "The app should also support {feature}.",
    "Include {feature} as a premium feature.",
    "The app needs: {feature}.",
    "Extend with {feature}.",
    "Build a simplified version without {remove}.",
    "Focus on the {focus} aspect. Remove everything else.",
    "Add {feature} with real-time updates.",
    "Make it mobile-first with {feature}.",
    "The app should handle {feature} for enterprise users.",
]

FEATURES = [
    "dark mode", "email notifications", "push notifications", "file uploads",
    "image galleries", "drag and drop", "real-time collaboration", "offline mode",
    "export to CSV", "export to PDF", "bulk operations", "advanced search",
    "full-text search", "filtering and sorting", "pagination", "infinite scroll",
    "social login (Google/GitHub)", "two-factor authentication", "role-based access",
    "team accounts", "activity logging", "audit trails", "API keys",
    "webhooks", "analytics dashboard", "report generation", "data import",
    "batch processing", "scheduled tasks", "rate limiting", "multi-language support",
    "accessibility features", "keyboard shortcuts", "comments and discussions",
    "rating and reviews", "favorites and bookmarks", "sharing and collaboration",
    "version history", "draft and publish workflow", "approval workflows",
    "payment processing", "subscription billing", "shopping cart",
    "wishlists", "order tracking", "inventory alerts", "barcode scanning",
    "QR code generation", "map integration", "calendar integration",
    "video embedding", "markdown editor", "WYSIWYG editor", "code syntax highlighting",
]

# ─── Intent generation ────────────────────────────────────────────────────────

def generate_intents(seed_count: int = 50, augment_per_seed: int = 5) -> List[str]:
    """Generate a diverse set of app descriptions for training data.

    Args:
        seed_count: Number of seed apps to sample from SEED_APPS
        augment_per_seed: Number of augmented variations per seed

    Returns:
        List of unique app descriptions
    """
    intents = []

    # Sample seeds
    seeds = random.sample(SEED_APPS, min(seed_count, len(SEED_APPS)))
    intents.extend(seeds)

    # Generate augmentations
    for seed in seeds:
        for _ in range(augment_per_seed):
            template = random.choice(AUGMENT_TEMPLATES)
            feature = random.choice(FEATURES)
            remove = random.choice(FEATURES)
            focus = random.choice(["mobile", "desktop", "admin", "public", "reporting", "collaboration"])

            augmented = template.format(feature=feature, remove=remove, focus=focus)
            full = f"{seed} {augmented}"
            intents.append(full)

    # Shuffle
    random.shuffle(intents)
    return intents


def _llm_generate_variations(seed_intent: str, count: int = 10) -> List[str]:
    """Use an LLM to generate creative variations of an app description."""
    prompt = f"""Given this app description:
"{seed_intent}"

Generate {count} creative variations. Each variation should be a DIFFERENT app in the same domain.
Vary: target audience, scale (simple→complex), features, constraints, platform focus.
Make each one a complete, self-contained app description of 1-3 sentences.

Return ONLY a JSON array of strings. No markdown. No explanation.

Example format:
["A simple todo app for personal use with lists and due dates",
 "A team task manager with projects, assignments, and Gantt charts",
 ...]"""

    try:
        messages = [
            {"role": "system", "content": "You generate diverse app descriptions. Output ONLY a JSON array of strings."},
            {"role": "user", "content": prompt}
        ]
        raw = _call_llm(messages, temperature=0.8)
        # Extract JSON array
        text = raw.strip()
        if text.startswith("```"):
            text = text[text.index("\n")+1:text.rindex("```")].strip()
        variations = json.loads(text)
        if isinstance(variations, list):
            return [v for v in variations if isinstance(v, str) and len(v) > 20]
    except Exception:
        pass
    return []


# ─── Training pair generation ─────────────────────────────────────────────────

def generate_training_pairs(
    intents: List[str],
    max_refine_rounds: int = 3,
    output_jsonl: Optional[str] = None,
    use_llm_augment: bool = True,
    target_count: int = 5000,
) -> Dict[str, Any]:
    """Generate (intent → clean ArchitecturalGraph) training pairs.

    For each intent:
    1. Run the PoC (conceive + witness + refine)
    2. If the graph is clean (passes all Witness checks), save the pair
    3. If use_llm_augment, also generate variations and process those

    Returns:
        Envelope with stats: {total_intents, successful, failed, pairs, ...}
    """
    pairs = []
    stats = {"total_intents": 0, "successful": 0, "failed": 0,
             "failed_conception": 0, "failed_witness": 0, "rounds_distribution": {}}
    pair_file = None

    if output_jsonl:
        pair_file = open(output_jsonl, "w")

    processed = set()
    queue = list(intents)

    try:
        while queue and len(pairs) < target_count:
            intent = queue.pop(0)
            intent_key = intent.strip().lower()[:100]
            if intent_key in processed:
                continue
            processed.add(intent_key)
            stats["total_intents"] += 1

            print(f"[{stats['total_intents']}] Processing: {intent[:100]}...", file=sys.stderr)

            # Run conception
            env = conceive(intent, max_refine_rounds=max_refine_rounds)

            if not env["success"]:
                stats["failed"] += 1
                if env["metadata"].get("stage") == "conception_failed":
                    stats["failed_conception"] += 1
                else:
                    stats["failed_witness"] += 1
                continue

            graph_dict = env["data"]
            rounds = env["metadata"].get("rounds", 1)
            stats["rounds_distribution"][str(rounds)] = stats["rounds_distribution"].get(str(rounds), 0) + 1
            stats["successful"] += 1

            # Create training pair
            pair = {
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": f"Create a complete Architectural Graph for this application:\n\n{intent}"},
                    {"role": "assistant", "content": json.dumps(graph_dict, ensure_ascii=False)},
                ],
                "metadata": {
                    "intent": intent,
                    "rounds": rounds,
                    "entities": len(graph_dict.get("entities", [])),
                    "routes": len(graph_dict.get("routes", [])),
                    "pages": len(graph_dict.get("pages", [])),
                    "components": len(graph_dict.get("components", [])),
                },
            }
            pairs.append(pair)

            if pair_file:
                pair_file.write(json.dumps(pair, ensure_ascii=False) + "\n")
                pair_file.flush()

            print(f"  ✓ Clean in {rounds} round(s). Total pairs: {len(pairs)}", file=sys.stderr)

            # Augment: generate variations from successful intents
            if use_llm_augment and len(pairs) < target_count and len(queue) < target_count:
                try:
                    variations = _llm_generate_variations(intent, count=5)
                    for v in variations:
                        if v.strip().lower()[:100] not in processed:
                            queue.append(v)
                    print(f"  + {len(variations)} variations added to queue", file=sys.stderr)
                except Exception:
                    pass

            # Rate limiting
            time.sleep(0.5)

    finally:
        if pair_file:
            pair_file.close()

    return _envelope(True, {"pairs": len(pairs), "stats": stats}, stats, [])


# ─── System prompt (same as prompts.py but duplicated for standalone use) ─────

_SYSTEM_PROMPT = """You are an expert software architect. Your task is to convert a user's natural language description of a web application into a complete, internally consistent Architectural Graph in JSON format.

The Architectural Graph is a structured specification that fully describes the application. It is the "conscious void" — the complete conception before any code exists. Every entity, every route, every component, every relationship must be specified.

**Your process:**
1. Read the user's description carefully
2. Identify all entities (data models) needed
3. Define all relationships between entities
4. Design all API routes needed
5. Define all pages and their data requirements
6. Define all components and their props/state
7. Ensure internal consistency — every reference must be valid
8. Output ONLY valid JSON — no explanation, no markdown wrapping

Output ONLY the JSON object. No preamble. No explanation. The JSON must parse."""


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    output_jsonl = None
    count = 50
    augment = 5

    i = 1
    while i < len(argv):
        if argv[i] == "--output" and i + 1 < len(argv):
            output_jsonl = argv[i + 1]
            i += 2
        elif argv[i] == "--count" and i + 1 < len(argv):
            count = int(argv[i + 1])
            i += 2
        elif argv[i] == "--augment" and i + 1 < len(argv):
            augment = int(argv[i + 1])
            i += 2
        elif argv[i] == "--no-llm-augment":
            augment = 0
            i += 1
        elif argv[i] == "--json":
            i += 1
        else:
            i += 1

    if output_jsonl is None:
        output_jsonl = f"data/finetune_pairs_{int(time.time())}.jsonl"

    os.makedirs(os.path.dirname(output_jsonl) if os.path.dirname(output_jsonl) else "data", exist_ok=True)

    print(f"Generating {count} base intents with {augment}x augmentation...", file=sys.stderr)
    intents = generate_intents(seed_count=count, augment_per_seed=augment)
    print(f"Total intents: {len(intents)}", file=sys.stderr)
    print(f"Output: {output_jsonl}", file=sys.stderr)

    env = generate_training_pairs(
        intents,
        output_jsonl=output_jsonl,
        use_llm_augment=(augment > 0),
        target_count=count * (augment + 1),
    )

    if as_json:
        print(json.dumps(env, indent=2, default=str))
    else:
        stats = env["metadata"]
        print(f"\n{'='*60}")
        print(f"Training Data Generation Complete")
        print(f"{'='*60}")
        print(f"Total attempted:  {stats['total_intents']}")
        print(f"Successful:      {stats['successful']}")
        print(f"Failed:          {stats['failed']}")
        print(f"  Conception:    {stats['failed_conception']}")
        print(f"  Witness:       {stats['failed_witness']}")
        print(f"Pairs generated: {env['data']['pairs']}")
        print(f"Rounds distribution: {stats['rounds_distribution']}")
        if output_jsonl:
            print(f"Saved to: {output_jsonl}")

    return 0 if env["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
