"""OpenAI-compatible LLM call abstraction (FP-002).

The single channel through which the itinerary planner talks to an LLM:
generation flows (FP-009) call ``LLMClient.complete`` and never touch the
network directly. Supplier parameters (base_url / api_key / model /
timeout) are injected; failures are classified into timeout / unavailable /
rate-limited so callers need no vendor knowledge.

Wire format (task card §3.2): ``POST {base_url}/chat/completions`` with
JSON body ``{"model": ..., "messages": [{"role": "user", "content": ...}]}``,
``Authorization: Bearer <api_key>`` and ``Content-Type: application/json``
headers; on 2xx the generated text is ``choices[0].message.content``.
"""

import json
import os
import urllib.error
import urllib.request

BASE_URL_ENV = "LLM_BASE_URL"
API_KEY_ENV = "LLM_API_KEY"
MODEL_ENV = "LLM_MODEL"
TIMEOUT_ENV = "LLM_TIMEOUT_SECONDS"
DEFAULT_TIMEOUT_SECONDS = 30.0

CHAT_COMPLETIONS_PATH = "/chat/completions"


class LLMError(Exception):
    """Base class for all LLM channel failures; ``.reason`` is human-readable."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class LLMTimeoutError(LLMError):
    """The supplier did not answer within ``timeout_seconds``."""


class LLMUnavailableError(LLMError):
    """Endpoint unreachable, connection failed, HTTP 5xx (or other HTTP
    error besides 429), or a 2xx response with an unusable body."""


class LLMRateLimitError(LLMError):
    """The supplier answered HTTP 429 (rate limited)."""


class LLMClient:
    """Minimal synchronous OpenAI-compatible chat-completions client."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def complete(self, prompt: str) -> str:
        """Send ``prompt`` as a single user message; return the reply text.

        Raises ``LLMTimeoutError`` / ``LLMUnavailableError`` /
        ``LLMRateLimitError`` (each carrying a non-empty ``.reason``).
        """
        url = self.base_url.rstrip("/") + CHAT_COMPLETIONS_PATH
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        body = self._exchange(request)
        return self._extract_content(body)

    def _exchange(self, request: urllib.request.Request) -> bytes:
        """Perform the HTTP round trip, mapping transport errors to LLM*Error."""
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds
            ) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            reason = f"LLM endpoint returned HTTP {exc.code}"
            if exc.code == 429:
                raise LLMRateLimitError(reason) from exc
            raise LLMUnavailableError(reason) from exc
        except TimeoutError as exc:  # socket.timeout aliases TimeoutError
            raise LLMTimeoutError(
                f"LLM request timed out after {self.timeout_seconds} s"
            ) from exc
        except urllib.error.URLError as exc:
            # A connect-phase timeout arrives wrapped in URLError.reason
            # (socket.timeout aliases TimeoutError on py>=3.10).
            if isinstance(exc.reason, TimeoutError):
                raise LLMTimeoutError(
                    f"LLM request timed out after {self.timeout_seconds} s"
                ) from exc
            raise LLMUnavailableError(
                f"LLM endpoint unreachable: {exc.reason}"
            ) from exc
        except OSError as exc:  # e.g. connection reset during body read
            raise LLMUnavailableError(
                f"LLM connection failed: {exc}"
            ) from exc

    def _extract_content(self, body: bytes) -> str:
        """Pull ``choices[0].message.content`` out of a 2xx response body."""
        try:
            parsed = json.loads(body.decode("utf-8"))
            content = parsed["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailableError(
                f"Malformed LLM response body: {exc!r}"
            ) from exc
        if not isinstance(content, str):
            raise LLMUnavailableError(
                f"Malformed LLM response body: content is "
                f"{type(content).__name__}, expected str"
            )
        return content


def client_from_env() -> LLMClient:
    """Build a client from the LLM_* environment variables (read-and-use).

    ``LLM_TIMEOUT_SECONDS`` defaults to 30 when unset or non-numeric;
    missing string variables become ``""`` (startup checks belong to FP-013).
    """
    raw_timeout = os.environ.get(TIMEOUT_ENV, "").strip()
    try:
        timeout_seconds = float(raw_timeout) if raw_timeout else DEFAULT_TIMEOUT_SECONDS
    except ValueError:
        timeout_seconds = DEFAULT_TIMEOUT_SECONDS
    return LLMClient(
        base_url=os.environ.get(BASE_URL_ENV, ""),
        api_key=os.environ.get(API_KEY_ENV, ""),
        model=os.environ.get(MODEL_ENV, ""),
        timeout_seconds=timeout_seconds,
    )
