"""
Deck model.

Parses MTG Arena export format and expands into an immutable flat card list.

MTG Arena format example:
    Deck
    4 Lightning Bolt
    2 Goblin Guide
    ...

    Sideboard
    2 Pyroblast
    ...

Only the main deck section is imported; sideboard is ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


# ---------------------------------------------------------------------------
# Card
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Card:
    """A single card. Immutable and hashable."""
    name: str

    def __str__(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# Deck
# ---------------------------------------------------------------------------

@dataclass
class Deck:
    """
    An immutable logical deck parsed from an MTG Arena decklist.

    `cards` is the fully-expanded list (e.g. 4 copies → 4 Card objects).
    Use `counts` for a name → quantity mapping.
    """
    cards: tuple[Card, ...]          # expanded, immutable
    source: str = ""                  # filename or label, for display

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_text(cls, text: str, source: str = "") -> "Deck":
        """Parse an MTG Arena decklist string and return a Deck."""
        cards: list[Card] = []
        in_sideboard = False

        for raw_line in text.splitlines():
            line = raw_line.strip()

            # Section headers
            if re.match(r"^(sideboard|commander|companion)$", line, re.I):
                in_sideboard = True
                continue
            if re.match(r"^deck$", line, re.I):
                in_sideboard = False
                continue

            # Skip blank lines and section separators
            if not line:
                continue

            if in_sideboard:
                continue

            # Match "N Card Name" or "N Card Name (SET) 123"
            m = re.match(r"^(\d+)\s+(.+?)(?:\s+\([A-Z0-9]+\)\s+\d+)?$", line)
            if m:
                qty = int(m.group(1))
                name = m.group(2).strip()
                cards.extend(Card(name) for _ in range(qty))

        if not cards:
            raise ValueError("No cards found in decklist — check the format.")

        return cls(cards=tuple(cards), source=source)

    @classmethod
    def from_file(cls, path: str | Path) -> "Deck":
        p = Path(path)
        return cls.from_text(p.read_text(encoding="utf-8"), source=p.name)

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    @property
    def counts(self) -> dict[str, int]:
        """Sorted name → count mapping (alphabetical)."""
        result: dict[str, int] = {}
        for card in self.cards:
            result[card.name] = result.get(card.name, 0) + 1
        return dict(sorted(result.items()))

    @property
    def size(self) -> int:
        return len(self.cards)

    def __len__(self) -> int:
        return self.size

    def __repr__(self) -> str:
        return f"Deck({self.size} cards, source={self.source!r})"