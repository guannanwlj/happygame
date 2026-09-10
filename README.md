# happygame

## Primes

Generate all prime numbers strictly smaller than a limit (default 100):

```console
$ python3 primes.py            # primes below 100
$ python3 primes.py 50         # primes below 50
```

Usage errors (non-integer or extra arguments) print a message to stderr and
exit with code 2.

## Testing

Install the test-only dependencies, then run the full suite from the
repository root:

```console
$ python3 -m pip install -r requirements-dev.txt
$ python3 -m pytest -q
```
