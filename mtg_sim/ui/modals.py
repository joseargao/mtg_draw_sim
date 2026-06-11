"""
mtg_sim/ui/modals.py — Modal dialogs for condition and simulation CRUD,
plus the F1 help overlay.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Checkbox, Input, Label, Select, Static
from textual.containers import Horizontal, Vertical, ScrollableContainer

from ..engine.simulation import Comparator, Condition, SuccessRule, Simulation


# ---------------------------------------------------------------------------
# HelpModal — F1 key binding reference
# ---------------------------------------------------------------------------

class HelpModal(ModalScreen[None]):
    """Full keybinding reference. Dismiss with any key or click."""

    BINDINGS = [
        ("escape", "dismiss_help", "Close"),
        ("f1",     "dismiss_help", "Close"),
        ("q",      "dismiss_help", "Close"),
        ("space",  "dismiss_help", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container help-container"):
            yield Static("Keybindings", classes="modal-title")
            yield Static(HELP_TEXT, classes="help-body")
            yield Static(
                "[dim]Press [/dim][cyan]Esc[/cyan][dim], [/dim][cyan]F1[/cyan][dim],"
                " [/dim][cyan]Space[/cyan][dim], or [/dim][cyan]q[/cyan][dim] to close[/dim]",
                classes="help-footer",
            )

    def action_dismiss_help(self) -> None:
        self.dismiss(None)


HELP_TEXT = """\
[cyan]Navigation[/cyan]
  [cyan]Tab[/cyan] / [cyan]Shift+Tab[/cyan]   Switch between panes
  [cyan]↑[/cyan] / [cyan]↓[/cyan]            Select item within a pane

[cyan]Game[/cyan]
  [cyan]r[/cyan]                Deal opening hand (reset)
  [cyan]n[/cyan]                Draw next turn

[cyan]Simulations[/cyan]
  [cyan]s[/cyan]                Run all simulations

[cyan]Editing[/cyan]
  [cyan]a[/cyan]                Add condition
  [cyan]A[/cyan]                Add simulation
  [cyan]Enter[/cyan]            Edit selected condition or simulation
  [cyan]d[/cyan]                Delete selected condition or simulation

[cyan]App[/cyan]
  [cyan]F1[/cyan] / [cyan]Esc[/cyan]         Close this help
  [cyan]q[/cyan]                Quit\
