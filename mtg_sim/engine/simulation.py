"""
Condition, Simulation, and SimulationRunner.

Condition
---------
An atomic rule: "card_name comparator count by turn_deadline"

Simulation
----------
A named experiment. Stores condition_indices — integer indices into
AppState.conditions — rather than condition object references.
This avoids stale reference bugs when conditions are edited in place.

SimulationRunner
----------------
Executes a Simulation against a GameState repeatedly.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Comparators
# ---------------------------------------------------------------------------

class Comparator(str, Enum):
    GTE = ">="
    LTE = "<="
    EQ  = "=="
    GT  = ">"
    LT  = "<"

    def evaluate(self, actual: int, threshold: int) -> bool:
        match self:
            case Comparator.GTE: return actual >= threshold
            case Comparator.LTE: return actual <= threshold
            case Comparator.EQ:  return actual == threshold
            case Comparator.GT:  return actual >  threshold
            case Comparator.LT:  return actual <  threshold

    def __str__(self) -> str:
        return self.value


# ---------------------------------------------------------------------------
# SuccessRule
# ---------------------------------------------------------------------------

class SuccessRule(str, Enum):
    ANY = "ANY"
    ALL = "ALL"


# ---------------------------------------------------------------------------
# Condition
# ---------------------------------------------------------------------------

@dataclass
class Condition:
    """
    A single drawable condition evaluated against the hand.

    id is kept for widget DOM purposes only (button IDs in modals).
    It plays no role in simulation logic.
    """
    card_name: str
    comparator: Comparator
    count: int
    turn_deadline: int
    label: str = ""

    def evaluate(self, hand_counts: dict[str, int], current_turn: int) -> bool:
        if current_turn > self.turn_deadline:
            return False
        actual = hand_counts.get(self.card_name, 0)
        return self.comparator.evaluate(actual, self.count)

    @property
    def display_label(self) -> str:
        return self.label or self._auto_label()

    def _auto_label(self) -> str:
        return (
            f"{self.card_name} {self.comparator} {self.count} "
            f"by turn {self.turn_deadline}"
        )

    def __str__(self) -> str:
        return self.display_label

    def __repr__(self) -> str:
        return f"Condition({self._auto_label()!r})"


# ---------------------------------------------------------------------------
# SimulationResult
# ---------------------------------------------------------------------------

@dataclass
class ConditionResult:
    condition_index: int
    satisfied: bool


@dataclass
class RunResult:
    condition_results: list[ConditionResult]
    simulation_success: bool


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

@dataclass
class Simulation:
    """
    A named experiment.

    condition_indices: list of int — indices into AppState.conditions.
    The runner resolves these to actual Condition objects at run time,
    so editing a condition is always reflected without any reference juggling.
    """
    label: str = ""
    condition_indices: list[int] = field(default_factory=list)
    success_rule: SuccessRule = SuccessRule.ALL
    run_count: int = 10_000
    turn_limit: Optional[int] = None

    # Results
    total_runs: int = 0
    success_count: int = 0
    condition_hits: dict[int, int] = field(default_factory=dict)  # index -> hits
    elapsed_seconds: float = 0.0
    status: str = "READY"

    @property
    def display_label(self) -> str:
        return self.label or self._auto_label()

    def _auto_label(self) -> str:
        if not self.condition_indices:
            return "(no conditions)"
        indices = ", ".join(str(i+1) for i in self.condition_indices)
        rule = "All" if self.success_rule == SuccessRule.ALL else "Any"
        return f"{rule} of condition {indices}"

    def effective_turn_limit(self, all_conditions: list[Condition]) -> int:
        if self.turn_limit is not None:
            return self.turn_limit
        conditions = self._resolve(all_conditions)
        if not conditions:
            return 1
        return max(c.turn_deadline for c in conditions)

    def _resolve(self, all_conditions: list[Condition]) -> list[Condition]:
        """Return the actual Condition objects for this simulation's indices."""
        return [
            all_conditions[i]
            for i in self.condition_indices
            if 0 <= i < len(all_conditions)
        ]

    @property
    def success_rate(self) -> Optional[float]:
        if self.total_runs == 0:
            return None
        return self.success_count / self.total_runs

    @property
    def success_rate_pct(self) -> str:
        r = self.success_rate
        return f"{r * 100:.1f}%" if r is not None else "--"

    def condition_hit_rate(self, index: int) -> Optional[float]:
        if self.total_runs == 0:
            return None
        return self.condition_hits.get(index, 0) / self.total_runs

    def condition_hit_rate_pct(self, index: int) -> str:
        r = self.condition_hit_rate(index)
        return f"{r * 100:.1f}%" if r is not None else "--"

    def _reset_results(self, all_conditions: list[Condition]) -> None:
        self.total_runs = 0
        self.success_count = 0
        self.condition_hits = {i: 0 for i in self.condition_indices
                               if 0 <= i < len(all_conditions)}
        self.elapsed_seconds = 0.0
        self.status = "RUNNING"

    def _record_run(self, run: RunResult) -> None:
        self.total_runs += 1
        if run.simulation_success:
            self.success_count += 1
        for cr in run.condition_results:
            if cr.satisfied:
                self.condition_hits[cr.condition_index] = (
                    self.condition_hits.get(cr.condition_index, 0) + 1
                )

    def __str__(self) -> str:
        return f"{self.display_label} | {self.success_rate_pct} over {self.total_runs} runs"


