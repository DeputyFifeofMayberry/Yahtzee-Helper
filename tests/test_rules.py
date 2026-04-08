from yahtzee.models import Category, Scorecard
from yahtzee.rules import (
    is_full_house,
    is_large_straight,
    is_n_of_a_kind,
    is_small_straight,
    is_yahtzee,
    legal_categories_for_roll,
    matching_upper_category_for_yahtzee,
    yahtzee_context,
)


def test_pattern_detection_basics():
    assert is_yahtzee((6, 6, 6, 6, 6))
    assert is_n_of_a_kind((6, 6, 6, 2, 1), 3)
    assert not is_n_of_a_kind((6, 6, 2, 1, 3), 3)
    assert is_n_of_a_kind((4, 4, 4, 4, 2), 4)
    assert not is_n_of_a_kind((4, 4, 4, 2, 2), 4)


def test_full_house_and_straight_edges():
    assert is_full_house((2, 2, 3, 3, 3))
    assert not is_full_house((2, 2, 2, 2, 3))
    assert not is_full_house((1, 1, 1, 1, 1))
    assert is_small_straight((1, 2, 3, 4, 4))
    assert is_small_straight((2, 3, 3, 4, 5))
    assert not is_small_straight((1, 1, 2, 5, 6))
    assert is_large_straight((2, 3, 4, 5, 6))
    assert not is_large_straight((1, 2, 3, 4, 4))


def test_matching_upper_category_for_yahtzee():
    assert matching_upper_category_for_yahtzee((5, 5, 5, 5, 5)) == Category.FIVES


def test_ordinary_legal_categories_non_yahtzee_are_all_open():
    sc = Scorecard()
    sc.scores[Category.FULL_HOUSE] = 25
    legal = legal_categories_for_roll((1, 2, 3, 4, 6), sc)
    assert Category.FULL_HOUSE not in legal
    assert set(legal) == set(sc.open_categories())


def test_yahtzee_unfilled_uses_normal_category_legality():
    sc = Scorecard()
    legal = legal_categories_for_roll((6, 6, 6, 6, 6), sc)
    assert set(legal) == set(sc.open_categories())
    context = yahtzee_context((6, 6, 6, 6, 6), sc)
    assert context.is_extra_yahtzee is False
    assert context.bonus_awarded == 0


def test_extra_yahtzee_forced_upper_context_and_legality():
    sc = Scorecard()
    sc.scores[Category.YAHTZEE] = 50
    legal = legal_categories_for_roll((6, 6, 6, 6, 6), sc)
    assert legal == [Category.SIXES]

    context = yahtzee_context((6, 6, 6, 6, 6), sc)
    assert context.is_extra_yahtzee
    assert context.forced_upper_required
    assert context.bonus_awarded == 100


def test_extra_yahtzee_lower_joker_legality_and_context():
    sc = Scorecard()
    sc.scores[Category.YAHTZEE] = 50
    sc.scores[Category.SIXES] = 18
    legal = legal_categories_for_roll((6, 6, 6, 6, 6), sc)
    assert set(legal) == set(sc.open_lower_categories())

    context = yahtzee_context((6, 6, 6, 6, 6), sc)
    assert context.lower_joker_allowed
    assert not context.upper_zero_fallback_required


def test_extra_yahtzee_upper_fallback_legality():
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

    legal = legal_categories_for_roll((6, 6, 6, 6, 6), sc)
    assert set(legal) == set(sc.open_upper_categories())


def test_yahtzee_box_zero_still_uses_joker_legality_but_no_bonus():
    sc = Scorecard()
    sc.scores[Category.YAHTZEE] = 0
    legal = legal_categories_for_roll((4, 4, 4, 4, 4), sc)
    assert legal == [Category.FOURS]
    context = yahtzee_context((4, 4, 4, 4, 4), sc)
    assert context.is_extra_yahtzee
    assert context.bonus_awarded == 0
