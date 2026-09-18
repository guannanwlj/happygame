"""FP-002 tests: OpenAI-compatible LLM client abstraction (itinerary_app/llm.py).

Scenarios documented in docs/test-cases/fp002-llm-client.md. All network
scenarios run against a programmable local fake endpoint (task card §6):
a ThreadingHTTPServer that can return 200 / 429 / 5xx / other statuses,
slow responses, or malformed bodies, and records the captured requests.
"""

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from itinerary_app import llm

DEFAULT_TIMEOUT = 30.0


class _FakeEndpoint(ThreadingHTTPServer):
    """Programmable fake OpenAI-compatible endpoint (card §6)."""

    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _FakeHandler)
        self.mode = "ok"
        self.status = 500
        self.content = "ITIN_OK"
        self.delay_seconds = 0.0
        self.requests = []

    def handle_error(self, request, client_address):
        """Quiet client disconnects (e.g. timed-out callers closing the socket)."""
        if isinstance(sys.exc_info()[1], ConnectionError):
            return
        super().handle_error(request, client_address)


class _FakeHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        server = self.server
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw)
        except ValueError:
            body = raw.decode("utf-8", "replace")
        server.requests.append(
            {
                "method": self.command,
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "content_type": self.headers.get("Content-Type"),
                "body": body,
            }
        )
        if server.delay_seconds > 0:
            time.sleep(server.delay_seconds)
        self._respond(server)

    def _respond(self, server):
        if server.mode == "ok":
            payload = {
                "choices": [
                    {"message": {"role": "assistant", "content": server.content}}
                ]
            }
            self._send(200, json.dumps(payload))
        elif server.mode == "bad_json":
            self._send(200, "not json at all")
        elif server.mode == "missing_choices":
            self._send(200, json.dumps({"id": "chatcmpl-1"}))
        elif server.mode == "empty_choices":
            self._send(200, json.dumps({"choices": []}))
        elif server.mode == "missing_content":
            self._send(200, json.dumps({"choices": [{"message": {"role": "assistant"}}]}))
        elif server.mode == "non_str_content":
            self._send(200, json.dumps({"choices": [{"message": {"content": 42}}]}))
        else:  # "status": configurable HTTP error code
            self._send(server.status, json.dumps({"error": {"message": "boom"}}))

    def _send(self, status, text):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