# ---------------------------------------------------------------------------
# SimulationRunner
# ---------------------------------------------------------------------------

class SimulationRunner:
    def __init__(
        self,
        game_state,
        cards_per_turn: int = 1,
        seed: Optional[int] = None,
    ) -> None:
        self.game_state = game_state
        self.cards_per_turn = cards_per_turn
        self._base_seed = seed

    def run(
        self,
        simulation: Simulation,
        all_conditions: list[Condition],
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> Simulation:
        simulation._reset_results(all_conditions)
        conditions = simulation._resolve(all_conditions)
        gs = self.game_state
        t0 = time.monotonic()

        for i in range(simulation.run_count):
            run_seed = (self._base_seed + i) if self._base_seed is not None else None
            gs.reset(seed=run_seed)
            gs.deal_opening_hand()
            run = self._execute_run(simulation, conditions, gs)
            simulation._record_run(run)
            if progress_cb is not None:
                progress_cb(i + 1, simulation.run_count)

        simulation.elapsed_seconds = time.monotonic() - t0
        simulation.status = "COMPLETE"
        return simulation

    def _execute_run(
        self,
        simulation: Simulation,
        conditions: list[Condition],
        gs,
    ) -> RunResult:
        turn_limit = simulation.turn_limit or (
            max(c.turn_deadline for c in conditions) if conditions else 1
        )
        satisfied: dict[int, bool] = {
            idx: False for idx in simulation.condition_indices
        }

        self._evaluate_all(conditions, simulation.condition_indices, satisfied, gs)
        for _ in range(turn_limit):
            gs.advance_turn(self.cards_per_turn)
            self._evaluate_all(conditions, simulation.condition_indices, satisfied, gs)

        condition_results = [
            ConditionResult(idx, satisfied[idx])
            for idx in simulation.condition_indices
        ]

        flags = [satisfied[idx] for idx in simulation.condition_indices]
        if simulation.success_rule == SuccessRule.ANY:
            sim_success = any(flags) if flags else False
        else:
            sim_success = all(flags) if flags else False

        return RunResult(condition_results=condition_results, simulation_success=sim_success)

    @staticmethod
    def _evaluate_all(
        conditions: list[Condition],
        indices: list[int],
        satisfied: dict[int, bool],
        gs,
    ) -> None:
        hand = gs.hand_counts
        turn = gs.turn
        for idx, c in zip(indices, conditions):
            if not satisfied[idx]:
                if c.evaluate(hand, turn):
                    satisfied[idx] = True