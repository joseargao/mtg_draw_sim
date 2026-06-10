"""
mtg_sim/ui/modals.py — Modal dialogs for condition and simulation CRUD.
"""

from __future__ import annotations

import uuid
import dataclasses

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static
from textual.containers import Horizontal, Vertical, ScrollableContainer
from rich.text import Text

from ..engine.simulation import Comparator, Condition, SuccessRule, Simulation


# ---------------------------------------------------------------------------
# ConditionModal
# ---------------------------------------------------------------------------

class ConditionModal(ModalScreen[Condition | None]):
    """
    Modal for creating or editing a Condition.

    Card name is chosen from a searchable dropdown populated from the deck.
    Returns a Condition on confirm, None on cancel.
    """

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
            yield Static(
                "Edit condition" if ex else "Add condition",
                classes="modal-title",
            )

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
                classes="modal-input",
            )

            yield Label("Turn deadline", classes="modal-label")
            yield Input(
                value=str(ex.turn_deadline) if ex else "4",
                placeholder="e.g. 4",
                id="input-turn",
                classes="modal-input",
            )

            yield Label("Label (optional)", classes="modal-label")
            yield Input(
                value=ex.label if ex else "",
                placeholder="e.g. Early bolt",
                id="input-label",
                classes="modal-input",
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
        except ValueError:
            self._show_error("Count must be a whole number.")
            return

        try:
            turn = int(self.query_one("#input-turn", Input).value.strip())
        except ValueError:
            self._show_error("Turn deadline must be a whole number.")
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
        ex = self._existing

        cond = Condition(
            card_name=card,
            comparator=comparator,
            count=count,
            turn_deadline=turn,
            label=label,
            id=ex.id if ex else uuid.uuid4().hex[:8],
        )
        self.dismiss(cond)


# ---------------------------------------------------------------------------
# SimulationModal
# ---------------------------------------------------------------------------

class SimulationModal(ModalScreen[Simulation | None]):
    """
    Modal for creating or editing a Simulation.

    Conditions are assigned via a dropdown + Add button, building up a list.
    Returns a Simulation on confirm, None on cancel.
    """

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
        # Start with conditions already on the simulation, or empty
        self._selected_ids: list[str] = (
            [c.id for c in existing.conditions] if existing else []
        )

    def compose(self) -> ComposeResult:
        ex = self._existing
        with Vertical(classes="modal-container"):
            yield Static(
                "Edit simulation" if ex else "Add simulation",
                classes="modal-title",
            )

            yield Label("Name", classes="modal-label")
            yield Input(
                value=ex.name if ex else "",
                placeholder="e.g. Aggro opener",
                id="input-name",
                classes="modal-input",
            )

            yield Label("Success rule", classes="modal-label")
            yield Select(
                options=[
                    ("ALL — every condition must be met", SuccessRule.ALL),
                    ("ANY — at least one condition must be met", SuccessRule.ANY),
                ],
                value=ex.success_rule if ex else SuccessRule.ALL,
                id="select-rule",
                classes="modal-select",
            )

            yield Label("Run count", classes="modal-label")
            yield Input(
                value=str(ex.run_count) if ex else "10000",
                placeholder="e.g. 10000",
                id="input-runs",
                classes="modal-input",
            )

            yield Label("Turn limit (blank = auto from conditions)", classes="modal-label")
            yield Input(
                value=str(ex.turn_limit) if (ex and ex.turn_limit) else "",
                placeholder="auto",
                id="input-turns",
                classes="modal-input",
            )

            # Condition picker
            yield Label("Conditions", classes="modal-label")
            with Horizontal(classes="modal-picker-row"):
                yield Select(
                    options=self._condition_options(),
                    prompt="Pick a condition to add…",
                    allow_blank=True,
                    id="select-condition",
                    classes="modal-select modal-picker-select",
                )
                yield Button("Add", id="btn-add-condition", classes="modal-picker-btn")

            # Live list of assigned conditions
            yield ScrollableContainer(
                *self._build_condition_tags(),
                id="condition-list",
                classes="modal-condition-list",
            )

            yield Static("", id="modal-error", classes="modal-error")

            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel")
                yield Button("Save", id="btn-save", variant="primary")

    # ------------------------------------------------------------------
    # Condition picker helpers
    # ------------------------------------------------------------------

    def _condition_options(self) -> list[tuple[Text, str]]:
        """Options for the condition dropdown — excludes already-added ones.
        Uses Rich Text objects so card names with special characters are safe.
        """
        return [
            (Text(self._condition_label(c), no_wrap=True), c.id)
            for c in self._all_conditions
            if c.id not in self._selected_ids
        ]

    def _condition_label(self, c: Condition) -> str:
        """Plain text label — no Rich markup, safe to embed anywhere."""
        label = c.label or f"{c.card_name} {c.comparator} {c.count}"
        return f"{label}  (by turn {c.turn_deadline})"

    def _build_condition_tags(self) -> list[Static]:
        """Build the list of currently assigned condition rows."""
        if not self._selected_ids:
            return [Static("No conditions added yet.", classes="modal-no-conditions")]
        widgets = []
        for cid in self._selected_ids:
            cond = next((c for c in self._all_conditions if c.id == cid), None)
            if cond is None:
                continue
            label = self._condition_label(cond)
            widgets.append(
                Static(f"  {label}",
                       markup=False,
                       classes="modal-condition-tag",
                       id=f"tag-{cid}")
            )
        return widgets

    def _rebuild_condition_list(self) -> None:
        """Re-render the condition list and refresh the dropdown options."""
        container = self.query_one("#condition-list", ScrollableContainer)
        container.remove_children()
        for w in self._build_condition_tags():
            container.mount(w)

        # Refresh dropdown to remove already-added conditions
        picker = self.query_one("#select-condition", Select)
        picker.set_options(self._condition_options())

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-save":
            self._save()
        elif event.button.id == "btn-add-condition":
            self._add_condition()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _add_condition(self) -> None:
        picker = self.query_one("#select-condition", Select)
        cid = picker.value
        if cid is Select.NULL:
            return
        if cid not in self._selected_ids:
            self._selected_ids.append(cid)
        self._rebuild_condition_list()

    def _show_error(self, msg: str) -> None:
        self.query_one("#modal-error", Static).update(f"[red]{msg}[/red]")

    def _save(self) -> None:
        name = self.query_one("#input-name", Input).value.strip()
        if not name:
            self._show_error("Name cannot be empty.")
            return

        try:
            runs = int(self.query_one("#input-runs", Input).value.strip())
        except ValueError:
            self._show_error("Run count must be a whole number.")
            return

        if runs <= 0:
            self._show_error("Run count must be greater than zero.")
            return

        turn_raw = self.query_one("#input-turns", Input).value.strip()
        turn_limit: int | None = None
        if turn_raw:
            try:
                turn_limit = int(turn_raw)
            except ValueError:
                self._show_error("Turn limit must be a whole number or blank.")
                return

        rule = self.query_one("#select-rule", Select).value
        if rule is Select.NULL:
            rule = SuccessRule.ALL

        # Resolve condition objects from selected IDs (preserving order)
        selected_conditions = [
            c for cid in self._selected_ids
            for c in self._all_conditions
            if c.id == cid
        ]

        ex = self._existing
        sim = Simulation(
            name=name,
            success_rule=rule,
            run_count=runs,
            turn_limit=turn_limit,
            conditions=selected_conditions,
            id=ex.id if ex else uuid.uuid4().hex[:8],
        )
        self.dismiss(sim)