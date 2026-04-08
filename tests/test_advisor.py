from yahtzee.advisor import YahtzeeAdvisor
from yahtzee.models import ActionType, Category, Scorecard


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
