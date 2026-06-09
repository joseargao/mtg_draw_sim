"""MTG Sim — entrypoint."""
from __future__ import annotations

import sys
import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mtg_sim",
        description="MTG Arena deck draw simulator",
    )
    parser.add_argument(
        "deck",
        nargs="?",
        metavar="DECK_FILE",
        help="MTG Arena decklist (.txt). Omit to launch with demo deck.",
    )
    parser.add_argument(
        "--config", "-c",
        metavar="CONFIG_FILE",
        default="config.ini",
        help="INI config file (default: config.ini)",
    )
    args = parser.parse_args()

    from mtg_sim.engine.app_state import AppState
    from mtg_sim.engine.config import Config
    from mtg_sim.engine.deck import Deck
    from mtg_sim.ui.app import run, build_demo_state

    # Load config if present
    cfg_path = Path(args.config)
    config = Config.load(cfg_path) if cfg_path.exists() else Config()

    # Load deck
    if args.deck:
        deck_path = Path(args.deck)
        if not deck_path.exists():
            print(f"Error: deck file not found: {deck_path}", file=sys.stderr)
            sys.exit(1)
        try:
            deck = Deck.from_file(deck_path)
        except ValueError as e:
            print(f"Error parsing deck: {e}", file=sys.stderr)
            sys.exit(1)
        state = AppState(config=config)
        state.load_deck(deck)
        run(state)
    else:
        # No deck provided — launch with demo data
        state = build_demo_state()
        state.config = config
        run(state)


if __name__ == "__main__":
    main()