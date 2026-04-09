from random import Random

from benchmark.metrics import summarize_game_results, summarize_oracle_results
from benchmark.models import DecisionStateSnapshot, PolicyDecision
from benchmark.oracle import RolloutOraclePolicy, compare_policies_to_oracle
from benchmark.page_helpers import flatten_full_summary, flatten_oracle_summary, preset_name_for_settings
from benchmark.policies import HumanHeuristicPolicy, ObjectivePolicy
from benchmark.run import BenchmarkSettings, profile_settings
from benchmark.simulator import apply_decision_once, classify_state, simulate_full_game
from yahtzee.advisor import YahtzeeAdvisor
from yahtzee.models import ActionType, Category, GameState, OptimizationObjective, Scorecard


def test_simulate_full_game_runs_for_board_policy():
    advisor = YahtzeeAdvisor()
    policy = ObjectivePolicy("board_utility", OptimizationObjective.BOARD_UTILITY)
    result = simulate_full_game(policy, seed=123, advisor=advisor)
    assert result.final_score >= 0
    assert isinstance(result.category_scores["Chance"], (int, type(None)))
    assert result.policy_name == "board_utility"


def test_human_heuristic_policy_returns_legal_decision():
    advisor = YahtzeeAdvisor()
    policy = HumanHeuristicPolicy()
    state = GameState(scorecard=Scorecard(), turn_index=1, current_dice=[2, 3, 4, 5, 6], roll_number=1)
    decision = policy.decide(state, advisor)
    assert decision.action_type in {ActionType.HOLD_AND_REROLL, ActionType.SCORE_NOW}


def test_apply_decision_once_advances_scored_state():
    state = GameState(scorecard=Scorecard(), turn_index=1, current_dice=[2, 2, 2, 3, 4], roll_number=3)
    next_state = apply_decision_once(
        state,
        decision=PolicyDecision(ActionType.SCORE_NOW, category=Category.THREE_KIND, description="Score three kind."),
        rng=Random(1),
    )
    assert next_state.turn_index == 2


def test_classify_state_tags_common_patterns():
    scorecard = Scorecard()
    state = GameState(scorecard=scorecard, turn_index=1, current_dice=[2, 3, 4, 4, 5], roll_number=1)
    tags = classify_state(state)
    assert "roll_1" in tags
    assert "phase_early" in tags
    assert "made_small_straight" in tags


def test_oracle_comparison_records_are_generated():
    advisor = YahtzeeAdvisor()
    snapshot = DecisionStateSnapshot(
        score_signature=Scorecard().score_signature(),
        dice=(2, 3, 4, 5, 6),
        roll_number=1,
        turn_index=1,
        tags=("phase_early", "made_large_straight"),
    )
    policies = [
        ObjectivePolicy("board_utility", OptimizationObjective.BOARD_UTILITY),
        ObjectivePolicy("exact_turn_ev", OptimizationObjective.EXACT_TURN_EV),
        HumanHeuristicPolicy(),
    ]
    oracle = RolloutOraclePolicy(rollouts_per_action=3, continuation_policy=policies[0])
    records = compare_policies_to_oracle([snapshot], policies, oracle, advisor=advisor)
    assert len(records) == len(policies)
    assert {record.policy_name for record in records} == {"board_utility", "exact_turn_ev", "human_heuristic"}


def test_oracle_comparison_caches_repeated_snapshot_evaluations():
    advisor = YahtzeeAdvisor()
    snapshot = DecisionStateSnapshot(
        score_signature=Scorecard().score_signature(),
        dice=(1, 1, 1, 2, 3),
        roll_number=2,
        turn_index=4,
        tags=("phase_mid",),
    )

    class FixedPolicy:
        name = "fixed"

        def decide(self, state, advisor):
            return PolicyDecision(ActionType.HOLD_AND_REROLL, held_dice=(1, 1, 1), description="hold triples")

    policies = [FixedPolicy()]
    oracle = RolloutOraclePolicy(rollouts_per_action=2)
    oracle.decide = lambda state, advisor: PolicyDecision(  # type: ignore[method-assign]
        ActionType.HOLD_AND_REROLL,
        held_dice=(1, 1, 1),
        description="hold triples",
    )

    call_counter = {"count": 0}

    def fake_estimate(state, decision, advisor, rollout_seeds, decision_cache=None):
        key = (state.scorecard.score_signature(), tuple(state.current_dice), tuple(rollout_seeds), tuple(decision.held_dice or ()))
        if decision_cache is not None and key in decision_cache:
            return decision_cache[key]
        call_counter["count"] += 1
        value = float(len(rollout_seeds))
        if decision_cache is not None:
            decision_cache[key] = value
        return value

    oracle._estimate_action_value = fake_estimate  # type: ignore[method-assign]
    compare_policies_to_oracle([snapshot, snapshot], policies, oracle, advisor=advisor, evaluation_rollouts=2)
    assert call_counter["count"] == 1


def test_page_helper_flattens_and_detects_custom_edited_preset():
    preset = profile_settings("fast", seed=7)
    presets = {"Fast Check": preset}

    assert preset_name_for_settings(preset, presets) == "Fast Check"
    edited = BenchmarkSettings(**{**preset.__dict__, "full_games": preset.full_games + 1})
    assert preset_name_for_settings(edited, presets) == "Custom (edited)"

    game_rows = flatten_full_summary({"board_utility": summarize_game_results([])})
    assert game_rows[0]["Strategy"] == "board_utility"

    oracle_rows = flatten_oracle_summary({"board_utility": summarize_oracle_results([])})
    assert oracle_rows[0]["Strategy"] == "board_utility"


def test_summary_helpers_return_expected_shapes():
    advisor = YahtzeeAdvisor()
    policy = ObjectivePolicy("board_utility", OptimizationObjective.BOARD_UTILITY)
    game_results = [simulate_full_game(policy, seed=seed, advisor=advisor) for seed in (1, 2)]
    summary = summarize_game_results(game_results)
    assert summary["games"] == 2
    assert "average_final_score" in summary

    oracle_summary = summarize_oracle_results([])
    assert oracle_summary["comparisons"] == 0
