# FP-002 Test Scenarios — LLM Client Abstraction

Module under test: `itinerary_app/llm.py` (spec: task card FP-002 §3.2/§3.3/§7/§8).
All network scenarios run against a programmable local fake OpenAI-compatible
endpoint (`http.server.ThreadingHTTPServer`, card §6) — no real supplier, no
shared state between tests.

## A. Acceptance 1 — success path

| # | Scenario | Expected |
|---|----------|----------|
| A1 | Fake endpoint returns 200 with `choices[0].message.content = "ITIN_OK"`; `complete("...")` | Returns exactly `"ITIN_OK"`; return value is `str` (no vendor types leak) |
| A2 | Card §6 seed content `"## 第1天 …"` | Round-trips unchanged |
| A3 | Wire format as seen by the fake endpoint | `POST` to `/chat/completions`, header `Authorization: Bearer <api_key>`, header `Content-Type: application/json`, JSON body `{"model": <model>, "messages": [{"role": "user", "content": <prompt>}]}` |
| A4 | `base_url` configured with a trailing slash | Request path is still `/chat/completions` (no `//`) |

## B. Acceptance 2 — timeout classification

| # | Scenario | Expected |
|---|----------|----------|
| B1 | Fake endpoint sleeps longer than `timeout_seconds` before responding | Raises `LLMTimeoutError`; `.reason` is a non-empty string mentioning the timeout |

## C. Acceptance 3 — unavailable classification

| # | Scenario | Expected |
|---|----------|----------|
| C1 | No listener on the target port (server bound then shut down) | Raises `LLMUnavailableError`; `.reason` non-empty |
| C2 | Fake endpoint returns HTTP 500 | Raises `LLMUnavailableError`; `.reason` mentions status 500 |
| C3 | Fake endpoint returns HTTP 503 | Raises `LLMUnavailableError` (any 5xx, not just 500) |
| C4 | 200 but body is not valid JSON | Raises `LLMUnavailableError`; `.reason` non-empty (malformed body) |
| C5 | 200 but JSON lacks `choices` / has empty `choices` / lacks `message.content` | Raises `LLMUnavailableError` (missing-field variants) |
| C6 | 200 but `content` is not a string | Raises `LLMUnavailableError` |

## D. Acceptance 4 — rate-limit classification

| # | Scenario | Expected |
|---|----------|----------|
| D1 | Fake endpoint returns HTTP 429 | Raises `LLMRateLimitError`; `.reason` non-empty |

## E. Acceptance 5 — `client_from_env` configuration

| # | Scenario | Expected |
|---|----------|----------|
| E1 | All four env vars set (`LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`/`LLM_TIMEOUT_SECONDS`) | Returned client reflects them on observable attributes `base_url` / `api_key` / `model` / `timeout_seconds` |
| E2 | `LLM_TIMEOUT_SECONDS` unset | `timeout_seconds` defaults to `30.0` |
| E3 | `LLM_TIMEOUT_SECONDS` non-numeric | Falls back to `30.0` without raising (design decision: read-and-use, no validation here) |

## F. Edge cases / error-model integrity

| # | Scenario | Expected |
|---|----------|----------|
| F1 | Class hierarchy | `LLMTimeoutError`, `LLMUnavailableError`, `LLMRateLimitError` are all subclasses of `LLMError`; `LLMError` subclasses `Exception` |
| F2 | Constructor defaults | `LLMClient(...)` without `timeout_seconds` uses `30.0` |
| F3 | Non-429 4xx (HTTP 401) | Raises `LLMUnavailableError` with status in `.reason` (design decision D3) |
| F4 | `client_from_env` with unset vars | Empty strings, no exception raised at construction (FP-013 owns startup checks) |

Skeleton/test file: `tests/test_fp002_llm_client.py`.