"""


# ---------------------------------------------------------------------------
# ConditionModal — returns a Condition or None
# ---------------------------------------------------------------------------

class ConditionModal(ModalScreen[Condition | None]):

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(
        self,
        card_names: list[str],
        existing: Condition | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._card_names = sorted(card_names)
        self._existing = existing

    def compose(self) -> ComposeResult:
        ex = self._existing
        with Vertical(classes="modal-container"):
            yield Static("Edit condition" if ex else "Add condition", classes="modal-title")

            yield Label("Card name", classes="modal-label")
            yield Select(
                options=[(name, name) for name in self._card_names],
                value=ex.card_name if ex else Select.NULL,
                prompt="Select a card…",
                type_to_search=True,
                id="select-card",
                classes="modal-select",
            )

            yield Label("Comparator", classes="modal-label")
            yield Select(
                options=[(c.value, c) for c in Comparator],
                value=ex.comparator if ex else Comparator.GTE,
                id="select-comparator",
                classes="modal-select",
            )

            yield Label("Count", classes="modal-label")
            yield Input(
                value=str(ex.count) if ex else "1",
                placeholder="e.g. 1",
                id="input-count",
            )

            yield Label("Turn deadline", classes="modal-label")
            yield Input(
                value=str(ex.turn_deadline) if ex else "4",
                placeholder="e.g. 4",
                id="input-turn",
            )

            yield Label("Label (optional)", classes="modal-label")
            yield Input(
                value=ex.label if ex else "",
                placeholder="e.g. Early bolt",
                id="input-label",
            )

            yield Static("", id="modal-error", classes="modal-error")

            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel")
                yield Button("Save", id="btn-save", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-save":
            self._save()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _show_error(self, msg: str) -> None:
        self.query_one("#modal-error", Static).update(f"[red]{msg}[/red]")

    def _save(self) -> None:
        card = self.query_one("#select-card", Select).value
        if card is Select.NULL:
            self._show_error("Please select a card.")
            return
        try:
            count = int(self.query_one("#input-count", Input).value.strip())
            turn  = int(self.query_one("#input-turn",  Input).value.strip())
        except ValueError:
            self._show_error("Count and turn must be whole numbers.")
            return
        if count < 0:
            self._show_error("Count cannot be negative.")
            return
        if turn < 0:
            self._show_error("Turn deadline cannot be negative.")
            return

        comparator = self.query_one("#select-comparator", Select).value
        if comparator is Select.NULL:
            comparator = Comparator.GTE

        label = self.query_one("#input-label", Input).value.strip()
        ex    = self._existing

        self.dismiss(Condition(
            card_name=card,
            comparator=comparator,
            count=count,
            turn_deadline=turn,
            label=label,
        ))


# ---------------------------------------------------------------------------
# SimulationModal — returns (Simulation, list[int]) or None
# ---------------------------------------------------------------------------

class SimulationModal(ModalScreen[tuple[Simulation, list[int]] | None]):

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(
        self,
        conditions: list[Condition],
        existing: Simulation | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._all_conditions = conditions
        self._existing = existing
        self._selected_indices: list[int] = (
            list(existing.condition_indices) if existing else []
        )

    def compose(self) -> ComposeResult:
        ex = self._existing
        with Vertical(classes="modal-container"):
            yield Static("Edit simulation" if ex else "Add simulation", classes="modal-title")

            yield Label("Label (optional)", classes="modal-label")
            yield Input(
                value=ex.label if ex else "",
                placeholder="auto-generated if blank",
                id="input-name",
            )

            yield Label("Success rule", classes="modal-label")
            yield Select(
                options=[
                    ("ALL — every condition must be met", SuccessRule.ALL),
                    ("ANY — at least one condition must be met", SuccessRule.ANY),
                ],
                value=ex.success_rule if ex else SuccessRule.ALL,
                id="select-rule",
            )

            yield Label("Run count", classes="modal-label")
            yield Input(
                value=str(ex.run_count) if ex else "10000",
                placeholder="e.g. 10000",
                id="input-runs",
            )

            yield Label("Turn limit (blank = auto from conditions)", classes="modal-label")
            yield Input(
                value=str(ex.turn_limit) if (ex and ex.turn_limit) else "",
                placeholder="auto",
                id="input-turns",
            )

            yield Label("Conditions", classes="modal-label")
            # Scrollable checklist — fixed height regardless of condition count
            with Vertical(classes="modal-checklist", id="checklist"):
                if not self._all_conditions:
                    yield Static(
                        "[dim]No conditions defined yet.[/dim]",
                        classes="modal-no-conditions",
                    )
                else:
                    for i, cond in enumerate(self._all_conditions):
                        checked = i in self._selected_indices
                        label = f"{i+1}. {cond.display_label}"
                        yield Checkbox(
                            label,
                            value=checked,
                            id=f"chk-{i}",
                            classes="modal-checkbox",
                            compact=True,
                        )

            yield Static("", id="modal-error", classes="modal-error")

            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel")
                yield Button("Save", id="btn-save", variant="primary")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        # Extract index from checkbox ID "chk-{i}"
        chk_id = event.checkbox.id or ""
        if not chk_id.startswith("chk-"):
            return
        idx = int(chk_id[4:])
        if event.value:
            if idx not in self._selected_indices:
                self._selected_indices.append(idx)
        else:
            if idx in self._selected_indices:
                self._selected_indices.remove(idx)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "btn-cancel":
            self.dismiss(None)
        elif bid == "btn-save":
            self._save()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _show_error(self, msg: str) -> None:
        self.query_one("#modal-error", Static).update(f"[red]{msg}[/red]")

    def _save(self) -> None:
        label = self.query_one("#input-name", Input).value.strip()

        try:
            runs = int(self.query_one("#input-runs", Input).value.strip())
        except ValueError:
            self._show_error("Run count must be a whole number.")
            return
        if runs <= 0:
            self._show_error("Run count must be greater than zero.")
            return

        turn_raw = self.query_one("#input-turns", Input).value.strip()
        turn_limit = None
        if turn_raw:
            try:
                turn_limit = int(turn_raw)
            except ValueError:
                self._show_error("Turn limit must be a whole number or blank.")
                return

        rule = self.query_one("#select-rule", Select).value
        if rule is Select.NULL:
            rule = SuccessRule.ALL

        sim = Simulation(
            label=label,
            success_rule=rule,
            run_count=runs,
            turn_limit=turn_limit,
        )
        self.dismiss((sim, sorted(self._selected_indices)))