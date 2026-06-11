"""
mtg_sim/ui/modals.py — Modal dialogs for condition and simulation CRUD.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Input, Label, Select, Static
from textual.containers import Horizontal, Vertical, ScrollableContainer

from ..engine.simulation import Comparator, Condition, SuccessRule, Simulation


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
#
# The second element of the tuple is the list of condition INDICES the user
# selected. The app stores these on sim.condition_indices.
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
        # Work with indices directly
        self._selected_indices: list[int] = (
            list(existing.condition_indices) if existing else []
        )
        self._remove_btn_map: dict[int, int] = {}  # button id() -> condition index

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
            with Horizontal(classes="modal-picker-row"):
                yield Select(
                    options=self._condition_options(),
                    prompt="Pick a condition to add…",
                    allow_blank=True,
                    id="select-condition",
                    classes="modal-picker-select",
                )
                yield Button("Add", id="btn-add-condition", classes="modal-picker-btn")

            yield ScrollableContainer(
                id="condition-list",
                classes="modal-condition-list",
            )

            yield Static("", id="modal-error", classes="modal-error")

            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel")
                yield Button("Save", id="btn-save", variant="primary")

    def on_mount(self) -> None:
        self._rebuild_condition_list()

    def _condition_label(self, idx: int) -> str:
        if 0 <= idx < len(self._all_conditions):
            c = self._all_conditions[idx]
            label = c.label or f"{c.card_name} {c.comparator} {c.count}"
            return f"[C{idx+1}] {label}  (by turn {c.turn_deadline})"
        return f"[C{idx+1}] (missing)"

    def _condition_options(self) -> list[tuple[Text, int]]:
        """Dropdown options — indices not yet selected."""
        return [
            (Text(self._condition_label(i), no_wrap=True), i)
            for i in range(len(self._all_conditions))
            if i not in self._selected_indices
        ]

    def _rebuild_condition_list(self) -> None:
        self._remove_btn_map.clear()
        container = self.query_one("#condition-list", ScrollableContainer)
        container.remove_children()
        if not self._selected_indices:
            container.mount(Static("No conditions added yet.", classes="modal-no-conditions"))
        else:
            for idx in self._selected_indices:
                label = self._condition_label(idx)
                row = Horizontal(classes="modal-condition-row")
                container.mount(row)
                lbl = Static(f" {label}", markup=False, classes="modal-condition-tag")
                btn = Button("x", classes="modal-condition-remove")
                self._remove_btn_map[id(btn)] = idx
                row.mount(lbl)
                row.mount(btn)
        # Refresh picker
        self.query_one("#select-condition", Select).set_options(self._condition_options())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "btn-cancel":
            self.dismiss(None)
        elif bid == "btn-save":
            self._save()
        elif bid == "btn-add-condition":
            self._add_condition()
        elif id(event.button) in self._remove_btn_map:
            idx = self._remove_btn_map[id(event.button)]
            if idx in self._selected_indices:
                self._selected_indices.remove(idx)
            self._rebuild_condition_list()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _add_condition(self) -> None:
        picker = self.query_one("#select-condition", Select)
        val = picker.value
        if val is Select.NULL:
            return
        idx = int(val)
        if idx not in self._selected_indices:
            self._selected_indices.append(idx)
        self._rebuild_condition_list()

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

        ex = self._existing
        sim = Simulation(
            label=label,
            success_rule=rule,
            run_count=runs,
            turn_limit=turn_limit,
        )
        self.dismiss((sim, list(self._selected_indices)))