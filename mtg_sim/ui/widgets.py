"""
mtg_sim/ui/widgets.py — Reusable TUI widgets for each pane.

Each pane contains a single Static widget whose text content is replaced
via .update() on every refresh. This is fully synchronous — no mount/remove
races possible.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static
from textual.containers import ScrollableContainer
from textual.reactive import reactive

from ..engine.app_state import AppState
from ..engine.deck import Card
from ..engine.simulation import Condition, Simulation, SuccessRule

FLASH_DURATION = 0.6


# ---------------------------------------------------------------------------
# LibraryPane
# ---------------------------------------------------------------------------

class LibraryPane(Widget):
    can_focus = True

    def __init__(self, state: AppState, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state = state

    def compose(self) -> ComposeResult:
        yield Label("LIBRARY", classes="pane-title", id="lib-title")
        yield ScrollableContainer(
            Static("", id="lib-content"),
            classes="pane-scroll",
            can_focus=False,
        )

    def on_mount(self) -> None:
        self.refresh_library()

    def refresh_library(self, highlight_names: list[str] | None = None) -> None:
        gs = self._state.game_state
        content = self.query_one("#lib-content", Static)

        if gs is None:
            content.update("No deck loaded.")
            return

        deck_counts   = self._state.deck.counts if self._state.deck else {}
        lib_counts    = gs.library_counts
        highlight_set = set(highlight_names or [])

        lines = []
        for name in sorted(deck_counts.keys()):
            lib_qty  = lib_counts.get(name, 0)
            deck_qty = deck_counts[name]
            drawn    = deck_qty - lib_qty
            qty_str  = f"x{lib_qty}"

            if lib_qty == 0:
                # dim — all copies drawn
                lines.append(f"[dim]{name:<38} {qty_str}[/dim]")
            elif name in highlight_set:
                # blue — just drawn this turn
                lines.append(f"[bold cyan]{name:<38} {qty_str}[/bold cyan]")
            elif drawn > 0:
                # grey — partially drawn
                lines.append(f"[#888888]{name:<38} {qty_str}[/#888888]")
            else:
                lines.append(f"{name:<38} {qty_str}")

        total_deck = sum(deck_counts.values())
        lines.append(f"[dim]{'─' * 44}[/dim]")
        lines.append(f"[yellow]TOTAL  {total_deck} → {gs.library_size}[/yellow]")

        content.update("\n".join(lines))
        self.query_one("#lib-title", Label).update(
            f"LIBRARY  [dim]turn {gs.turn}[/dim]"
        )

        if highlight_names:
            self.set_timer(FLASH_DURATION, lambda: self.refresh_library())


# ---------------------------------------------------------------------------
# HandPane
# ---------------------------------------------------------------------------

class HandPane(Widget):
    can_focus = True

    def __init__(self, state: AppState, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state = state
        self._flash_names: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Label("HAND", classes="pane-title", id="hand-title")
        yield ScrollableContainer(
            Static("", id="hand-content"),
            classes="pane-scroll",
            can_focus=False,
        )

    def on_mount(self) -> None:
        self.refresh_hand()

    def refresh_hand(self, newly_drawn: list[Card] | None = None) -> None:
        gs = self._state.game_state
        content = self.query_one("#hand-content", Static)

        if gs is None:
            content.update("No deck loaded.")
            return

        hand        = gs.hand_counts
        drawn_names = set(c.name for c in (newly_drawn or []))
        self._flash_names = drawn_names

        if not hand:
            content.update("[dim]Hand is empty.[/dim]")
        else:
            lines = []
            for name, qty in sorted(hand.items()):
                display = name if qty == 1 else f"{name} ×{qty}"
                if name in drawn_names:
                    lines.append(f"[bold white]{display}[/bold white]")
                else:
                    lines.append(f"[#9d7dea]{display}[/#9d7dea]")
            content.update("\n".join(lines))

        self.query_one("#hand-title", Label).update(
            f"HAND  [dim]{gs.hand_size_current} cards[/dim]"
        )

        if drawn_names:
            self.set_timer(FLASH_DURATION, self._clear_flash)

    def _clear_flash(self) -> None:
        self._flash_names = set()
        self.refresh_hand()


# ---------------------------------------------------------------------------
# ConditionsPane
# ---------------------------------------------------------------------------

class ConditionsPane(Widget):
    can_focus = True
    selected_index: reactive[int] = reactive(-1)

    def __init__(self, state: AppState, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state = state

    def compose(self) -> ComposeResult:
        yield Label("CONDITIONS", classes="pane-title", id="cond-title")
        yield ScrollableContainer(
            Static("", id="cond-content"),
            classes="pane-scroll",
        )

    def on_mount(self) -> None:
        self.refresh_conditions()

    def refresh_conditions(self) -> None:
        conditions = self._state.conditions
        content    = self.query_one("#cond-content", Static)

        if not conditions:
            content.update("No conditions defined.\n[dim]Press [/dim][cyan]a[/cyan][dim] to add one.[/dim]")
            self.query_one("#cond-title", Label).update("CONDITIONS  [dim]0 defined[/dim]")
            return

        lines = []
        for i, cond in enumerate(conditions):
            selected = (i == self.selected_index)
            cid      = f"[C{i+1}]"
            # display_label returns the custom label if set,
            # otherwise auto-generates from the rule itself
            main = f"{cid:<6}{cond.display_label}"
            # If a custom label exists, show the full rule as a subtitle
            if cond.label:
                rule_line = f"{"":6}{cond.card_name} {cond.comparator} {cond.count} by turn {cond.turn_deadline}"
                text = main + "\n" + rule_line
            else:
                text = main

            if selected:
                lines.append(f"[bold white]{text}[/bold white]")
            else:
                lines.append(text)

        content.update("\n".join(lines))
        self.query_one("#cond-title", Label).update(
            f"CONDITIONS  [dim]{len(conditions)} defined[/dim]"
        )

    def watch_selected_index(self, old: int, new: int) -> None:
        if old == new:
            return
        self.refresh_conditions()

    def select_next(self) -> None:
        n = len(self._state.conditions)
        if n == 0:
            return
        self.selected_index = (self.selected_index + 1) % n

    def select_prev(self) -> None:
        n = len(self._state.conditions)
        if n == 0:
            return
        self.selected_index = (self.selected_index - 1) % n

    @property
    def selected_condition(self) -> Condition | None:
        conditions = self._state.conditions
        if 0 <= self.selected_index < len(conditions):
            return conditions[self.selected_index]
        return None


# ---------------------------------------------------------------------------
# SimulationsPane
# ---------------------------------------------------------------------------

class SimulationsPane(Widget):
    can_focus = True
    selected_index: reactive[int] = reactive(-1)

    def __init__(self, state: AppState, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state = state

    def compose(self) -> ComposeResult:
        yield Label("SIMULATIONS", classes="pane-title", id="sim-title")
        yield ScrollableContainer(
            Static("", id="sim-content"),
            classes="pane-scroll",
        )

    def on_mount(self) -> None:
        self.refresh_simulations()

    def refresh_simulations(self) -> None:
        simulations = self._state.simulations
        content     = self.query_one("#sim-content", Static)

        if not simulations:
            content.update("No simulations defined.\n[dim]Press [/dim][cyan]A[/cyan][dim] to add one.[/dim]")
            self.query_one("#sim-title", Label).update("SIMULATIONS  [dim]0 defined[/dim]")
            return

        lines = []
        for i, sim in enumerate(simulations):
            selected = (i == self.selected_index)
            sid      = f"[S{i+1}]"
            rule     = "ANY" if sim.success_rule == SuccessRule.ANY else "ALL"
            # Default sim name: generate from conditions and rule if blank
            if sim.name:
                sim_name = sim.name
            else:
                cond_list = ", ".join(
                    f"C{idx+1}" for idx in sim.condition_indices
                    if 0 <= idx < len(self._state.conditions)
                ) or "no conditions"
                sim_name = f"{rule} of {cond_list}"

            cond_ids = [
                f"[C{i+1}]" if 0 <= i < len(self._state.conditions) else "[C?]"
                for i in sim.condition_indices
            ]
            uses_str = " ".join(cond_ids) if cond_ids else "none"
            turn_lim = sim.effective_turn_limit(self._state.conditions)

            header = f"{sid:<6}{sim_name:<28}{rule:<5}{sim.status:>9}"
            meta   = f"{'':6}runs: {sim.run_count:,}  turns: {turn_lim}  rate: {sim.success_rate_pct}"
            uses   = f"{'':6}uses: {uses_str}"
            block  = header + "\n" + meta + "\n" + uses

            if selected:
                lines.append(f"[bold white]{block}[/bold white]")
            else:
                lines.append(block)

            if i < len(simulations) - 1:
                lines.append("[dim]" + "─" * 50 + "[/dim]")

        content.update("\n".join(lines))
        self.query_one("#sim-title", Label).update(
            f"SIMULATIONS  [dim]{len(simulations)} defined[/dim]"
        )

    def watch_selected_index(self, old: int, new: int) -> None:
        if old == new:
            return
        self.refresh_simulations()

    def select_next(self) -> None:
        n = len(self._state.simulations)
        if n == 0:
            return
        self.selected_index = (self.selected_index + 1) % n

    def select_prev(self) -> None:
        n = len(self._state.simulations)
        if n == 0:
            return
        self.selected_index = (self.selected_index - 1) % n

    @property
    def selected_simulation(self) -> Simulation | None:
        sims = self._state.simulations
        if 0 <= self.selected_index < len(sims):
            return sims[self.selected_index]
        return None