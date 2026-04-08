from yahtzee.advisor import YahtzeeAdvisor
from yahtzee.models import ActionType, Category, OptimizationObjective, Scorecard
from yahtzee.rules import legal_categories_for_roll
from yahtzee.state import GameManager


def test_triple_sixes_preferred_hold():
    advisor = YahtzeeAdvisor()
    rec = advisor.recommend([6, 6, 6, 2, 1], 1, Scorecard())
    assert rec.best_action.action_type == ActionType.HOLD_AND_REROLL
    assert rec.best_action.held_dice is not None
    assert rec.best_action.held_dice.count(6) >= 3
    assert len(rec.best_action.held_dice) <= 4


def test_large_straight_roll3_prefers_scoring_large_straight():
    advisor = YahtzeeAdvisor()
    sc = Scorecard()
    rec = advisor.recommend([2, 3, 4, 5, 6], 3, sc)
    assert rec.best_action.action_type == ActionType.SCORE_NOW
    assert rec.best_action.category == Category.LARGE_STRAIGHT


def test_roll3_never_reroll():
    advisor = YahtzeeAdvisor()
    rec = advisor.recommend([1, 1, 2, 3, 4], 3, Scorecard())
    assert all(a.action_type == ActionType.SCORE_NOW for a in rec.top_actions)


def test_probability_outputs_roll1_vs_roll2_are_distinct_and_valid():
    advisor = YahtzeeAdvisor()
    sc = Scorecard()
    p_roll1 = advisor.optimal_turn_outcome_probabilities((6, 6, 6), 2, sc)
    p_roll2 = advisor.optimal_turn_outcome_probabilities((6, 6, 6), 1, sc)
    assert p_roll1 != p_roll2
    assert abs(sum(p_roll1.values()) - 1.0) < 1e-9
    assert abs(sum(p_roll2.values()) - 1.0) < 1e-9


def test_materially_different_scorecards_have_different_signatures():
    a = Scorecard()
    b = Scorecard()
    a.scores[Category.ONES] = 3
    b.scores[Category.ONES] = 0
    assert a.open_categories() == b.open_categories()
    assert a.score_signature() != b.score_signature()


def test_roll1_distribution_uses_two_step_optimal_continuation():
    advisor = YahtzeeAdvisor()
    sc = Scorecard()
    one_step = advisor.optimal_turn_outcome_probabilities((6, 6, 6), 1, sc)
    two_step = advisor.optimal_turn_outcome_probabilities((6, 6, 6), 2, sc)
    assert two_step["Yahtzee"] > one_step["Yahtzee"]


def test_advisor_score_now_never_recommends_illegal_joker_category():
    advisor = YahtzeeAdvisor()
    sc = Scorecard()
    sc.scores[Category.YAHTZEE] = 50
    rec = advisor.recommend([6, 6, 6, 6, 6], 3, sc)
    assert rec.best_action.category == Category.SIXES
    assert rec.best_action.category in legal_categories_for_roll((6, 6, 6, 6, 6), sc)


def test_game_manager_rejects_illegal_joker_apply_path():
    manager = GameManager()
    manager.state.scorecard.scores[Category.YAHTZEE] = 50
    manager.set_current_roll([6, 6, 6, 6, 6], 3)
    try:
        manager.apply_score(Category.CHANCE)
        assert False, "expected illegal category to be rejected"
    except ValueError as exc:
        assert "Illegal category for roll" in str(exc)


def test_roll3_recommendation_category_is_legal_in_joker_state():
    advisor = YahtzeeAdvisor()
    sc = Scorecard()
    sc.scores[Category.YAHTZEE] = 0
    sc.scores[Category.TWOS] = 6
    rec = advisor.recommend([2, 2, 2, 2, 2], 3, sc)
    assert rec.best_action.action_type == ActionType.SCORE_NOW
    legal = legal_categories_for_roll((2, 2, 2, 2, 2), sc)
    assert rec.best_action.category in legal


def test_choose_best_hold_matches_recommendation_for_exact_turn_ev():
    advisor = YahtzeeAdvisor()
    sc = Scorecard()
    dice = [2, 2, 3, 3, 6]
    rec = advisor.recommend(dice, 1, sc, objective=OptimizationObjective.EXACT_TURN_EV)
    expected_hold = advisor.choose_best_hold(tuple(sorted(dice)), 2, sc.score_signature(), OptimizationObjective.EXACT_TURN_EV)
    assert rec.best_action.held_dice == expected_hold


def test_probability_of_max_yahtzee_state_is_at_least_recommended_line():
    advisor = YahtzeeAdvisor()
    sc = Scorecard()
    rec = advisor.recommend([2, 2, 3, 3, 6], 1, sc, objective=OptimizationObjective.BOARD_UTILITY)
    assert rec.max_yahtzee_probability >= rec.recommended_line_yahtzee_probability
