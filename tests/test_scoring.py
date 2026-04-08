import pytest

from yahtzee.models import Category, Scorecard
from yahtzee.scoring import (
    apply_score_to_scorecard,
    ordinary_category_score,
    preview_score_for_category,
    raw_category_score,
    score_with_scorecard,
)


def test_upper_section_scores_each_face():
    dice = (1, 2, 3, 4, 5)
    assert ordinary_category_score(dice, Category.ONES) == 1
    assert ordinary_category_score(dice, Category.TWOS) == 2
    assert ordinary_category_score(dice, Category.THREES) == 3
    assert ordinary_category_score(dice, Category.FOURS) == 4
    assert ordinary_category_score(dice, Category.FIVES) == 5
    assert ordinary_category_score(dice, Category.SIXES) == 0


def test_basic_lower_scoring_positive_and_negative_cases():
    assert ordinary_category_score((6, 6, 6, 2, 1), Category.THREE_KIND) == 21
    assert ordinary_category_score((6, 6, 2, 2, 1), Category.THREE_KIND) == 0
    assert ordinary_category_score((6, 6, 6, 6, 2), Category.FOUR_KIND) == 26
    assert ordinary_category_score((2, 2, 2, 4, 5), Category.FOUR_KIND) == 0
    assert ordinary_category_score((2, 2, 3, 3, 3), Category.FULL_HOUSE) == 25
    assert ordinary_category_score((2, 2, 2, 2, 3), Category.FULL_HOUSE) == 0
    assert ordinary_category_score((1, 2, 3, 4, 6), Category.SMALL_STRAIGHT) == 30
    assert ordinary_category_score((1, 2, 3, 4, 4), Category.LARGE_STRAIGHT) == 0
    assert ordinary_category_score((2, 3, 4, 5, 6), Category.LARGE_STRAIGHT) == 40
    assert ordinary_category_score((1, 1, 1, 1, 1), Category.YAHTZEE) == 50
    assert ordinary_category_score((1, 1, 1, 1, 1), Category.CHANCE) == 5


def test_upper_bonus_thresholds():
    sc = Scorecard()
    sc.scores[Category.ONES] = 3
    sc.scores[Category.TWOS] = 6
    sc.scores[Category.THREES] = 9
    sc.scores[Category.FOURS] = 12
    sc.scores[Category.FIVES] = 15
    sc.scores[Category.SIXES] = 17
    assert sc.upper_subtotal == 62
    assert sc.upper_bonus == 0

    sc.scores[Category.SIXES] = 18
    assert sc.upper_subtotal == 63
    assert sc.upper_bonus == 35

    sc.scores[Category.SIXES] = 24
    assert sc.upper_subtotal == 69
    assert sc.upper_bonus == 35


def test_yahtzee_box_unfilled_roll_yahtzee_is_normal_rules_only():
    sc = Scorecard()
    result = preview_score_for_category((6, 6, 6, 6, 6), Category.FULL_HOUSE, sc)
    assert result.yahtzee_bonus_awarded == 0
    assert result.score == 0
    assert result.rule_metadata["is_extra_yahtzee"] is False


def test_yahtzee_50_matching_upper_open_forces_only_upper_and_bonus():
    sc = Scorecard()
    sc.scores[Category.YAHTZEE] = 50
    with pytest.raises(ValueError):
        preview_score_for_category((6, 6, 6, 6, 6), Category.CHANCE, sc)
    res = preview_score_for_category((6, 6, 6, 6, 6), Category.SIXES, sc)
    assert res.score == 30
    assert res.yahtzee_bonus_awarded == 100


def test_yahtzee_50_matching_filled_lower_open_uses_joker_scores_and_bonus():
    sc = Scorecard()
    sc.scores[Category.YAHTZEE] = 50
    sc.scores[Category.SIXES] = 18

    res_fh = preview_score_for_category((6, 6, 6, 6, 6), Category.FULL_HOUSE, sc)
    assert res_fh.score == 25
    assert res_fh.yahtzee_bonus_awarded == 100
    assert res_fh.rule_metadata["applied_rule"] == "joker_lower"


def test_yahtzee_50_upper_fallback_non_matching_upper_scores_zero_with_bonus():
    sc = Scorecard()
    sc.scores[Category.YAHTZEE] = 50
    sc.scores[Category.SIXES] = 18
    for lower in [
        Category.THREE_KIND,
        Category.FOUR_KIND,
        Category.FULL_HOUSE,
        Category.SMALL_STRAIGHT,
        Category.LARGE_STRAIGHT,
        Category.CHANCE,
    ]:
        sc.scores[lower] = 0

    res_non_match = preview_score_for_category((6, 6, 6, 6, 6), Category.FIVES, sc)
    assert res_non_match.score == 0
    assert res_non_match.yahtzee_bonus_awarded == 100


def test_yahtzee_0_matching_upper_open_forced_no_bonus():
    sc = Scorecard()
    sc.scores[Category.YAHTZEE] = 0
    with pytest.raises(ValueError):
        preview_score_for_category((2, 2, 2, 2, 2), Category.CHANCE, sc)
    res = preview_score_for_category((2, 2, 2, 2, 2), Category.TWOS, sc)
    assert res.score == 10
    assert res.yahtzee_bonus_awarded == 0


def test_yahtzee_0_matching_filled_lower_open_joker_no_bonus():
    sc = Scorecard()
    sc.scores[Category.YAHTZEE] = 0
    sc.scores[Category.TWOS] = 6
    res = preview_score_for_category((2, 2, 2, 2, 2), Category.LARGE_STRAIGHT, sc)
    assert res.score == 40
    assert res.yahtzee_bonus_awarded == 0


def test_yahtzee_0_upper_fallback_non_matching_upper_zero_no_bonus():
    sc = Scorecard()
    sc.scores[Category.YAHTZEE] = 0
    sc.scores[Category.FOURS] = 12
    for lower in [
        Category.THREE_KIND,
        Category.FOUR_KIND,
        Category.FULL_HOUSE,
        Category.SMALL_STRAIGHT,
        Category.LARGE_STRAIGHT,
        Category.CHANCE,
    ]:
        sc.scores[lower] = 0
    res = preview_score_for_category((4, 4, 4, 4, 4), Category.ONES, sc)
    assert res.score == 0
    assert res.yahtzee_bonus_awarded == 0


def test_apply_score_to_scorecard_updates_score_and_bonus():
    sc = Scorecard()
    sc.scores[Category.YAHTZEE] = 50
    res = apply_score_to_scorecard((1, 1, 1, 1, 1), Category.ONES, sc)
    assert res.score == 5
    assert sc.scores[Category.ONES] == 5
    assert sc.yahtzee_bonus == 100


def test_back_compat_functions_still_work():
    sc = Scorecard()
    assert raw_category_score((2, 2, 3, 3, 3), Category.FULL_HOUSE) == 25
    score, yb = score_with_scorecard((2, 2, 3, 3, 3), Category.FULL_HOUSE, sc)
    assert (score, yb) == (25, 0)
