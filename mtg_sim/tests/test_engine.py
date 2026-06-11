"""
Stage 1 engine tests.

Run with:  python -m pytest tests/ -v
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mtg_sim.engine import (
    Card, Deck, GameState, Comparator, Condition, SuccessRule,
    Simulation, SimulationRunner, Config, AppState,
)


# ===========================================================================
# Deck
# ===========================================================================

SAMPLE_DECKLIST = """
Deck
4 Lightning Bolt
4 Goblin Guide
4 Monastery Swiftspear
4 Eidolon of the Great Revel
4 Searing Blaze
4 Shard Volley
3 Inspiring Vantage
9 Mountain
4 Sacred Foundry
"""

class TestDeck:
    def test_parse_basic(self):
        deck = Deck.from_text(SAMPLE_DECKLIST)
        assert deck.size == 40

    def test_counts(self):
        deck = Deck.from_text(SAMPLE_DECKLIST)
        assert deck.counts["Lightning Bolt"] == 4
        assert deck.counts["Mountain"] == 9

    def test_sideboard_excluded(self):
        text = SAMPLE_DECKLIST + "\nSideboard\n2 Pyroblast\n"
        deck = Deck.from_text(text)
        assert "Pyroblast" not in deck.counts

    def test_arena_format_with_set_codes(self):
        text = "Deck\n4 Lightning Bolt (M11) 100\n20 Mountain (BRO) 265\n"
        deck = Deck.from_text(text)
        assert deck.size == 24
        assert deck.counts["Lightning Bolt"] == 4

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            Deck.from_text("Deck\n\n")

    def test_cards_immutable(self):
        deck = Deck.from_text(SAMPLE_DECKLIST)
        assert isinstance(deck.cards, tuple)

    def test_source_label(self):
        deck = Deck.from_text(SAMPLE_DECKLIST, source="burn.txt")
        assert deck.source == "burn.txt"


# ===========================================================================
# GameState
# ===========================================================================

class TestGameState:
    @pytest.fixture
    def deck(self):
        return Deck.from_text(SAMPLE_DECKLIST)

    @pytest.fixture
    def gs(self, deck):
        import random
        gs = GameState(deck=deck, rng=random.Random(42), hand_size=7)
        gs.reset()
        gs.deal_opening_hand()
        return gs

    def test_opening_hand_size(self, gs):
        assert gs.hand_size_current == 7

    def test_library_size_after_hand(self, gs, deck):
        assert gs.library_size == deck.size - 7

    def test_advance_turn_draws_one(self, gs):
        lib_before = gs.library_size
        hand_before = gs.hand_size_current
        drawn = gs.advance_turn(cards_per_turn=1)
        assert len(drawn) == 1
        assert gs.hand_size_current == hand_before + 1
        assert gs.library_size == lib_before - 1

    def test_turn_counter_increments(self, gs):
        assert gs.turn == 0
        gs.advance_turn()
        assert gs.turn == 1
        gs.advance_turn()
        assert gs.turn == 2

    def test_reset_clears_state(self, gs):
        gs.advance_turn()
        gs.advance_turn()
        gs.reset()
        assert gs.turn == 0
        assert gs.hand_size_current == 0
        assert gs.library_size == gs.deck.size

    def test_count_in_hand(self, gs, deck):
        # After opening hand, counts should sum to 7
        total = sum(gs.count_in_hand(name) for name in deck.counts)
        assert total == 7

    def test_seeded_reproducible(self, deck):
        import random
        gs1 = GameState(deck=deck, rng=random.Random(99))
        gs1.reset(seed=99); gs1.deal_opening_hand()

        gs2 = GameState(deck=deck, rng=random.Random(99))
        gs2.reset(seed=99); gs2.deal_opening_hand()

        assert [c.name for c in gs1.hand] == [c.name for c in gs2.hand]


# ===========================================================================
# Condition
# ===========================================================================

class TestCondition:
    def test_gte_satisfied(self):
        c = Condition("Forest", Comparator.GTE, 2, turn_deadline=2)
        assert c.evaluate({"Forest": 2}, current_turn=2)

    def test_gte_not_satisfied(self):
        c = Condition("Forest", Comparator.GTE, 2, turn_deadline=2)
        assert not c.evaluate({"Forest": 1}, current_turn=2)

    def test_past_deadline_always_false(self):
        c = Condition("Forest", Comparator.GTE, 1, turn_deadline=2)
        assert not c.evaluate({"Forest": 5}, current_turn=3)

    def test_missing_card_counts_zero(self):
        c = Condition("Forest", Comparator.GT, 0, turn_deadline=4)
        assert not c.evaluate({}, current_turn=1)

    def test_eq_comparator(self):
        c = Condition("Island", Comparator.EQ, 2, turn_deadline=3)
        assert c.evaluate({"Island": 2}, 1)
        assert not c.evaluate({"Island": 3}, 1)

    def test_auto_label(self):
        c = Condition("Lightning Bolt", Comparator.GT, 0, turn_deadline=4)
        assert "Lightning Bolt" in c.display_label
        assert "turn 4" in c.display_label

    def test_custom_label(self):
        c = Condition("Forest", Comparator.GTE, 2, 2, label="Ramp Online")
        assert c.display_label == "Ramp Online"

    def test_unique_ids(self):
        c1 = Condition("Forest", Comparator.GTE, 2, 2)
        c2 = Condition("Forest", Comparator.GTE, 2, 2)
        assert c1.id != c2.id


# ===========================================================================
# Simulation + SimulationRunner
# ===========================================================================

MONO_RED = """
Deck
4 Lightning Bolt
4 Goblin Guide
4 Monastery Swiftspear
4 Eidolon of the Great Revel
4 Searing Blaze
4 Shard Volley
4 Inspiring Vantage
12 Mountain
"""

class TestSimulation:
    @pytest.fixture
    def deck(self):
        return Deck.from_text(MONO_RED)

    @pytest.fixture
    def gs(self, deck):
        import random
        gs = GameState(deck=deck, rng=random.Random(0))
        return gs

    def test_effective_turn_limit_from_conditions(self):
        c1 = Condition("Mountain", Comparator.GTE, 1, turn_deadline=2)
        c2 = Condition("Lightning Bolt", Comparator.GT, 0, turn_deadline=4)
        sim = Simulation("Test", conditions=[c1, c2])
        assert sim.effective_turn_limit == 4

    def test_explicit_turn_limit_overrides(self):
        c = Condition("Mountain", Comparator.GTE, 1, turn_deadline=2)
        sim = Simulation("Test", conditions=[c], turn_limit=6)
        assert sim.effective_turn_limit == 6

    def test_success_rate_none_before_run(self):
        sim = Simulation("Test")
        assert sim.success_rate is None
        assert sim.success_rate_pct == "--"

    def test_run_completes(self, gs):
        c = Condition("Mountain", Comparator.GTE, 1, turn_deadline=4)
        sim = Simulation("Mountain Test", conditions=[c], run_count=100)
        runner = SimulationRunner(gs, cards_per_turn=1)
        runner.run(sim)
        assert sim.status == "COMPLETE"
        assert sim.total_runs == 100
        assert sim.success_rate is not None

    def test_always_true_condition(self, gs):
        # Mountain >= 0 by turn 4: always satisfied
        c = Condition("Mountain", Comparator.GTE, 0, turn_deadline=4)
        sim = Simulation("Always", conditions=[c], run_count=200, success_rule=SuccessRule.ALL)
        runner = SimulationRunner(gs, cards_per_turn=1)
        runner.run(sim)
        assert sim.success_rate == pytest.approx(1.0)

    def test_impossible_condition(self, gs):
        # Need 99 Lightning Bolts by turn 1 — impossible
        c = Condition("Lightning Bolt", Comparator.GTE, 99, turn_deadline=1)
        sim = Simulation("Impossible", conditions=[c], run_count=200)
        runner = SimulationRunner(gs, cards_per_turn=1)
        runner.run(sim)
        assert sim.success_rate == pytest.approx(0.0)

    def test_any_rule_succeeds_if_one_met(self, gs):
        c_easy = Condition("Mountain", Comparator.GTE, 0, turn_deadline=4)     # always true
        c_hard = Condition("Lightning Bolt", Comparator.GTE, 99, turn_deadline=1)  # always false
        sim = Simulation("OR Test", conditions=[c_easy, c_hard],
                         success_rule=SuccessRule.ANY, run_count=100)
        runner = SimulationRunner(gs, cards_per_turn=1)
        runner.run(sim)
        assert sim.success_rate == pytest.approx(1.0)

    def test_all_rule_fails_if_one_missed(self, gs):
        c_easy = Condition("Mountain", Comparator.GTE, 0, turn_deadline=4)
        c_hard = Condition("Lightning Bolt", Comparator.GTE, 99, turn_deadline=1)
        sim = Simulation("AND Test", conditions=[c_easy, c_hard],
                         success_rule=SuccessRule.ALL, run_count=100)
        runner = SimulationRunner(gs, cards_per_turn=1)
        runner.run(sim)
        assert sim.success_rate == pytest.approx(0.0)

    def test_progress_callback(self, gs):
        c = Condition("Mountain", Comparator.GTE, 0, turn_deadline=4)
        sim = Simulation("Progress", conditions=[c], run_count=50)
        runner = SimulationRunner(gs)
        calls = []
        runner.run(sim, progress_cb=lambda done, total: calls.append((done, total)))
        assert len(calls) == 50
        assert calls[-1] == (50, 50)

    def test_per_condition_hit_rates(self, gs):
        c = Condition("Mountain", Comparator.GTE, 0, turn_deadline=4)
        sim = Simulation("Hit Rate", conditions=[c], run_count=100)
        runner = SimulationRunner(gs)
        runner.run(sim)
        assert sim.condition_hit_rate(c.id) == pytest.approx(1.0)

    def test_seeded_run_reproducible(self, deck):
        import random
        c = Condition("Mountain", Comparator.GTE, 1, turn_deadline=3)

        gs1 = GameState(deck=deck, rng=random.Random(7))
        sim1 = Simulation("Seed Test", conditions=[c], run_count=500)
        SimulationRunner(gs1, seed=7).run(sim1)

        gs2 = GameState(deck=deck, rng=random.Random(7))
        sim2 = Simulation("Seed Test", conditions=[c], run_count=500)
        SimulationRunner(gs2, seed=7).run(sim2)

        assert sim1.success_count == sim2.success_count


# ===========================================================================
# Config
# ===========================================================================

class TestConfig:
    def test_defaults(self):
        cfg = Config()
        assert cfg.hand_size == 7
        assert cfg.cards_per_turn == 1
        assert cfg.run_count == 10_000
        assert cfg.seed is None

    def test_load_save_roundtrip(self, tmp_path):
        cfg = Config(hand_size=5, run_count=500, seed=42, deck_source="deck.txt")
        path = tmp_path / "config.ini"
        cfg.save(path)
        loaded = Config.load(path)
        assert loaded.hand_size == 5
        assert loaded.run_count == 500
        assert loaded.seed == 42
        assert loaded.deck_source == "deck.txt"

    def test_blank_seed_is_none(self, tmp_path):
        path = tmp_path / "c.ini"
        path.write_text("[simulation]\nrun_count=100\nseed=\n")
        cfg = Config.load(path)
        assert cfg.seed is None


# ===========================================================================
# AppState integration
# ===========================================================================

class TestAppState:
    @pytest.fixture
    def state(self):
        deck = Deck.from_text(MONO_RED)
        s = AppState()
        s.load_deck(deck)
        return s

    def test_load_deck(self, state):
        assert state.deck is not None
        assert state.game_state is not None

    def test_add_remove_condition(self, state):
        c = Condition("Mountain", Comparator.GTE, 1, 2)
        state.add_condition(c)
        assert c in state.conditions
        state.remove_condition(c.id)
        assert c not in state.conditions

    def test_remove_condition_cascades(self, state):
        c = Condition("Mountain", Comparator.GTE, 1, 2)
        state.add_condition(c)
        sim = Simulation("S", conditions=[c])
        state.add_simulation(sim)
        state.remove_condition(c.id)
        assert c not in state.simulations_using_condition(c.id)[0].conditions \
            if state.simulations_using_condition(c.id) else True

    def test_run_simulation(self, state):
        c = Condition("Mountain", Comparator.GTE, 1, 4)
        sim = Simulation("Test", conditions=[c], run_count=200)
        state.add_condition(c)
        state.add_simulation(sim)
        state.run_simulation(sim)
        assert sim.status == "COMPLETE"

    def test_simulations_using_condition(self, state):
        c = Condition("Mountain", Comparator.GTE, 1, 2)
        state.add_condition(c)
        sim = Simulation("S", conditions=[c])
        state.add_simulation(sim)
        assert sim in state.simulations_using_condition(c.id)

    def test_advance_turn(self, state):
        turn_before = state.game_state.turn
        state.advance_turn()
        assert state.game_state.turn == turn_before + 1

    def test_reset_game(self, state):
        state.advance_turn()
        state.advance_turn()
        state.reset_game()
        assert state.game_state.turn == 0