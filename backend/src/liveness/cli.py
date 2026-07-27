"""CLI entrypoint: `liveness serve`."""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="liveness", description="Liveness identity platform")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the Checks API")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")

    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        uvicorn.run(
            "liveness.api:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )


if __name__ == "__main__":
    main()
