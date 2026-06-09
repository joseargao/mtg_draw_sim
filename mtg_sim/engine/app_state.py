"""
AppState — single source of truth for the running application.

Holds the Deck, GameState, all Conditions, all Simulations, and Config.
The UI reads from this; user actions mutate it through well-defined methods.

This is deliberately not a God object — it's just a named bag that prevents
passing a dozen arguments everywhere and makes persistence/serialization easy.
"""

from __future__ import annotations

import random
from typing import Optional

from .config import Config
from .deck import Deck
from .game_state import GameState
from .simulation import Condition, Simulation, SimulationRunner


class AppState:
    def __init__(self, config: Optional[Config] = None) -> None:
        self.config: Config = config or Config()
        self.deck: Optional[Deck] = None
        self.game_state: Optional[GameState] = None

        # Ordered lists (list preserves insertion order for display)
        self.conditions: list[Condition] = []
        self.simulations: list[Simulation] = []

    # ------------------------------------------------------------------
    # Deck management
    # ------------------------------------------------------------------

    def load_deck(self, deck: Deck) -> None:
        self.deck = deck
        self.game_state = GameState(
            deck=deck,
            rng=random.Random(self.config.seed),
            hand_size=self.config.hand_size,
        )
        self.game_state.reset()
        self.game_state.deal_opening_hand()

    # ------------------------------------------------------------------
    # Condition CRUD
    # ------------------------------------------------------------------

    def add_condition(self, condition: Condition) -> None:
        self.conditions.append(condition)

    def remove_condition(self, condition_id: str) -> None:
        self.conditions = [c for c in self.conditions if c.id != condition_id]
        # Cascade: remove from any simulations that reference it
        for sim in self.simulations:
            sim.conditions = [c for c in sim.conditions if c.id != condition_id]

    def get_condition(self, condition_id: str) -> Optional[Condition]:
        return next((c for c in self.conditions if c.id == condition_id), None)

    def duplicate_condition(self, condition_id: str) -> Optional[Condition]:
        src = self.get_condition(condition_id)
        if src is None:
            return None
        import dataclasses, uuid
        dup = dataclasses.replace(src, id=str(uuid.uuid4())[:8], label=src.label + " (copy)")
        self.conditions.append(dup)
        return dup

    # ------------------------------------------------------------------
    # Simulation CRUD
    # ------------------------------------------------------------------

    def add_simulation(self, simulation: Simulation) -> None:
        self.simulations.append(simulation)

    def remove_simulation(self, simulation_id: str) -> None:
        self.simulations = [s for s in self.simulations if s.id != simulation_id]

    def get_simulation(self, simulation_id: str) -> Optional[Simulation]:
        return next((s for s in self.simulations if s.id == simulation_id), None)

    # ------------------------------------------------------------------
    # Simulation execution
    # ------------------------------------------------------------------

    def run_simulation(
        self,
        simulation: Simulation,
        progress_cb=None,
    ) -> Simulation:
        """Execute a single simulation. Requires a deck to be loaded."""
        if self.game_state is None:
            raise RuntimeError("No deck loaded — call load_deck() first.")
        runner = SimulationRunner(
            self.game_state,
            cards_per_turn=self.config.cards_per_turn,
            seed=self.config.seed,
        )
        return runner.run(simulation, progress_cb=progress_cb)

    def run_all_simulations(self, progress_cb=None) -> None:
        """Run every simulation in order."""
        for sim in self.simulations:
            self.run_simulation(sim, progress_cb=progress_cb)

    # ------------------------------------------------------------------
    # Interactive game state helpers (forwarded for UI convenience)
    # ------------------------------------------------------------------

    def reset_game(self) -> None:
        if self.game_state:
            self.game_state.reset(seed=self.config.seed)
            self.game_state.deal_opening_hand()

    def advance_turn(self) -> list:
        if self.game_state is None:
            return []
        return self.game_state.advance_turn(self.config.cards_per_turn)

    # ------------------------------------------------------------------
    # Association queries (for UI display)
    # ------------------------------------------------------------------

    def simulations_using_condition(self, condition_id: str) -> list[Simulation]:
        return [s for s in self.simulations if any(c.id == condition_id for c in s.conditions)]

    def conditions_in_simulation(self, simulation_id: str) -> list[Condition]:
        sim = self.get_simulation(simulation_id)
        return sim.conditions if sim else []
