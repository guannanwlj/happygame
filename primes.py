"""Prime number generation via the Sieve of Eratosthenes."""

import math
import sys

DEFAULT_LIMIT = 100


def primes_below(limit):
    """Return all primes strictly smaller than limit, in ascending order."""
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TypeError(f"limit must be an integer, got {type(limit).__name__}")
    if limit <= 2:
        return []
    is_prime = [True] * limit
    is_prime[0] = is_prime[1] = False
    for p in range(2, math.isqrt(limit - 1) + 1):
        if is_prime[p]:
            for multiple in range(p * p, limit, p):
                is_prime[multiple] = False
    return [n for n, prime in enumerate(is_prime) if prime]


def main(argv):
    limit = int(argv[1]) if len(argv) > 1 else DEFAULT_LIMIT
    print(primes_below(limit))


if __name__ == "__main__":
    main(sys.argv)
