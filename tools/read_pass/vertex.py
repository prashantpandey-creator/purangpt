"""vertex — one provider for the whole Vertex AI Model Garden.

Daddy enabled GCP billing so the pipeline can hit Gemini + Claude + Llama +
Mistral through ONE surface, ONE auth (gcloud OAuth), no per-vendor API keys.

Publisher quirks this module hides:
  - google    → endpoint `:generateContent`, payload {contents:[...]},
                response candidates[].content.parts[].text
  - anthropic → endpoint `:rawPredict`, payload {anthropic_version, messages, max_tokens},
                response content[].text  (Claude's native shape, minus model field)
  - meta/mistral → OpenAI-ish via `:rawPredict` too (add when needed)

Auth = `gcloud auth print-access-token` (Bearer). The token_provider/http hooks
are injectable so the pure endpoint/payload/parse logic is unit-tested without
live GCP. probe() reports which Model Garden models the project can reach.

JSON contract (Rule 0, precond B):
  probe(project) -> {success, data:{models:[{model,reachable,...}]}, metadata, errors}
"""
from __future__ import annotations

import json
import subprocess
import urllib.request
import urllib.error
from typing import Any, Callable, Dict, List, Optional, Tuple


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


# ── endpoint + payload + parse (pure, unit-tested) ─────────────────────────

def build_endpoint(project: str, region: str, publisher: str, model: str) -> str:
    method = "generateContent" if publisher == "google" else "rawPredict"
    return (f"https://{region}-aiplatform.googleapis.com/v1/projects/{project}/"
            f"locations/{region}/publishers/{publisher}/models/{model}:{method}")


def build_payload(publisher: str, prompt: str, max_tokens: int = 4096,
                  temperature: float = 0.3) -> Dict[str, Any]:
    if publisher == "google":
        return {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens,
                                 "temperature": temperature},
        }
    if publisher == "anthropic":
        return {
            "anthropic_version": "vertex-2023-10-16",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
    # meta / mistral on Vertex speak an OpenAI-ish chat shape via rawPredict
    return {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens, "temperature": temperature,
    }


def parse_response(publisher: str, resp: Dict[str, Any]) -> str:
    if publisher == "google":
        cand = resp["candidates"][0]
        parts = cand.get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts)
    if publisher == "anthropic":
        return "".join(b.get("text", "") for b in resp.get("content", []))
    # openai-ish
    return resp["choices"][0]["message"]["content"]


# ── auth + http (injectable) ───────────────────────────────────────────────

def _gcloud_token() -> str:
    return subprocess.check_output(
        ["gcloud", "auth", "print-access-token"], text=True).strip()


def _http_post(url: str, headers: Dict[str, str], body: Dict[str, Any]) -> Dict[str, Any]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers=headers)
    return json.load(urllib.request.urlopen(req, timeout=180))


def generate(publisher: str, model: str, prompt: str, project: str,
             region: str = "us-central1", max_tokens: int = 4096,
             token_provider: Optional[Callable[[], str]] = None,
             http: Optional[Callable[..., Dict]] = None) -> str:
    """Single completion via Vertex. Returns plain text."""
    tp = token_provider or _gcloud_token
    fn = http or _http_post
    url = build_endpoint(project, region, publisher, model)
    headers = {"Authorization": f"Bearer {tp()}", "Content-Type": "application/json"}
    body = build_payload(publisher, prompt, max_tokens=max_tokens)
    resp = fn(url, headers, body)
    return parse_response(publisher, resp)


# ── probe: which Model Garden models can the project reach? ─────────────────

# Canonical Model Garden targets (publisher, model, region). Anthropic models on
# Vertex live in us-east5; Gemini in us-central1.
DEFAULT_PROBE_MODELS: List[Tuple[str, str, str]] = [
    ("google", "gemini-2.0-flash", "us-central1"),
    ("google", "gemini-2.5-flash", "us-central1"),
    ("google", "gemini-2.5-pro", "us-central1"),
    ("anthropic", "claude-3-5-sonnet-v2@20241022", "us-east5"),
    ("anthropic", "claude-3-5-haiku@20241022", "us-east5"),
]


def probe(project: str,
          models: Optional[List[Tuple[str, str, str]]] = None,
          token_provider: Optional[Callable[[], str]] = None,
          http: Optional[Callable[..., Dict]] = None) -> Dict[str, Any]:
    """Test-call each model with a trivial prompt; report reachability."""
    models = models or DEFAULT_PROBE_MODELS
    results = []
    errors = []
    for publisher, model, region in models:
        entry = {"publisher": publisher, "model": model, "region": region}
        try:
            txt = generate(publisher, model, "Reply with the single word: OK",
                           project, region=region, max_tokens=16,
                           token_provider=token_provider, http=http)
            entry["reachable"] = True
            entry["sample"] = (txt or "").strip()[:40]
        except Exception as e:
            entry["reachable"] = False
            msg = str(e)[:160]
            entry["error"] = msg
            errors.append({"code": "unreachable", "message": f"{model}: {msg}"})
        results.append(entry)

    data = {
        "project": project,
        "models": results,
        "n_reachable": sum(1 for m in results if m.get("reachable")),
        "n_total": len(results),
    }
    # success if at least one model reachable (probe ran); errors list per-model
    return _envelope(data["n_reachable"] > 0, data, {}, errors)


if __name__ == "__main__":
    import sys
    project = (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--")
               else subprocess.check_output(
                   ["gcloud", "config", "get-value", "project"], text=True).strip())
    env = probe(project)
    if "--json" in sys.argv:
        print(json.dumps(env, indent=2, ensure_ascii=False, default=str))
    else:
        d = env["data"]
        print(f"Vertex Model Garden probe — project {d['project']}")
        print(f"  reachable: {d['n_reachable']}/{d['n_total']}")
        for m in d["models"]:
            mark = "✅" if m.get("reachable") else "❌"
            extra = m.get("sample", "") if m.get("reachable") else m.get("error", "")[:70]
            print(f"  {mark} {m['publisher']:10s} {m['model']:32s} {extra}")