@pytest.fixture()
def fake_endpoint():
    server = _FakeEndpoint()
    thread = threading.Thread(target=server.serve_forever, args=(0.01,), daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def make_client(server, **overrides):
    kwargs = {
        "base_url": f"http://127.0.0.1:{server.server_address[1]}",
        "api_key": "test-key-123",
        "model": "test-model",
        "timeout_seconds": 5.0,
    }
    kwargs.update(overrides)
    return llm.LLMClient(**kwargs)


class TestSuccessPath:
    """Acceptance 1 (scenarios A1–A4)."""

    def test_returns_content_string(self, fake_endpoint):
        fake_endpoint.content = "ITIN_OK"
        client = make_client(fake_endpoint)
        result = client.complete("Plan a 3-day trip")
        assert result == "ITIN_OK"
        assert isinstance(result, str)

    def test_seed_content_round_trip(self, fake_endpoint):
        fake_endpoint.content = "## 第1天 …"
        client = make_client(fake_endpoint)
        assert client.complete("生成行程") == "## 第1天 …"

    def test_request_wire_format(self, fake_endpoint):
        client = make_client(fake_endpoint)
        client.complete("Plan a trip")

        assert len(fake_endpoint.requests) == 1
        request = fake_endpoint.requests[0]
        assert request["method"] == "POST"
        assert request["path"] == "/chat/completions"
        assert request["authorization"] == "Bearer test-key-123"
        assert request["content_type"] == "application/json"
        assert request["body"] == {
            "model": "test-model",
            "messages": [{"role": "user", "content": "Plan a trip"}],
        }

    def test_base_url_trailing_slash(self, fake_endpoint):
        client = make_client(fake_endpoint, base_url=f"http://127.0.0.1:{fake_endpoint.server_address[1]}/")
        client.complete("Plan a trip")
        assert fake_endpoint.requests[0]["path"] == "/chat/completions"


class TestTimeout:
    """Acceptance 2 (scenario B1)."""

    def test_slow_endpoint_raises_timeout(self, fake_endpoint):
        fake_endpoint.delay_seconds = 1.2
        client = make_client(fake_endpoint, timeout_seconds=0.25)
        with pytest.raises(llm.LLMTimeoutError) as excinfo:
            client.complete("Plan a trip")
        assert isinstance(excinfo.value.reason, str)
        assert excinfo.value.reason.strip()


class TestUnavailable:
    """Acceptance 3 (scenarios C1–C6)."""

    def test_connection_refused(self):
        server = _FakeEndpoint()
        port = server.server_address[1]
        server.server_close()  # port is now dead: nothing listens on it
        client = llm.LLMClient(
            base_url=f"http://127.0.0.1:{port}",
            api_key="k",
            model="m",
            timeout_seconds=2.0,
        )
        with pytest.raises(llm.LLMUnavailableError) as excinfo:
            client.complete("ping")
        assert excinfo.value.reason.strip()

    @pytest.mark.parametrize("status", [500, 503])
    def test_http_5xx(self, fake_endpoint, status):
        fake_endpoint.mode = "status"
        fake_endpoint.status = status
        client = make_client(fake_endpoint)
        with pytest.raises(llm.LLMUnavailableError) as excinfo:
            client.complete("Plan a trip")
        assert str(status) in excinfo.value.reason

    def test_malformed_json_body(self, fake_endpoint):
        fake_endpoint.mode = "bad_json"
        client = make_client(fake_endpoint)
        with pytest.raises(llm.LLMUnavailableError) as excinfo:
            client.complete("Plan a trip")
        assert excinfo.value.reason.strip()

    @pytest.mark.parametrize(
        "mode", ["missing_choices", "empty_choices", "missing_content"]
    )
    def test_missing_fields_in_body(self, fake_endpoint, mode):
        fake_endpoint.mode = mode
        client = make_client(fake_endpoint)
        with pytest.raises(llm.LLMUnavailableError):
            client.complete("Plan a trip")

    def test_non_string_content(self, fake_endpoint):
        fake_endpoint.mode = "non_str_content"
        client = make_client(fake_endpoint)
        with pytest.raises(llm.LLMUnavailableError):
            client.complete("Plan a trip")


class TestRateLimit:
    """Acceptance 4 (scenario D1)."""

    def test_http_429(self, fake_endpoint):
        fake_endpoint.mode = "status"
        fake_endpoint.status = 429
        client = make_client(fake_endpoint)
        with pytest.raises(llm.LLMRateLimitError) as excinfo:
            client.complete("Plan a trip")
        assert "429" in excinfo.value.reason


class TestClientFromEnv:
    """Acceptance 5 (scenarios E1–E4)."""

    def test_reads_all_four_variables(self, fake_endpoint, monkeypatch):
        monkeypatch.setenv("LLM_BASE_URL", f"http://127.0.0.1:{fake_endpoint.server_address[1]}")
        monkeypatch.setenv("LLM_API_KEY", "env-key")
        monkeypatch.setenv("LLM_MODEL", "env-model")
        monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "12.5")

        client = llm.client_from_env()
        assert client.base_url == f"http://127.0.0.1:{fake_endpoint.server_address[1]}"
        assert client.api_key == "env-key"
        assert client.model == "env-model"
        assert client.timeout_seconds == 12.5

    def test_env_client_is_functional(self, fake_endpoint, monkeypatch):
        monkeypatch.setenv("LLM_BASE_URL", f"http://127.0.0.1:{fake_endpoint.server_address[1]}")
        monkeypatch.setenv("LLM_API_KEY", "env-key")
        monkeypatch.setenv("LLM_MODEL", "env-model")
        monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "5")

        fake_endpoint.content = "ENV_OK"
        assert llm.client_from_env().complete("from env") == "ENV_OK"

    def test_default_timeout_when_unset(self, monkeypatch):
        monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
        monkeypatch.setenv("LLM_BASE_URL", "http://example.invalid")
        monkeypatch.setenv("LLM_API_KEY", "k")
        monkeypatch.setenv("LLM_MODEL", "m")
        assert llm.client_from_env().timeout_seconds == DEFAULT_TIMEOUT

    def test_default_timeout_when_non_numeric(self, monkeypatch):
        monkeypatch.setenv("LLM_BASE_URL", "http://example.invalid")
        monkeypatch.setenv("LLM_API_KEY", "k")
        monkeypatch.setenv("LLM_MODEL", "m")
        monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "fast")
        assert llm.client_from_env().timeout_seconds == DEFAULT_TIMEOUT

    def test_missing_vars_empty_strings(self, monkeypatch):
        for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "LLM_TIMEOUT_SECONDS"):
            monkeypatch.delenv(name, raising=False)
        client = llm.client_from_env()
        assert client.base_url == ""
        assert client.api_key == ""
        assert client.model == ""
        assert client.timeout_seconds == DEFAULT_TIMEOUT


class TestErrorModel:
    """Edge cases (scenarios F1–F3)."""

    def test_exception_hierarchy(self):
        for exc in (llm.LLMTimeoutError, llm.LLMUnavailableError, llm.LLMRateLimitError):
            assert issubclass(exc, llm.LLMError)
        assert issubclass(llm.LLMError, Exception)

    def test_reason_attribute(self):
        err = llm.LLMUnavailableError("endpoint down")
        assert err.reason == "endpoint down"
        assert str(err) == "endpoint down"

    def test_constructor_default_timeout(self):
        client = llm.LLMClient(
            base_url="http://example.invalid", api_key="k", model="m"
        )
        assert client.timeout_seconds == DEFAULT_TIMEOUT

    def test_non_429_client_error_is_unavailable(self, fake_endpoint):
        fake_endpoint.mode = "status"
        fake_endpoint.status = 401
        client = make_client(fake_endpoint)
        with pytest.raises(llm.LLMUnavailableError) as excinfo:
            client.complete("Plan a trip")
        assert "401" in excinfo.value.reason
