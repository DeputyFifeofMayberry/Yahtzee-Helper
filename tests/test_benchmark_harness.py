from random import Random

from benchmark.metrics import summarize_game_results, summarize_oracle_results
from benchmark.models import PolicyDecision
from benchmark.page_helpers import STRATEGY_METADATA, flatten_full_summary, flatten_oracle_summary, strategy_display_name
from benchmark.policies import HumanHeuristicPolicy, ObjectivePolicy
from benchmark.simulator import apply_decision_once, classify_state
from yahtzee.advisor import YahtzeeAdvisor
from yahtzee.models import ActionType, Category, GameState, OptimizationObjective, Scorecard


def test_human_heuristic_policy_returns_legal_decision():
    advisor = YahtzeeAdvisor()
    policy = HumanHeuristicPolicy()
    state = GameState(scorecard=Scorecard(), turn_index=1, current_dice=[2, 3, 4, 5, 6], roll_number=1)
    decision = policy.decide(state, advisor)
    assert decision.action_type in {ActionType.HOLD_AND_REROLL, ActionType.SCORE_NOW}


def test_objective_policy_can_be_created_for_board_utility():
    policy = ObjectivePolicy("board_utility", OptimizationObjective.BOARD_UTILITY)
    assert policy.name == "board_utility"


def test_apply_decision_once_advances_scored_state():
    state = GameState(scorecard=Scorecard(), turn_index=1, current_dice=[2, 2, 2, 3, 4], roll_number=3)
    next_state = apply_decision_once(
        state,
        decision=PolicyDecision(ActionType.SCORE_NOW, category=Category.THREE_KIND, description="Score three kind."),
        rng=Random(1),
    )
    assert next_state.turn_index == 2


def test_classify_state_tags_common_patterns():
    state = GameState(scorecard=Scorecard(), turn_index=1, current_dice=[2, 3, 4, 4, 5], roll_number=1)
    tags = classify_state(state)
    assert "roll_1" in tags
    assert "phase_early" in tags


def test_strategy_display_metadata_used_in_helpers():
    assert strategy_display_name("board_utility") == "Board-aware strategy"
    game_rows = flatten_full_summary({"board_utility": summarize_game_results([])})
    oracle_rows = flatten_oracle_summary({"board_utility": summarize_oracle_results([])})
    assert game_rows[0]["Strategy"] == "Board-aware strategy"
    assert oracle_rows[0]["Strategy"] == "Board-aware strategy"
    assert set(STRATEGY_METADATA.keys()) >= {"board_utility", "exact_turn_ev", "human_heuristic", "rollout_oracle"}
