"""
mtg_sim/ui/widgets.py — Reusable TUI widgets for each pane.

Each widget is self-contained and refreshes by calling its own
`refresh_*()` method.  The app calls these whenever state changes.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static
from textual.containers import ScrollableContainer
from textual.reactive import reactive

from ..engine.app_state import AppState
from ..engine.simulation import Condition, Simulation, SuccessRule


# ---------------------------------------------------------------------------
# LibraryPane
# ---------------------------------------------------------------------------

class LibraryPane(Widget):
    """Shows remaining cards in library and current turn."""

    DEFAULT_CSS = ""
    can_focus = True

    def __init__(self, state: AppState, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state = state

    def compose(self) -> ComposeResult:
        yield Label("LIBRARY", classes="pane-title")
        yield ScrollableContainer(id="lib-scroll", classes="pane-scroll")

    def on_mount(self) -> None:
        self.refresh_library()

    def refresh_library(self) -> None:
        scroll = self.query_one("#lib-scroll", ScrollableContainer)
        scroll.remove_children()

        gs = self._state.game_state
        if gs is None:
            scroll.mount(Label("No deck loaded.", classes="lib-name"))
            return

        deck_counts = self._state.deck.counts if self._state.deck else {}
        lib_counts = gs.library_counts

        for name in sorted(deck_counts.keys()):
            lib_qty = lib_counts.get(name, 0)
            deck_qty = deck_counts[name]
            changed = lib_qty < deck_qty

            row = Widget(classes="lib-row")
            name_label = Label(name, classes="lib-name")
            count_label = Label(
                f"x{lib_qty}",
                classes=f"lib-count {'changed' if changed else ''}",
            )
            row.compose = lambda n=name_label, c=count_label: iter([n, c])  # type: ignore
            scroll.mount(name_label)

        # Rebuild as proper rows
        scroll.remove_children()
        for name in sorted(deck_counts.keys()):
            lib_qty = lib_counts.get(name, 0)
            deck_qty = deck_counts[name]
            changed = lib_qty < deck_qty
            row = Static(
                f"{name:<38} {'x' + str(lib_qty):>4}",
                classes="lib-name" + (" changed" if changed else ""),
            )
            scroll.mount(row)

        # Total line
        total_deck = sum(deck_counts.values())
        total_lib = gs.library_size
        scroll.mount(
            Static(
                f"{'─' * 42}\n"
                f"{'TOTAL':<38} {total_deck} → {total_lib:>2}",
                classes="lib-total total-count",
            )
        )

        # Update title meta
        turn = gs.turn
        try:
            title = self.query_one(".pane-title", Label)
            title.update(f"LIBRARY  [dim]turn {turn}[/dim]")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# HandPane
# ---------------------------------------------------------------------------

class HandPane(Widget):
    """Shows cards currently in hand."""

    can_focus = True

    def __init__(self, state: AppState, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state = state

    def compose(self) -> ComposeResult:
        yield Label("HAND", classes="pane-title")
        yield ScrollableContainer(id="hand-scroll", classes="pane-scroll")

    def on_mount(self) -> None:
        self.refresh_hand()

    def refresh_hand(self) -> None:
        scroll = self.query_one("#hand-scroll", ScrollableContainer)
        scroll.remove_children()

        gs = self._state.game_state
        if gs is None:
            scroll.mount(Label("No deck loaded.", classes="hand-empty"))
            return

        hand = gs.hand_counts
        if not hand:
            scroll.mount(Label("Hand is empty.", classes="hand-empty"))
        else:
            for name, qty in sorted(hand.items()):
                display = name if qty == 1 else f"{name} ×{qty}"
                scroll.mount(Static(display, classes="hand-card"))

        # Update title
        try:
            title = self.query_one(".pane-title", Label)
            title.update(f"HAND  [dim]{gs.hand_size_current} cards[/dim]")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# ConditionsPane
# ---------------------------------------------------------------------------

class ConditionsPane(Widget):
    """Shows all defined conditions with selection highlight."""

    can_focus = True
    selected_index: reactive[int] = reactive(-1)

    def __init__(self, state: AppState, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state = state

    def compose(self) -> ComposeResult:
        yield Label("CONDITIONS", classes="pane-title")
        yield ScrollableContainer(id="cond-scroll", classes="pane-scroll")

    def on_mount(self) -> None:
        self.refresh_conditions()

    def refresh_conditions(self) -> None:
        scroll = self.query_one("#cond-scroll", ScrollableContainer)
        scroll.remove_children()

        conditions = self._state.conditions
        if not conditions:
            scroll.mount(Static(
                "No conditions defined.\nPress [a] to add one.",
                classes="cond-empty",
            ))
        else:
            for i, cond in enumerate(conditions):
                selected = (i == self.selected_index)
                sel_cls = " cond-selected" if selected else ""
                cid = f"[C{i+1}]"
                rule = f"by turn {cond.turn_deadline}"
                expr = f"{cond.card_name} {cond.comparator} {cond.count}"
                label_text = cond.label or ""

                # Compose as a single static block per condition
                if label_text:
                    line1 = f"{cid:<6}{label_text}"
                    line2 = f"{'':6}{expr:<34}{rule:>14}"
                else:
                    line1 = f"{cid:<6}{expr:<34}{rule:>14}"
                    line2 = ""

                text = line1 + ("\n" + line2 if line2 else "")
                scroll.mount(Static(text, classes=f"cond-item{sel_cls}", id=f"cond-{i}"))

        # Update title
        count = len(conditions)
        try:
            title = self.query_one(".pane-title", Label)
            title.update(f"CONDITIONS  [dim]{count} defined[/dim]")
        except Exception:
            pass

    def watch_selected_index(self, _old: int, _new: int) -> None:
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
    """Shows all simulations with stats."""

    can_focus = True
    selected_index: reactive[int] = reactive(-1)

    def __init__(self, state: AppState, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state = state

    def compose(self) -> ComposeResult:
        yield Label("SIMULATIONS", classes="pane-title")
        yield ScrollableContainer(id="sim-scroll", classes="pane-scroll")

    def on_mount(self) -> None:
        self.refresh_simulations()

    def refresh_simulations(self) -> None:
        scroll = self.query_one("#sim-scroll", ScrollableContainer)
        scroll.remove_children()

        simulations = self._state.simulations
        if not simulations:
            scroll.mount(Static(
                "No simulations defined.\nPress [S] to add one.",
                classes="sim-empty",
            ))
        else:
            for i, sim in enumerate(simulations):
                selected = (i == self.selected_index)
                sel_cls = " sim-selected" if selected else ""

                sid = f"[S{i+1}]"
                rule = "ANY" if sim.success_rule == SuccessRule.ANY else "ALL"
                status = sim.status
                rate = sim.success_rate_pct

                # Condition references
                cond_ids = []
                for cond in sim.conditions:
                    try:
                        idx = next(
                            j for j, c in enumerate(self._state.conditions)
                            if c.id == cond.id
                        )
                        cond_ids.append(f"[C{idx+1}]")
                    except StopIteration:
                        cond_ids.append("[C?]")
                uses_str = " ".join(cond_ids) if cond_ids else "none"

                header = f"{sid:<6}{sim.name:<28}{rule:<5}{status:>9}"
                meta   = f"{'':6}runs: {sim.run_count:,}  turns: {sim.effective_turn_limit}  rate: {rate}"
                uses   = f"{'':6}uses: {uses_str}"

                block = header + "\n" + meta + "\n" + uses
                scroll.mount(Static(block, classes=f"sim-item{sel_cls}", id=f"sim-{i}"))
                if i < len(simulations) - 1:
                    scroll.mount(Static("─" * 50, classes="sim-divider"))

        # Update title
        count = len(simulations)
        try:
            title = self.query_one(".pane-title", Label)
            title.update(f"SIMULATIONS  [dim]{count} defined[/dim]")
        except Exception:
            pass

    def watch_selected_index(self, _old: int, _new: int) -> None:
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