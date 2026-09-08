# happygame

## Primes

Generate all prime numbers strictly smaller than a limit (default 100):

```console
$ python3 primes.py            # primes below 100
$ python3 primes.py 50         # primes below 50
```

Usage errors (non-integer or extra arguments) print a message to stderr and
exit with code 2. Run the tests with `python3 -m pytest`.

## Social App

Install the dependencies and start the local development server
(single process, Flask built-in server, loopback only — public deployment
is out of scope):

```console
$ pip install -r requirements.txt
$ python3 -m social_app
```

On startup the app idempotently creates the SQLite schema
(`social_app/db.py::init_db()`) and then serves the Flask application
built by `social_app/app.py::create_app()` at `http://127.0.0.1:5000/`.
The listen port can be changed with the `SOCIAL_PORT` environment variable.

### Storage location (`SOCIAL_DB`)

The SQLite database file defaults to `social_platform.db` in the working
directory. Point `SOCIAL_DB` at any path to use a different file; the
variable is read at call time, so it can be changed per run. Data persists
across restarts:

```console
$ SOCIAL_DB=/tmp/social-platform.db python3 -m social_app
```

Run the storage and runtime tests with:

```console
$ python3 -m pytest tests/test_fp001_storage.py tests/test_fp004_runtime.py -q
```
