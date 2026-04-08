from yahtzee.advisor import YahtzeeAdvisor
from yahtzee.models import ActionType, Category, Scorecard


def test_triple_sixes_preferred_hold():
    advisor = YahtzeeAdvisor()
    rec = advisor.recommend([6, 6, 6, 2, 1], 1, Scorecard())
    assert rec.best_action.action_type == ActionType.HOLD_AND_REROLL
    assert rec.best_action.held_dice is not None
    assert rec.best_action.held_dice.count(6) >= 3


def test_large_straight_roll3_score_now():
    advisor = YahtzeeAdvisor()
    sc = Scorecard()
    rec = advisor.recommend([2, 3, 4, 5, 6], 3, sc)
    assert rec.best_action.action_type == ActionType.SCORE_NOW
    assert rec.best_stop_category in {Category.LARGE_STRAIGHT, Category.CHANCE}


def test_roll3_never_reroll():
    advisor = YahtzeeAdvisor()
    rec = advisor.recommend([1, 1, 2, 3, 4], 3, Scorecard())
    assert all(a.action_type == ActionType.SCORE_NOW for a in rec.top_actions)
