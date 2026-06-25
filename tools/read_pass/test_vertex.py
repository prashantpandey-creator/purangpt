"""Tests-first for the Vertex AI provider (Rule 0 precond A).

Daddy is enabling GCP billing so the pipeline can hit the WHOLE Vertex Model
Garden — Gemini + Claude (Anthropic) + Llama + Mistral — under one bill, one
gcloud-OAuth auth, no juggling per-vendor keys.

This module is a thin provider that:
  - builds the correct Vertex endpoint per publisher (google→generateContent,
    anthropic→rawPredict — DIFFERENT request shapes)
  - auths via `gcloud auth print-access-token` (no API key)
  - normalizes both response shapes to plain text
  - probes which Model Garden models the project can actually reach

Pure logic (endpoint/payload/parse) is tested with injected fakes — no live
GCP calls in tests.

Run: venv/bin/python -m tools.read_pass.test_vertex   (exit 0)
"""
from __future__ import annotations
import json

from tools.read_pass import vertex


PROJECT = "test-proj"


def test_endpoint_for_google_gemini():
    url = vertex.build_endpoint(PROJECT, "us-central1", "google", "gemini-2.0-flash")
    assert "us-central1-aiplatform.googleapis.com" in url
    assert f"projects/{PROJECT}/locations/us-central1" in url
    assert "publishers/google/models/gemini-2.0-flash:generateContent" in url


def test_endpoint_for_anthropic_uses_rawpredict():
    url = vertex.build_endpoint(PROJECT, "us-east5", "anthropic",
                                "claude-3-5-sonnet-v2@20241022")
    assert "publishers/anthropic/models/claude-3-5-sonnet-v2@20241022:rawPredict" in url
    assert "us-east5-aiplatform.googleapis.com" in url


def test_google_payload_shape():
    body = vertex.build_payload("google", "translate this", max_tokens=512)
    assert "contents" in body
    assert body["contents"][0]["parts"][0]["text"] == "translate this"
    assert body["generationConfig"]["maxOutputTokens"] == 512


def test_anthropic_payload_shape():
    # Anthropic-on-Vertex needs anthropic_version + messages, NOT contents
    body = vertex.build_payload("anthropic", "translate this", max_tokens=512)
    assert body["anthropic_version"] == "vertex-2023-10-16"
    assert body["messages"][0]["content"] == "translate this"
    assert body["max_tokens"] == 512
    assert "contents" not in body


def test_parse_google_response():
    resp = {"candidates": [{"content": {"parts": [{"text": "Hello"}, {"text": " world"}]}}]}
    assert vertex.parse_response("google", resp) == "Hello world"


def test_parse_anthropic_response():
    resp = {"content": [{"type": "text", "text": "Hello"}, {"type": "text", "text": " yog"}]}
    assert vertex.parse_response("anthropic", resp) == "Hello yog"


def test_generate_uses_token_provider_and_caller():
    seen = {}
    def fake_token():
        return "fake-oauth-token"
    def fake_http(url, headers, body):
        seen["url"] = url
        seen["auth"] = headers.get("Authorization")
        return {"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}
    out = vertex.generate("google", "gemini-2.0-flash", "hi", PROJECT,
                          region="us-central1",
                          token_provider=fake_token, http=fake_http)
    assert out == "OK"
    assert seen["auth"] == "Bearer fake-oauth-token"
    assert "gemini-2.0-flash" in seen["url"]


def test_probe_envelope_shape():
    # probe() reports reachability per model; with fakes, no live calls
    def fake_token():
        return "t"
    def fake_http(url, headers, body):
        # simulate gemini reachable, claude billing-blocked
        if "anthropic" in url:
            raise RuntimeError("403 BILLING_DISABLED")
        return {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
    env = vertex.probe(PROJECT, token_provider=fake_token, http=fake_http,
                       models=[("google", "gemini-2.0-flash", "us-central1"),
                               ("anthropic", "claude-3-5-sonnet", "us-east5")])
    assert set(env.keys()) == {"success", "data", "metadata", "errors"}
    reach = {m["model"]: m["reachable"] for m in env["data"]["models"]}
    assert reach["gemini-2.0-flash"] is True
    assert reach["claude-3-5-sonnet"] is False


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
