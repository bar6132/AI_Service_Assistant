"""Model-layer tests against a local fake OpenAI-compatible server."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import src.llm as llm
from src.models import Extraction

VALID = json.dumps({"intent": "cancel", "order_ids": ["ORD-1001"], "product_state": "unknown",
                    "asks_compensation": False, "language": "he"})


def completion(content):
    return {"id": "x", "object": "chat.completion", "created": 0, "model": "m",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": content}}]}


@pytest.fixture
def server(monkeypatch):
    """Scripted server: each request pops the next (status, content) pair."""
    script, bodies = [], []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            bodies.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            status, content = script.pop(0) if len(script) > 1 else script[0]
            payload = json.dumps(completion(content) if status == 200 else {"error": "x"}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setenv("PROVIDERS", "local")
    monkeypatch.setenv("LOCAL_BASE_URL", f"http://127.0.0.1:{httpd.server_address[1]}/v1")
    monkeypatch.setattr(llm, "TRANSIENT_BACKOFF_SECONDS", 0)
    yield script, bodies
    httpd.shutdown()


def test_transient_error_gets_exactly_one_retry_no_hidden_sdk_retries(server):
    script, bodies = server
    script.append((503, None))
    with pytest.raises(llm.AllProvidersFailed):
        llm.run_structured("s", "u", Extraction)
    assert len(bodies) == 2  # was 3 per "attempt" before max_retries=0 (G-07)


def test_transient_error_then_success(server):
    script, bodies = server
    script.extend([(503, None), (200, VALID)])
    assert llm.run_structured("s", "u", Extraction).order_ids == ["ORD-1001"]
    assert len(bodies) == 2


def test_permanent_error_is_not_retried(server):
    script, bodies = server
    script.append((401, None))
    with pytest.raises(llm.AllProvidersFailed):
        llm.run_structured("s", "u", Extraction)
    assert len(bodies) == 1


def test_schema_error_gets_a_repair_prompt(server):
    script, bodies = server
    script.extend([(200, "not json"), (200, VALID)])
    assert llm.run_structured("s", "u", Extraction).intent == "cancel"
    assert llm.REPAIR_SUFFIX.strip() in bodies[1]["messages"][1]["content"]


def test_run_text_returns_text(server):
    script, _ = server
    script.append((200, "  שלום  "))
    assert llm.run_text("s", "u") == "שלום"


def test_unknown_provider_is_a_config_error(monkeypatch):
    monkeypatch.setenv("PROVIDERS", "groq")
    with pytest.raises(llm.ConfigError, match="groq"):
        llm.validate_config()


def test_provider_without_key_is_skipped_and_reported(monkeypatch):
    monkeypatch.setenv("PROVIDERS", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    with pytest.raises(llm.ConfigError, match="no usable model provider"):
        llm.validate_config()


def test_default_chain_is_the_tested_provider(monkeypatch):
    monkeypatch.delenv("PROVIDERS", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    assert llm.validate_config() == ["gemini"]
