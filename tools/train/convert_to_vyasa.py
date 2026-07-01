"""
Convert graph training data → Vyasa Response Plan format.

Takes phase JSONL files (flat Q&A) and converts to Response Plan
JSONL for the Vyasa conversation adapter training pipeline.

Usage: venv/bin/python -m tools.train.convert_to_vyasa
"""
import json, os, sys, random
from pathlib import Path

SYSTEM_PROMPT = """You are Vyasa — the compiler of the Vedas, the voice of the Puranas. You do not interpret. You do not embellish. You state what is in the texts — exact, bare, precise. Every name you speak is in the graph. Every connection you name is an edge with verse provenance. Every inner meaning is from the Shailendra Sharma lineage decryption.

Given a query, produce a Response Plan — structured JSON that a deterministic renderer converts to natural speech.

Format:
{
  "understanding": "What the user is really asking beneath the words",
  "insight": "The core truth — one clear teaching from the texts",
  "grounding": {"source": "Which text", "citation": "Exact verse if available"},
  "tone": "direct",
  "structure": ["teaching", "deepening"],
  "key_phrases": ["2-3 exact phrases to speak verbatim"]
}

Output ONLY valid JSON. No markdown. No explanation."""


def qa_to_plan(question, answer):
    """Convert a flat Q&A to a Response Plan."""
    # Extract key info from the answer
    answer_clean = answer.strip().rstrip('.')

    # Determine tone based on content
    if any(w in question.lower() for w in ['inner meaning', 'decode', 'what does']):
        tone = "precise"
    elif any(w in question.lower() for w in ['who', 'what is', 'tell me']):
        tone = "direct"
    elif any(w in question.lower() for w in ['connected', 'relationship', 'walk', 'how is']):
        tone = "precise"
    else:
        tone = "direct"

    # Split answer into insight + details
    parts = answer_clean.split('. ', 1)
    insight = parts[0]

    # Extract key phrases from the answer
    words = answer_clean.split()
    if len(words) > 6:
        key_phrases = [
            " ".join(words[:5]),
            answer_clean[-60:] if len(answer_clean) > 60 else answer_clean,
        ]
    else:
        key_phrases = [answer_clean]

    return {
        "understanding": f"The seeker wants to know: {question}",
        "insight": insight,
        "grounding": {
            "source": "Puranic Knowledge Graph",
            "citation": "From the verse-cited graph edges and entity records"
        },
        "tone": tone,
        "structure": ["teaching", "deepening"],
        "key_phrases": key_phrases[:2]
    }


def convert(input_path, output_path, max_examples=500):
    """Convert a phase JSONL to Vyasa Response Plan format."""
    examples = []
    with open(input_path, encoding='utf-8') as f:
        for line in f:
            if len(examples) >= max_examples:
                break
            try:
                item = json.loads(line)
                msgs = item.get("messages", [])
                # Extract user question and assistant answer
                user_msg = next((m["content"] for m in msgs if m["role"] == "user"), "")
                asst_msg = next((m["content"] for m in msgs if m["role"] == "assistant"), "")
                if user_msg and asst_msg:
                    plan = qa_to_plan(user_msg, asst_msg)
                    examples.append({
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_msg},
                            {"role": "assistant", "content": json.dumps(plan, ensure_ascii=False)}
                        ]
                    })
            except Exception:
                continue

    random.shuffle(examples)
    with open(output_path, 'w', encoding='utf-8') as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    return len(examples)


if __name__ == "__main__":
    out_dir = os.path.expanduser("~/vyasa/data/puranic_graph")
    os.makedirs(out_dir, exist_ok=True)

    phases_dir = "tools/train/out/phases"
    counts = {}
    total = 0

    for phase in ["phase1_mula", "phase2_sambandha", "phase3_bhashya", "phase4_darshana"]:
        inp = os.path.join(phases_dir, f"{phase}.jsonl")
        out = os.path.join(out_dir, f"{phase}_plans.jsonl")
        if os.path.exists(inp):
            # Sample proportionally: more from mula (foundation), fewer from darshana (synthesis)
            limits = {"phase1_mula": 300, "phase2_sambandha": 100, "phase3_bhashya": 80, "phase4_darshana": 20}
            n = convert(inp, out, max_examples=limits.get(phase, 50))
            counts[phase] = n
            total += n
            print(f"  {phase}: {n} plans → {out}")

    # Merge all into one training file
    all_plans = []
    for phase in ["phase1_mula", "phase2_sambandha", "phase3_bhashya", "phase4_darshana"]:
        fp = os.path.join(out_dir, f"{phase}_plans.jsonl")
        if os.path.exists(fp):
            with open(fp) as f:
                for line in f:
                    all_plans.append(line)

    random.shuffle(all_plans)
    split = int(len(all_plans) * 0.9)

    train_path = os.path.join(out_dir, "train.jsonl")
    val_path = os.path.join(out_dir, "val.jsonl")

    with open(train_path, 'w') as f:
        for line in all_plans[:split]:
            f.write(line)
    with open(val_path, 'w') as f:
        for line in all_plans[split:]:
            f.write(line)

    print(f"\nTotal: {total} Response Plans")
    print(f"Train: {split} → {train_path}")
    print(f"Val:   {len(all_plans) - split} → {val_path}")
    print("\nReady for Vyasa training:")
    print(f"  cd ~/vyasa && source venv/bin/activate")
    print(f"  python train/auto_train.py --data {train_path} --adapter adapters/xvyasa-puranic --type conversation --train")
