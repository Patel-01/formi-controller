"""Outcome-first controller — entry point for `python -m controller`."""
import argparse
import logging

from .core import Controller


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    ap = argparse.ArgumentParser(description="Formi outcome-first controller")
    ap.add_argument("--url", default="http://127.0.0.1:8700",
                    help="Simulator base URL")
    ap.add_argument("--db", default="controller.db",
                    help="SQLite database path")
    args = ap.parse_args()
    ctrl = Controller(args.url, args.db)
    ctrl.run()


if __name__ == "__main__":
    main()
