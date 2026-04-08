from yahtzee.models import Category, Scorecard
from yahtzee.scoring import category_score, score_with_scorecard


def test_category_scores():
    dice = (2, 2, 3, 3, 3)
    assert category_score(dice, Category.FULL_HOUSE) == 25
    assert category_score((1, 2, 3, 4, 6), Category.SMALL_STRAIGHT) == 30
    assert category_score((2, 3, 4, 5, 6), Category.LARGE_STRAIGHT) == 40
    assert category_score((6, 6, 6, 6, 2), Category.FOUR_KIND) == 26
    assert category_score((1, 1, 1, 1, 1), Category.CHANCE) == 5


def test_upper_bonus_math():
    sc = Scorecard()
    sc.scores[Category.ONES] = 3
    sc.scores[Category.TWOS] = 6
    sc.scores[Category.THREES] = 9
    sc.scores[Category.FOURS] = 12
    sc.scores[Category.FIVES] = 15
    sc.scores[Category.SIXES] = 18
    assert sc.upper_subtotal == 63
    assert sc.upper_bonus == 35


def test_yahtzee_bonus_and_joker_enforced():
    sc = Scorecard()
    sc.scores[Category.YAHTZEE] = 50
    sc.scores[Category.SIXES] = None
    import pytest
    with pytest.raises(ValueError):
        score_with_scorecard((6, 6, 6, 6, 6), Category.FULL_HOUSE, sc)
