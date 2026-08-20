# Test Cases: primes_below

## Scenarios
1. **Typical case**: `primes_below(100)` returns the 25 known primes below 100
   (2, 3, 5, ..., 97).
2. **Strictly smaller**: `primes_below(31)` must NOT include 31 itself.

## Edge cases
3. **limit = 2**: returns `[]` (no primes strictly below 2).
4. **limit = 0 / negative limit**: returns `[]`.
5. **Smallest prime**: `primes_below(3)` returns `[2]`.
6. **limit = 1**: returns `[]`.

## Error handling
7. **Non-integer input** (`float`, `str`, `None`): raises `TypeError`.

## Property checks
8. Every returned value has no divisor other than 1 and itself (brute-force check).
9. Result is strictly increasing and all elements are ints.
