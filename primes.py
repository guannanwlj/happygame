"""Prime number generation via the Sieve of Eratosthenes."""

import math
import sys

DEFAULT_LIMIT = 100
USAGE = "usage: primes [limit]"


def primes_below(limit):
    """Return all primes strictly smaller than limit, in ascending order."""
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TypeError(f"limit must be an integer, got {type(limit).__name__}")
    if limit <= 2:
        return []
    is_prime = [True] * limit
    is_prime[0] = is_prime[1] = False
    # Largest candidate is limit - 1, so sieving up to sqrt(limit - 1) suffices.
    for p in range(2, math.isqrt(limit - 1) + 1):
        if is_prime[p]:
            for multiple in range(p * p, limit, p):
                is_prime[multiple] = False
    return [n for n, prime in enumerate(is_prime) if prime]


def main(argv):
    """Run the CLI: print primes below the optional integer limit.

    Returns the process exit code: 0 on success, 2 on usage errors
    (non-integer or extra arguments), which are reported on stderr.
    """
    if len(argv) > 2:
        print(f"error: unexpected extra argument: {argv[2]!r}\n{USAGE}", file=sys.stderr)
        return 2
    try:
        limit = int(argv[1]) if len(argv) > 1 else DEFAULT_LIMIT
    except ValueError:
        print(f"error: limit must be an integer, got {argv[1]!r}\n{USAGE}", file=sys.stderr)
        return 2
    print(primes_below(limit))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
