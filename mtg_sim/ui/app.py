"""
mtg_sim/ui/app.py — Main Textual application.

Stage 2: 4-pane layout, keyboard navigation, static data display.
Stage 3 will wire interactive turn/reset actions.
Stage 4 will complete CRUD modals.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Label, Static

from ..engine.app_state import AppState
from ..engine.config import Config
from ..engine.deck import Deck
from ..engine.simulation import (
    Comparator, Condition, Simulation, SuccessRule, SimulationRunner,
)
from .widgets import ConditionsPane, HandPane, LibraryPane, SimulationsPane
from .modals import ConditionModal, SimulationModal


# ---------------------------------------------------------------------------
# MtgSimApp
# ---------------------------------------------------------------------------

def _css_path() -> Path:
    """
    Resolve app.tcss at runtime, handling both normal execution and
    PyInstaller bundles where __file__ points inside a temp directory.
    """
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        return base / "mtg_sim" / "ui" / "app.tcss"
    return Path(__file__).parent / "app.tcss"


class MtgSimApp(App):
    """MTG Draw Simulator — terminal UI."""

    CSS_PATH = _css_path()

    BINDINGS = [
        # Navigation
        Binding("tab",       "focus_next_pane",  "next pane",   show=False),
        Binding("shift+tab", "focus_prev_pane",  "prev pane",   show=False),
        Binding("up",        "select_prev",      "prev item",   show=False),
        Binding("down",      "select_next",      "next item",   show=False),
        # Game actions
        Binding("n", "next_turn",   "next turn"),
        Binding("r", "reset_game",  "reset"),
        Binding("s", "run_sims",    "run sims"),
        # CRUD
        Binding("a", "add_condition",   "add condition"),
        Binding("A", "add_simulation",  "add simulation"),
        Binding("d", "delete_selected", "delete"),
        # App
        Binding("q", "quit", "quit"),
    ]

    # Pane focus order
    PANE_IDS = ["pane-library", "pane-hand", "pane-conditions", "pane-simulations"]

    def __init__(self, state: AppState, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state = state
        self._pane_index = 0   # which pane has focus

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        state = self._state

        # Title bar
        deck_label = state.deck.source if state.deck else "no deck"
        yield Static(
            f" mtg_sim  [dim]│[/dim]  {deck_label}",
            id="title-bar",
        )

        # 2×2 grid
        lib_pane  = LibraryPane(state,  id="pane-library",     classes="pane")
        hand_pane = HandPane(state,     id="pane-hand",        classes="pane")
        cond_pane = ConditionsPane(state, id="pane-conditions", classes="pane")
        sim_pane  = SimulationsPane(state, id="pane-simulations", classes="pane")

        from textual.containers import Grid
        with Grid(id="main-grid"):
            yield lib_pane
            yield hand_pane
            yield cond_pane
            yield sim_pane

        # Status bar with key hints
        yield Static(self._build_status(), id="status-bar")

    def _build_status(self) -> str:
        hints = [
            ("[n]", "next turn"),
            ("[r]", "reset"),
            ("[s]", "run sims"),
            ("[a]", "add cond"),
            ("[A]", "add sim"),
            ("[d]", "delete"),
            ("[tab]", "focus"),
            ("[q]", "quit"),
        ]
        parts = [f"[dim]{key}[/dim] {desc}" for key, desc in hints]
        return "  ".join(parts)

    def on_mount(self) -> None:
        # Focus the library pane initially
        self._focus_pane(0)

    # ------------------------------------------------------------------
    # Pane navigation
    # ------------------------------------------------------------------

    def _focus_pane(self, index: int) -> None:
        self._pane_index = index % len(self.PANE_IDS)
        pane_id = self.PANE_IDS[self._pane_index]
        pane = self.query_one(f"#{pane_id}")
        pane.focus()

    def action_focus_next_pane(self) -> None:
        self._focus_pane(self._pane_index + 1)

    def action_focus_prev_pane(self) -> None:
        self._focus_pane(self._pane_index - 1)

    def action_select_next(self) -> None:
        pane_id = self.PANE_IDS[self._pane_index]
        if pane_id == "pane-conditions":
            self.query_one("#pane-conditions", ConditionsPane).select_next()
        elif pane_id == "pane-simulations":
            self.query_one("#pane-simulations", SimulationsPane).select_next()

    def action_select_prev(self) -> None:
        pane_id = self.PANE_IDS[self._pane_index]
        if pane_id == "pane-conditions":
            self.query_one("#pane-conditions", ConditionsPane).select_prev()
        elif pane_id == "pane-simulations":
            self.query_one("#pane-simulations", SimulationsPane).select_prev()

    # ------------------------------------------------------------------
    # Game actions
    # ------------------------------------------------------------------

    def action_next_turn(self) -> None:
        if self._state.game_state is None:
            self.notify("Load a deck first.", severity="warning")
            return
        self._state.advance_turn()
        self._refresh_game_panes()

    def action_reset_game(self) -> None:
        if self._state.game_state is None:
            self.notify("Load a deck first.", severity="warning")
            return
        self._state.reset_game()
        self._refresh_game_panes()
        self.notify("Game reset.")

    def action_run_sims(self) -> None:
        if self._state.game_state is None:
            self.notify("Load a deck first.", severity="warning")
            return
        if not self._state.simulations:
            self.notify("No simulations defined.", severity="warning")
            return

        count = len(self._state.simulations)
        self.notify(f"Running {count} simulation(s)…")

        # Run synchronously for now (Stage 5 will add async progress)
        self._state.run_all_simulations()
        self._refresh_all_panes()
        self.notify("Simulations complete.", severity="information")

    # ------------------------------------------------------------------
    # CRUD actions
    # ------------------------------------------------------------------

    def action_add_condition(self) -> None:
        card_names = list(self._state.deck.counts.keys()) if self._state.deck else []

        def on_result(cond: Condition | None) -> None:
            if cond is None:
                return
            self._state.add_condition(cond)
            self._refresh_conditions()
            self.notify(f"Condition added: {cond.display_label}")

        self.push_screen(ConditionModal(card_names=card_names), on_result)

    def action_add_simulation(self) -> None:
        def on_result(sim: Simulation | None) -> None:
            if sim is None:
                return
            self._state.add_simulation(sim)
            self._refresh_simulations()
            self.notify(f"Simulation added: {sim.name}")

        self.push_screen(SimulationModal(), on_result)

    def action_delete_selected(self) -> None:
        pane_id = self.PANE_IDS[self._pane_index]

        if pane_id == "pane-conditions":
            pane = self.query_one("#pane-conditions", ConditionsPane)
            cond = pane.selected_condition
            if cond is None:
                self.notify("Select a condition first (↑↓).", severity="warning")
                return
            self._state.remove_condition(cond.id)
            pane.selected_index = -1
            self._refresh_conditions()
            self._refresh_simulations()
            self.notify(f"Deleted condition: {cond.display_label}")

        elif pane_id == "pane-simulations":
            pane = self.query_one("#pane-simulations", SimulationsPane)
            sim = pane.selected_simulation
            if sim is None:
                self.notify("Select a simulation first (↑↓).", severity="warning")
                return
            self._state.remove_simulation(sim.id)
            pane.selected_index = -1
            self._refresh_simulations()
            self.notify(f"Deleted simulation: {sim.name}")

        else:
            self.notify("Focus conditions or simulations pane to delete.", severity="warning")

    # ------------------------------------------------------------------
    # Refresh helpers
    # ------------------------------------------------------------------

    def _refresh_game_panes(self) -> None:
        self.query_one("#pane-library", LibraryPane).refresh_library()
        self.query_one("#pane-hand", HandPane).refresh_hand()

    def _refresh_conditions(self) -> None:
        self.query_one("#pane-conditions", ConditionsPane).refresh_conditions()

    def _refresh_simulations(self) -> None:
        self.query_one("#pane-simulations", SimulationsPane).refresh_simulations()

    def _refresh_all_panes(self) -> None:
        self._refresh_game_panes()
        self._refresh_conditions()
        self._refresh_simulations()


# ---------------------------------------------------------------------------
# Entry point helpers
# ---------------------------------------------------------------------------

def build_demo_state() -> AppState:
    """Populate a demo AppState so Stage 2 has something to show."""
    from ..engine.simulation import Comparator, Condition, Simulation, SuccessRule

    demo_deck = """
