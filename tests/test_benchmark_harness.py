from random import Random

from benchmark.metrics import summarize_game_results, summarize_oracle_results
from benchmark.models import DecisionStateSnapshot, PolicyDecision
from benchmark.oracle import RolloutOraclePolicy, compare_policies_to_oracle
from benchmark.policies import HumanHeuristicPolicy, ObjectivePolicy
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


def test_summary_helpers_return_expected_shapes():
    advisor = YahtzeeAdvisor()
    policy = ObjectivePolicy("board_utility", OptimizationObjective.BOARD_UTILITY)
    game_results = [simulate_full_game(policy, seed=seed, advisor=advisor) for seed in (1, 2)]
    summary = summarize_game_results(game_results)
    assert summary["games"] == 2
    assert "average_final_score" in summary

    oracle_summary = summarize_oracle_results([])
    assert oracle_summary["comparisons"] == 0
