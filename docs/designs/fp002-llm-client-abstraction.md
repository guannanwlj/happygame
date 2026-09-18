# FP-002 Design: LLM Client Abstraction

Task card: `input/tasks/itinerary-planner/FP-002-llm-client-abstraction.task.md`
(sole spec). Goal: OpenAI-compatible LLM call abstraction in
`itinerary_app/llm.py` — the only channel through which the rest of the
itinerary planner talks to an LLM. Supplier parameters are injectable
(base_url / api_key / model / timeout) and failures are classified into
timeout / unavailable / rate-limited so callers (FP-009 orchestration)
never see vendor specifics.

## Approach

- New package `itinerary_app/` with a single module `itinerary_app/llm.py`;
  stdlib only (`urllib.request`, `json`, `socket`, `os`). No retries, no
  prompt building, no response parsing into itinerary structures — those
  belong to FP-007 / FP-008 / FP-009 (card §5).
- Error taxonomy per card §3.2:
  `LLMError` (base, carries non-empty `.reason`) with subclasses
  `LLMTimeoutError`, `LLMUnavailableError`, `LLMRateLimitError`. All four
  take a single `reason` argument in `__init__`.
- `LLMClient.complete(prompt)` is a single synchronous
  `POST {base_url}/chat/completions` with body
  `{"model": ..., "messages": [{"role": "user", "content": prompt}]}` and
  headers `Authorization: Bearer <api_key>` / `Content-Type: application/json`.
  The timeout is passed straight through
  `urllib.request.urlopen(..., timeout=self.timeout_seconds)`.
- Success path: read + UTF-8 decode + `json.loads`, then extract
  `choices[0].message.content` and return it as plain `str`.

## Key decisions

1. **URL joining**: `base_url.rstrip("/") + "/chat/completions"` so a
   trailing slash in configuration cannot produce `//chat/completions`.
2. **Exception mapping order** (matters because of subclass relations):
   `urllib.error.HTTPError` first (it subclasses `URLError`) — 429 →
   `LLMRateLimitError`, anything else (5xx and other 4xx such as 401/404)
   → `LLMUnavailableError`; then `TimeoutError` (alias of the socket
   timeout on py≥3.10, covers both connect and read phase) →
   `LLMTimeoutError`; then `URLError` — unwrap `.reason`, if it is itself
   a timeout → `LLMTimeoutError`, otherwise (connection refused, DNS, …)
   → `LLMUnavailableError`; finally bare `OSError` (e.g. connection reset
   during body read) → `LLMUnavailableError`. All raised errors chain the
   original via `from exc`.
3. **Non-429 4xx → unavailable**: the card only enumerates 429 / 5xx /
   connect-failure / bad-body. Auth or routing errors (401/404) mean "this
   endpoint is not usable as configured", so they collapse into
   `LLMUnavailableError` with the status code in `.reason`. The reason
   always embeds the HTTP status or underlying cause (card §3.3).
4. **Malformed 2xx body → unavailable**: JSON decode failure, missing
   `choices`, empty `choices`, missing `message`/`content`, or a non-`str`
   `content` all raise `LLMUnavailableError` ("响应体异常").
5. **`client_from_env` reads and uses whatever is set** (card §5): missing
   `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` become `""` — no startup
   validation, that is FP-013's job. `LLM_TIMEOUT_SECONDS` unset/empty →
   `30.0`; a non-numeric value also falls back to `30.0` (the layer stays
   non-crashing; configuration errors surface later as connection
   failures). Env is read at call time, not import time, matching FP-001's
   convention and making `monkeypatch.setenv` trivial in tests.
6. **Constructor attributes are public and observable** (`base_url`,
   `api_key`, `model`, `timeout_seconds`) so FP-009 and the acceptance
   test can inspect configuration without touching the network.
7. **Test strategy** (card §6): a programmable `http.server`
   `ThreadingHTTPServer` fake endpoint (`mode` / `status` / `content` /
   `delay_seconds` knobs on the server instance) that records every
   captured request for wire-format assertions. Connection-refused is
   simulated by binding a server, learning its port, shutting it down,
   and pointing the client at the now-dead port. `daemon_threads` plus a
   quiet `handle_error` keep slow/broken-pipe handler threads from
   blocking teardown or spamming stderr.

## Verification

`python3 -m pytest tests/test_fp002_llm_client.py -q` (plus the full suite).
Scenarios documented in `docs/test-cases/fp002-llm-client.md`.
