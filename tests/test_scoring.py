import pytest

from yahtzee.models import Category, Scorecard
from yahtzee.scoring import (
    legal_categories_for_roll,
    raw_category_score,
    score_roll_in_category,
    score_with_scorecard,
)


def test_raw_category_scores_edge_checks():
    assert raw_category_score((2, 2, 3, 3, 3), Category.FULL_HOUSE) == 25
    assert raw_category_score((1, 2, 3, 4, 6), Category.SMALL_STRAIGHT) == 30
    assert raw_category_score((2, 3, 4, 5, 6), Category.LARGE_STRAIGHT) == 40
    assert raw_category_score((6, 6, 6, 6, 2), Category.FOUR_KIND) == 26
    assert raw_category_score((2, 2, 2, 4, 5), Category.FOUR_KIND) == 0
    assert raw_category_score((1, 1, 1, 1, 1), Category.CHANCE) == 5


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


def test_yahtzee_zero_does_not_enable_bonus_or_joker():
    sc = Scorecard()
    sc.scores[Category.YAHTZEE] = 0
    legal = legal_categories_for_roll((6, 6, 6, 6, 6), sc)
    assert Category.FULL_HOUSE in legal
    result = score_roll_in_category((6, 6, 6, 6, 6), Category.FULL_HOUSE, sc)
    assert result.yahtzee_bonus_awarded == 0
    assert result.score == 0


def test_extra_yahtzee_forces_upper_when_open():
    sc = Scorecard()
    sc.scores[Category.YAHTZEE] = 50
    legal = legal_categories_for_roll((6, 6, 6, 6, 6), sc)
    assert legal == [Category.SIXES]
    with pytest.raises(ValueError):
        score_roll_in_category((6, 6, 6, 6, 6), Category.FULL_HOUSE, sc)


def test_extra_yahtzee_joker_when_forced_upper_closed():
    sc = Scorecard()
    sc.scores[Category.YAHTZEE] = 50
    sc.scores[Category.SIXES] = 24
    legal = legal_categories_for_roll((6, 6, 6, 6, 6), sc)
    assert Category.FULL_HOUSE in legal
    result = score_roll_in_category((6, 6, 6, 6, 6), Category.FULL_HOUSE, sc)
    assert result.yahtzee_bonus_awarded == 100
    assert result.score == 25


def test_extra_yahtzee_when_lower_full_allows_open_upper():
    sc = Scorecard()
    sc.scores[Category.YAHTZEE] = 50
    sc.scores[Category.SIXES] = 18
    for cat in [
        Category.THREE_KIND,
        Category.FOUR_KIND,
        Category.FULL_HOUSE,
        Category.SMALL_STRAIGHT,
        Category.LARGE_STRAIGHT,
        Category.CHANCE,
    ]:
        sc.scores[cat] = 0

    legal = legal_categories_for_roll((6, 6, 6, 6, 6), sc)
    assert legal == [Category.ONES, Category.TWOS, Category.THREES, Category.FOURS, Category.FIVES]


def test_score_with_scorecard_back_compat():
    sc = Scorecard()
    score, yb = score_with_scorecard((2, 2, 3, 3, 3), Category.FULL_HOUSE, sc)
    assert (score, yb) == (25, 0)
