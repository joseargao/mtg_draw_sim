"""
mtg_sim/ui/app.py — Main Textual application.
"""

from __future__ import annotations

import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid
from textual.widgets import Static

from ..engine.app_state import AppState
from ..engine.deck import Deck
from ..engine.simulation import Comparator, Condition, Simulation, SuccessRule
from .widgets import ConditionsPane, HandPane, LibraryPane, SimulationsPane
from .modals import ConditionModal, SimulationModal, HelpModal


def _css_path() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        return base / "mtg_sim" / "ui" / "app.tcss"
    return Path(__file__).parent / "app.tcss"


class MtgSimApp(App):
    CSS_PATH = _css_path()

    BINDINGS = [
        Binding("tab",       "focus_next_pane", "next pane",  show=False, priority=True),
        Binding("shift+tab", "focus_prev_pane", "prev pane",  show=False, priority=True),
        Binding("up",        "select_prev",     "prev item",  show=False),
        Binding("down",      "select_next",     "next item",  show=False),
        Binding("enter",     "edit_selected",   "edit",       show=False),
        Binding("n", "next_turn",   "next turn"),
        Binding("r", "reset_game",  "reset"),
        Binding("s", "run_sims",    "run sims"),
        Binding("a", "add_condition",   "add condition"),
        Binding("A", "add_simulation",  "add simulation"),
        Binding("d", "delete_selected", "delete"),
        Binding("q", "quit", "quit"),
        Binding("f1", "show_help", "help"),
    ]

    PANE_IDS = ["pane-library", "pane-hand", "pane-conditions", "pane-simulations"]

    def __init__(self, state: AppState, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state = state
        self._pane_index = 0

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        deck_label = self._state.deck.source if self._state.deck else "no deck"
        yield Static(
            f"[bold cyan]Draw Simulator[/bold cyan]  [dim]│[/dim]  {deck_label}",
            id="title-bar"
        )
        with Grid(id="main-grid"):
            yield LibraryPane(self._state,  id="pane-library",      classes="pane")
            yield HandPane(self._state,     id="pane-hand",         classes="pane")
            yield ConditionsPane(self._state, id="pane-conditions", classes="pane")
            yield SimulationsPane(self._state, id="pane-simulations", classes="pane")
        yield Static(self._build_status(), id="status-bar")

    def _build_status(self) -> str:
        hints = [
            ("tab", "switch pane"), ("↑↓", "select item"), ("enter", "edit"),
            ("r", "deal hand"), ("n", "next turn"), ("s", "run sims"),
            ("q", "quit"), ("F1", "help"),
        ]
        return "  ".join(f"[cyan]{k}[/cyan] [dim]{v}[/dim]" for k, v in hints)

    def on_mount(self) -> None:
        self._focus_pane(0)

    # ------------------------------------------------------------------
    # Pane focus
    # ------------------------------------------------------------------

    def _focus_pane(self, index: int) -> None:
        self._pane_index = index % len(self.PANE_IDS)
        self.query_one(f"#{self.PANE_IDS[self._pane_index]}").focus()

    def action_focus_next_pane(self) -> None:
        self._focus_pane(self._pane_index + 1)

    def action_focus_prev_pane(self) -> None:
        self._focus_pane(self._pane_index - 1)

    def on_focus(self, event) -> None:
        if event.widget.id in self.PANE_IDS:
            self._pane_index = self.PANE_IDS.index(event.widget.id)

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
        drawn = self._state.advance_turn()
        self._refresh_game_panes(newly_drawn=drawn)

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
        self.notify(f"Running {len(self._state.simulations)} simulation(s)…")
        self._state.run_all_simulations()
        self._refresh_all_panes()
        self.notify("Simulations complete.", severity="information")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def action_show_help(self) -> None:
        self.push_screen(HelpModal())

    def action_add_condition(self) -> None:
        card_names = sorted(self._state.deck.counts.keys()) if self._state.deck else []

        def on_result(cond: Condition | None) -> None:
            if cond is None:
                return
            self._state.add_condition(cond)
            self._refresh_conditions()

        self.push_screen(ConditionModal(card_names=card_names), on_result)

    def action_add_simulation(self) -> None:
        def on_result(result) -> None:
            if result is None:
                return
            sim, indices = result
            sim.condition_indices = indices
            self._state.add_simulation(sim)
            self._refresh_simulations()

        self.push_screen(
            SimulationModal(conditions=self._state.conditions),
            on_result,
        )

    def action_edit_selected(self) -> None:
        pane_id = self.PANE_IDS[self._pane_index]

        if pane_id == "pane-conditions":
            pane = self.query_one("#pane-conditions", ConditionsPane)
            idx = pane.selected_index
            if idx < 0:
                self.notify("Select a condition first (↑↓).", severity="warning")
                return
            existing = self._state.conditions[idx]
            card_names = sorted(self._state.deck.counts.keys()) if self._state.deck else []

            def on_result(updated: Condition | None) -> None:
                if updated is None:
                    return
                self._state.replace_condition(idx, updated)
                self._refresh_conditions()
                self._refresh_simulations()

            self.push_screen(ConditionModal(card_names=card_names, existing=existing), on_result)

        elif pane_id == "pane-simulations":
            pane = self.query_one("#pane-simulations", SimulationsPane)
            idx = pane.selected_index
            if idx < 0:
                self.notify("Select a simulation first (↑↓).", severity="warning")
                return
            existing = self._state.simulations[idx]

            def on_result(result) -> None:
                if result is None:
                    return
                sim, indices = result
                sim.condition_indices = indices
                self._state.replace_simulation(idx, sim)
                self._refresh_simulations()

            self.push_screen(
                SimulationModal(conditions=self._state.conditions, existing=existing),
                on_result,
            )

    def action_delete_selected(self) -> None:
        pane_id = self.PANE_IDS[self._pane_index]

        if pane_id == "pane-conditions":
            pane = self.query_one("#pane-conditions", ConditionsPane)
            idx = pane.selected_index
            if idx < 0:
                self.notify("Select a condition first (↑↓).", severity="warning")
                return
            name = self._state.conditions[idx].display_label
            self._state.remove_condition(idx)
            pane.selected_index = -1
            self._refresh_conditions()
            self._refresh_simulations()
            self.notify(f"Deleted: {name}")

        elif pane_id == "pane-simulations":
            pane = self.query_one("#pane-simulations", SimulationsPane)
            idx = pane.selected_index
            if idx < 0:
                self.notify("Select a simulation first (↑↓).", severity="warning")
                return
            name = self._state.simulations[idx].name
            self._state.remove_simulation(idx)
            pane.selected_index = -1
            self._refresh_simulations()
            self.notify(f"Deleted: {name}")

        else:
            self.notify("Focus conditions or simulations pane to delete.", severity="warning")

    # ------------------------------------------------------------------
    # Refresh helpers
    # ------------------------------------------------------------------

    def _refresh_game_panes(self, newly_drawn=None) -> None:
        drawn_names = [c.name for c in (newly_drawn or [])]
        self.query_one("#pane-library", LibraryPane).refresh_library(
            highlight_names=drawn_names if drawn_names else None
        )
        self.query_one("#pane-hand", HandPane).refresh_hand(
            newly_drawn=newly_drawn or []
        )

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

    s1 = Simulation(label="Aggro opener", condition_indices=[0, 1],
                    success_rule=SuccessRule.ANY, run_count=10_000)
    s2 = Simulation(label="Full setup",  condition_indices=[0, 2],
                    success_rule=SuccessRule.ALL, run_count=10_000)
    state.add_simulation(s1)
    state.add_simulation(s2)

    return state


def run(state: AppState | None = None) -> None:
    if state is None:
        state = build_demo_state()
    MtgSimApp(state).run()