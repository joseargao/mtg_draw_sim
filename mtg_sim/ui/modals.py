"""
mtg_sim/ui/modals.py — Modal dialogs for condition and simulation CRUD.

Stage 2: basic structure only.  Full validation and wiring in Stage 4.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static
from textual.containers import Horizontal, Vertical

from ..engine.simulation import Comparator, Condition, SuccessRule, Simulation


# ---------------------------------------------------------------------------
# ConditionModal
# ---------------------------------------------------------------------------

class ConditionModal(ModalScreen[Condition | None]):
    """
    Modal for creating or editing a Condition.

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
            yield Input(
                value=ex.card_name if ex else "",
                placeholder="e.g. Lightning Bolt",
                id="input-card",
                classes="modal-input",
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

            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel")
                yield Button("Save", id="btn-save", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
            return
        self._save()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _save(self) -> None:
        card = self.query_one("#input-card", Input).value.strip()
        if not card:
            return  # TODO Stage 4: show inline validation error

        try:
            count = int(self.query_one("#input-count", Input).value.strip())
            turn  = int(self.query_one("#input-turn", Input).value.strip())
        except ValueError:
            return

        comparator = self.query_one("#select-comparator", Select).value
        if comparator is Select.BLANK:
            comparator = Comparator.GTE

        label = self.query_one("#input-label", Input).value.strip()
        ex = self._existing

        cond = Condition(
            card_name=card,
            comparator=comparator,
            count=count,
            turn_deadline=turn,
            label=label,
            id=ex.id if ex else __import__("uuid").uuid4().hex[:8],
        )
        self.dismiss(cond)


# ---------------------------------------------------------------------------
# SimulationModal
# ---------------------------------------------------------------------------

class SimulationModal(ModalScreen[Simulation | None]):
    """
    Modal for creating or editing a Simulation.

    Returns a Simulation on confirm, None on cancel.
    Condition assignment happens in the main UI (Stage 4).
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(
        self,
        existing: Simulation | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._existing = existing

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
                options=[("ANY (at least one condition)", SuccessRule.ANY),
                         ("ALL (every condition)", SuccessRule.ALL)],
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

            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel")
                yield Button("Save", id="btn-save", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
            return
        self._save()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _save(self) -> None:
        name = self.query_one("#input-name", Input).value.strip()
        if not name:
            return

        try:
            runs = int(self.query_one("#input-runs", Input).value.strip())
        except ValueError:
            return

        turn_raw = self.query_one("#input-turns", Input).value.strip()
        turn_limit = int(turn_raw) if turn_raw else None

        rule = self.query_one("#select-rule", Select).value
        if rule is Select.BLANK:
            rule = SuccessRule.ALL

        ex = self._existing
        sim = Simulation(
            name=name,
            success_rule=rule,
            run_count=runs,
            turn_limit=turn_limit,
            conditions=list(ex.conditions) if ex else [],
            id=ex.id if ex else __import__("uuid").uuid4().hex[:8],
        )
        self.dismiss(sim)