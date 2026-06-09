"""
GameState model.

Tracks the mutable per-run state: library order, hand contents, and turn.
The underlying Deck is read-only; GameState owns the shuffle and draw logic.

Design note on mulligans
------------------------
Opening hand logic is isolated in `deal_opening_hand()` so that London
mulligan rules (or any other variant) can be dropped in later without
touching the rest of the engine.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from .deck import Card, Deck


@dataclass
class GameState:
    """
    Mutable simulation state for a single game run.

    Attributes
    ----------
    deck        : The source Deck (immutable).
    library     : Ordered list of cards remaining; index 0 is top of library.
    hand        : Cards currently in hand.
    turn        : Current turn number (0 = before any turns, after opening hand).
    rng         : Random source — pass a seeded Random for reproducibility.
    hand_size   : Number of cards in the opening hand.
    """

    deck: Deck
    library: list[Card] = field(default_factory=list)
    hand: list[Card] = field(default_factory=list)
    turn: int = 0
    rng: random.Random = field(default_factory=random.Random)
    hand_size: int = 7

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def reset(self, *, seed: Optional[int] = None) -> None:
        """
        Full reset: shuffle library, clear hand, return to turn 0.
        Optionally re-seed the RNG for reproducibility.
        """
        if seed is not None:
            self.rng.seed(seed)
        self.library = list(self.deck.cards)
        self.rng.shuffle(self.library)
        self.hand = []
        self.turn = 0

    def deal_opening_hand(self) -> None:
        """
        Draw the opening hand from a freshly shuffled library.
        Call after reset().

        Extension point: replace this method to implement mulligan logic
        (London, Paris, etc.) without touching anything else.
        """
        self._draw_to_hand(self.hand_size)

    # ------------------------------------------------------------------
    # Turn progression
    # ------------------------------------------------------------------

    def advance_turn(self, cards_per_turn: int = 1) -> list[Card]:
        """
        Advance to the next turn and draw `cards_per_turn` cards.
        Returns the cards drawn this turn (empty list if library is empty).
        """
        self.turn += 1
        return self._draw_to_hand(cards_per_turn)

    # ------------------------------------------------------------------
    # Inspection helpers
    # ------------------------------------------------------------------

    @property
    def hand_counts(self) -> dict[str, int]:
        """name → count for cards currently in hand."""
        return dict(sorted(Counter(c.name for c in self.hand).items()))

    @property
    def library_counts(self) -> dict[str, int]:
        """name → count for cards remaining in library."""
        return dict(sorted(Counter(c.name for c in self.library).items()))

    @property
    def hand_size_current(self) -> int:
        return len(self.hand)

    @property
    def library_size(self) -> int:
        return len(self.library)

    def count_in_hand(self, card_name: str) -> int:
        """How many copies of `card_name` are currently in hand?"""
        return sum(1 for c in self.hand if c.name == card_name)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _draw_to_hand(self, n: int) -> list[Card]:
        """Pop up to n cards from top of library into hand. Returns drawn cards."""
        drawn: list[Card] = []
        for _ in range(n):
            if not self.library:
                break
            card = self.library.pop(0)
            self.hand.append(card)
            drawn.append(card)
        return drawn

    def __repr__(self) -> str:
        return (
            f"GameState(turn={self.turn}, "
            f"hand={self.hand_size_current}, "
            f"library={self.library_size})"
        )
