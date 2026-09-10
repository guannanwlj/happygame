"""Entry point: ``python3 -m social_app`` starts the social platform web app.

The bind address comes from SOCIAL_HOST (default 127.0.0.1) and SOCIAL_PORT
(default 8000), resolved by `bind_address()` at startup.
"""

from social_app.app import bind_address, create_server


def main() -> None:
    host, port = bind_address()
    with create_server(host=host, port=port) as server:
        print(f"social_app listening on http://{host}:{port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
