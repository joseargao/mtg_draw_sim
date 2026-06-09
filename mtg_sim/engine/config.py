"""
Config model — INI-based configuration with sensible defaults.

Example INI file
----------------
[deck]
source = my_deck.txt

[game]
hand_size        = 7
cards_per_turn   = 1
turn_limit       = 8

[simulation]
run_count = 10000
seed      =         ; leave blank for random

Usage
-----
    cfg = Config.load("config.ini")
    cfg = Config()               # all defaults
"""

from __future__ import annotations

import configparser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Config:
    # [deck]
    deck_source: str = ""

    # [game]
    hand_size: int = 7
    cards_per_turn: int = 1
    turn_limit: int = 8

    # [simulation]
    run_count: int = 10_000
    seed: Optional[int] = None

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        p = Path(path)
        parser = configparser.ConfigParser()
        parser.read(p, encoding="utf-8")

        cfg = cls()

        if "deck" in parser:
            cfg.deck_source = parser["deck"].get("source", cfg.deck_source)

        if "game" in parser:
            g = parser["game"]
            cfg.hand_size      = int(g.get("hand_size",      cfg.hand_size))
            cfg.cards_per_turn = int(g.get("cards_per_turn", cfg.cards_per_turn))
            cfg.turn_limit     = int(g.get("turn_limit",     cfg.turn_limit))

        if "simulation" in parser:
            s = parser["simulation"]
            cfg.run_count = int(s.get("run_count", cfg.run_count))
            raw_seed = s.get("seed", "").strip()
            cfg.seed = int(raw_seed) if raw_seed else None

        return cfg

    def save(self, path: str | Path) -> None:
        parser = configparser.ConfigParser()
        parser["deck"]       = {"source": self.deck_source}
        parser["game"]       = {
            "hand_size":        str(self.hand_size),
            "cards_per_turn":   str(self.cards_per_turn),
            "turn_limit":       str(self.turn_limit),
        }
        parser["simulation"] = {
            "run_count": str(self.run_count),
            "seed":      str(self.seed) if self.seed is not None else "",
        }
        with open(path, "w", encoding="utf-8") as f:
            parser.write(f)

    def __repr__(self) -> str:
        return (
            f"Config(deck={self.deck_source!r}, hand={self.hand_size}, "
            f"cpp={self.cards_per_turn}, turns={self.turn_limit}, "
            f"runs={self.run_count}, seed={self.seed})"
        )
