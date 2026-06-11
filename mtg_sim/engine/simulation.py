"""
Condition, Simulation, and SimulationRunner.

Condition
---------
An atomic rule: "card_name comparator count by turn_deadline"
e.g. "Forest >= 2 by turn 2"

Comparators supported: >=, <=, ==, >, <

Simulation
----------
A named experiment grouping one or more Conditions, a success rule (ANY/ALL),
a run count, and a turn limit.  Holds its own results after running.

SimulationRunner
----------------
Executes a Simulation against a GameState repeatedly and records outcomes.
Each run is independent: reset → deal opening hand → advance turns → evaluate.
"""

from __future__ import annotations

import random
import time
import uuid
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
    ANY = "ANY"   # OR  — simulation succeeds if at least one condition met
    ALL = "ALL"   # AND — simulation succeeds only if every condition met


# ---------------------------------------------------------------------------
# Condition
# ---------------------------------------------------------------------------

@dataclass
class Condition:
    """
    A single drawable condition evaluated against the hand at or before
    `turn_deadline`.

    Attributes
    ----------
    card_name     : Exact card name (case-sensitive, matches deck).
    comparator    : One of >=, <=, ==, >, <
    count         : The threshold to compare against.
    turn_deadline : The latest turn by which the condition must be satisfied.
    label         : Optional human-readable name shown in UI.
    id            : Stable unique identifier (auto-generated).
    """

    card_name: str
    comparator: Comparator
    count: int
    turn_deadline: int
    label: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, hand_counts: dict[str, int], current_turn: int) -> bool:
        """
        Returns True if the condition is satisfied given the current hand
        and turn.  Always False if we've already passed the deadline.
        """
        if current_turn > self.turn_deadline:
            return False
        actual = hand_counts.get(self.card_name, 0)
        return self.comparator.evaluate(actual, self.count)

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

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
        return f"Condition({self._auto_label()!r}, id={self.id!r})"


# ---------------------------------------------------------------------------
# SimulationResult  (per-run snapshot; accumulated into Simulation)
# ---------------------------------------------------------------------------

