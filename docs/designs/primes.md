# Design: Prime Number Generation

## Goal
Generate all prime numbers smaller than a given limit (default task: limit = 100).

## Approach
Sieve of Eratosthenes — O(n log log n) time, O(n) space.

Algorithm:
1. Build a boolean array `is_prime[0..limit-1]`, initialized to True (indices 0 and 1 marked False).
2. For each integer p from 2 up to sqrt(limit), if p is still marked prime, mark all multiples of p (starting at p*p) as composite.
3. Collect all indices still marked True.

## Key decisions
- `primes_below(limit)` returns primes strictly smaller than `limit` (matches the task wording "smaller than 100").
- Limits < 2 return an empty list (no primes below 2).
- Input must be an integer; non-integers raise `TypeError`.
- CLI entry point: `python primes.py [limit]` prints the primes for the given limit (default 100).

## Files
- `primes.py` — implementation + CLI
- `tests/test_primes.py` — unit tests (pytest; run with `pytest` or `python -m pytest` from the repo root)
