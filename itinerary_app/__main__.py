"""Entry point: ``python3 -m itinerary_app`` starts the itinerary web app.

The bind address comes from ITIN_HOST (default 127.0.0.1) and ITIN_PORT
(default 8000), resolved at startup — names shared with FP-013's
configuration table.
"""

from itinerary_app.app import bind_address, create_server


def main() -> None:
    host, port = bind_address()
    with create_server(host=host, port=port) as server:
        print(f"itinerary_app listening on http://{host}:{port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