@dataclass
class ConditionResult:
    """Whether a single condition was ever satisfied within a run."""
    condition_id: str
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

    Attributes
    ----------
    name            : Display name.
    conditions      : List of Condition objects (references, not copies).
    success_rule    : ANY (OR) or ALL (AND) over conditions.
    run_count       : How many independent runs to perform.
    turn_limit      : How many turns to simulate per run. If None, derived
                      from max condition turn_deadline.
    id              : Stable unique identifier.

    Results (populated after running)
    ----------------------------------
    total_runs      : Runs completed.
    success_count   : Runs where simulation_success was True.
    condition_hits  : {condition_id: hit_count} across all runs.
    elapsed_seconds : Wall-clock time for the last batch.
    status          : "READY" | "RUNNING" | "COMPLETE"
    """

    name: str
    conditions: list[Condition] = field(default_factory=list)
    success_rule: SuccessRule = SuccessRule.ALL
    run_count: int = 10_000
    turn_limit: Optional[int] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    # Results
    total_runs: int = 0
    success_count: int = 0
    condition_hits: dict[str, int] = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    status: str = "READY"

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def effective_turn_limit(self) -> int:
        """Turn limit: explicit override OR max deadline across conditions."""
        if self.turn_limit is not None:
            return self.turn_limit
        if not self.conditions:
            return 1
        return max(c.turn_deadline for c in self.conditions)

    @property
    def success_rate(self) -> Optional[float]:
        if self.total_runs == 0:
            return None
        return self.success_count / self.total_runs

    @property
    def success_rate_pct(self) -> str:
        r = self.success_rate
        return f"{r * 100:.1f}%" if r is not None else "--"

    def condition_hit_rate(self, condition_id: str) -> Optional[float]:
        if self.total_runs == 0:
            return None
        return self.condition_hits.get(condition_id, 0) / self.total_runs

    def condition_hit_rate_pct(self, condition_id: str) -> str:
        r = self.condition_hit_rate(condition_id)
        return f"{r * 100:.1f}%" if r is not None else "--"

    # ------------------------------------------------------------------
    # Mutation helpers (called by runner)
    # ------------------------------------------------------------------

    def _reset_results(self) -> None:
        self.total_runs = 0
        self.success_count = 0
        self.condition_hits = {c.id: 0 for c in self.conditions}
        self.elapsed_seconds = 0.0
        self.status = "RUNNING"

    def _record_run(self, run: RunResult) -> None:
        self.total_runs += 1
        if run.simulation_success:
            self.success_count += 1
        for cr in run.condition_results:
            if cr.satisfied:
                self.condition_hits[cr.condition_id] = (
                    self.condition_hits.get(cr.condition_id, 0) + 1
                )

    def __str__(self) -> str:
        return (
            f"[{self.id}] {self.name} ({self.success_rule.value}) "
            f"| {self.success_rate_pct} over {self.total_runs} runs"
        )


# ---------------------------------------------------------------------------
# SimulationRunner
# ---------------------------------------------------------------------------

class SimulationRunner:
    """
    Executes simulations against a GameState.

    Usage
    -----
        runner = SimulationRunner(game_state, cards_per_turn=1)
        runner.run(simulation)                      # blocking
        runner.run(simulation, progress_cb=fn)      # with callback
    """

    def __init__(
        self,
        game_state,          # GameState — imported lazily to avoid circular
        cards_per_turn: int = 1,
        seed: Optional[int] = None,
    ) -> None:
        self.game_state = game_state
        self.cards_per_turn = cards_per_turn
        self._base_seed = seed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        simulation: Simulation,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> Simulation:
        """
        Run `simulation.run_count` independent games and record results
        back onto the Simulation object.

        Parameters
        ----------
        simulation  : Simulation to execute (mutated in place).
        progress_cb : Optional callable(completed_runs, total_runs) called
                      after each run — use for progress bars in the TUI.

        Returns the same Simulation for chaining.
        """
        simulation._reset_results()
        gs = self.game_state
        t0 = time.monotonic()

        for i in range(simulation.run_count):
            # Seed deterministically if a base seed was provided
            run_seed = (self._base_seed + i) if self._base_seed is not None else None
            gs.reset(seed=run_seed)
            gs.deal_opening_hand()

            run = self._execute_run(simulation, gs)
            simulation._record_run(run)

            if progress_cb is not None:
                progress_cb(i + 1, simulation.run_count)

        simulation.elapsed_seconds = time.monotonic() - t0
        simulation.status = "COMPLETE"
        return simulation

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _execute_run(self, simulation: Simulation, gs) -> RunResult:
        """
        Simulate one game: advance turns up to turn_limit, tracking whether
        each condition was ever satisfied at or before its deadline.
        """
        turn_limit = simulation.effective_turn_limit
        conditions = simulation.conditions

        # Track per-condition satisfaction (latches True once hit)
        satisfied: dict[str, bool] = {c.id: False for c in conditions}

        # Evaluate at turn 0 (opening hand)
        self._evaluate_all(conditions, satisfied, gs)

        for _ in range(turn_limit):
            gs.advance_turn(self.cards_per_turn)
            self._evaluate_all(conditions, satisfied, gs)

        # Build condition results
        condition_results = [
            ConditionResult(c.id, satisfied[c.id]) for c in conditions
        ]

        # Determine overall success
        flags = [satisfied[c.id] for c in conditions]
        if simulation.success_rule == SuccessRule.ANY:
            sim_success = any(flags) if flags else False
        else:  # ALL
            sim_success = all(flags) if flags else False

        return RunResult(condition_results=condition_results, simulation_success=sim_success)

    @staticmethod
    def _evaluate_all(
        conditions: list[Condition],
        satisfied: dict[str, bool],
        gs,
    ) -> None:
        """Evaluate all conditions, latching any that become True."""
        hand = gs.hand_counts
        turn = gs.turn
        for c in conditions:
            if not satisfied[c.id]:
                if c.evaluate(hand, turn):
                    satisfied[c.id] = True