# Test Cases: primes CLI (review round 1 fixes)

Covers the `main()` entry point in `primes.py`. Library-level scenarios for
`primes_below` are documented in `primes.md` and remain in `tests/test_primes.py`.

## Scenarios
1. **No arguments**: uses the default limit 100 and prints the 25 primes below 100
   to stdout; exit code 0.
2. **Explicit limit**: `main(["primes", "50"])` prints exactly the primes below 50;
   exit code 0.
3. **Limit 2 boundary via CLI**: `main(["primes", "2"])` prints `[]`; exit code 0.

## Edge cases
4. **Extra arguments**: `main(["primes", "100", "200"])` is a usage error —
   nothing on stdout, message on stderr, exit code 2.
5. **Empty-string limit**: `main(["primes", ""])` is treated as an invalid integer
   (usage error, exit code 2).

## Error handling
6. **Non-integer limit argument** (`abc`, `3.5`, `""`): friendly one-line message on
   stderr naming the offending value, no traceback, exit code 2.
7. **All failures write to stderr only** — stdout stays empty so scripted callers
   never parse error text as primes (asserted within scenarios 4 and 6).

## Regression guards (library, unchanged behavior)
8. `primes_below` suite from round 1 (`tests/test_primes.py`) must still pass
   unmodified.