Deck
4 Lightning Bolt
4 Goblin Guide
4 Monastery Swiftspear
4 Eidolon of the Great Revel
4 Searing Blaze
4 Shard Volley
4 Inspiring Vantage
12 Mountain
4 Sacred Foundry
"""
    state = AppState()
    deck = Deck.from_text(demo_deck, source="burn.txt (demo)")
    state.load_deck(deck)

    c1 = Condition("Goblin Guide",   Comparator.GT,  0, 1, label="Turn 1 guide")
    c2 = Condition("Lightning Bolt", Comparator.GT,  0, 1, label="Turn 1 bolt")
    c3 = Condition("Mountain",       Comparator.GTE, 2, 3, label="Double land")
    state.add_condition(c1)
    state.add_condition(c2)
    state.add_condition(c3)

    s1 = Simulation("Aggro opener", conditions=[c1, c2],
                    success_rule=SuccessRule.ANY, run_count=10_000)
    s2 = Simulation("Full setup",  conditions=[c1, c3],
                    success_rule=SuccessRule.ALL, run_count=10_000)
    state.add_simulation(s1)
    state.add_simulation(s2)

    return state


def run(state: AppState | None = None) -> None:
    """Launch the TUI."""
    if state is None:
        state = build_demo_state()
    MtgSimApp(state).run()