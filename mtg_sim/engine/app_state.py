"""
AppState — single source of truth for the running application.
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
        self.conditions: list[Condition] = []
        self.simulations: list[Simulation] = []

    # ------------------------------------------------------------------
    # Deck
    # ------------------------------------------------------------------

    def load_deck(self, deck: Deck) -> None:
        self.deck = deck
        self.game_state = GameState(
            deck=deck,
            rng=random.Random(self.config.seed),
            hand_size=self.config.hand_size,
        )
        self.game_state.reset()

    # ------------------------------------------------------------------
    # Condition CRUD
    # ------------------------------------------------------------------

    def add_condition(self, condition: Condition) -> None:
        self.conditions.append(condition)

    def remove_condition(self, index: int) -> None:
        """
        Remove condition at index. Update all simulation indices to account
        for the removed entry — indices above it shift down by one.
        """
        if not (0 <= index < len(self.conditions)):
            return
        self.conditions.pop(index)
        for sim in self.simulations:
            sim.condition_indices = [
                i - 1 if i > index else i
                for i in sim.condition_indices
                if i != index
            ]
            sim.status = "READY"
            sim.total_runs = 0
            sim.success_count = 0

    def replace_condition(self, index: int, condition: Condition) -> None:
        """Replace condition at index. No reference juggling needed."""
        if 0 <= index < len(self.conditions):
            self.conditions[index] = condition
            # Reset any sim using this condition so it re-runs
            for sim in self.simulations:
                if index in sim.condition_indices:
                    sim.status = "READY"
                    sim.total_runs = 0
                    sim.success_count = 0

    # ------------------------------------------------------------------
    # Simulation CRUD
    # ------------------------------------------------------------------

    def add_simulation(self, simulation: Simulation) -> None:
        self.simulations.append(simulation)

    def remove_simulation(self, index: int) -> None:
        if 0 <= index < len(self.simulations):
            self.simulations.pop(index)

    def replace_simulation(self, index: int, simulation: Simulation) -> None:
        if 0 <= index < len(self.simulations):
            self.simulations[index] = simulation

    # ------------------------------------------------------------------
    # Running simulations
    # ------------------------------------------------------------------

    def run_simulation(
        self,
        simulation: Simulation,
        progress_cb=None,
    ) -> Simulation:
        if self.game_state is None:
            raise RuntimeError("No deck loaded.")
        runner = SimulationRunner(
            self.game_state,
            cards_per_turn=self.config.cards_per_turn,
            seed=self.config.seed,
        )
        return runner.run(simulation, self.conditions, progress_cb=progress_cb)

    def run_all_simulations(self, progress_cb=None) -> None:
        for sim in self.simulations:
            self.run_simulation(sim, progress_cb=progress_cb)

    # ------------------------------------------------------------------
    # Interactive helpers
    # ------------------------------------------------------------------

    def reset_game(self) -> None:
        if self.game_state:
            self.game_state.reset(seed=self.config.seed)
            self.game_state.deal_opening_hand()

    def advance_turn(self) -> list:
        if self.game_state is None:
            return []
        return self.game_state.advance_turn(self.config.cards_per_turn)