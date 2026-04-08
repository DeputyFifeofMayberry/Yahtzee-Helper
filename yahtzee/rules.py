from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from yahtzee.models import Category, LOWER_CATEGORIES, Scorecard, UPPER_CATEGORIES


@dataclass(frozen=True)
class YahtzeeContext:
    """Rule context for a resolved final roll.

    This centralizes whether Joker restrictions apply, which categories are legal,
    and whether a Yahtzee bonus should be awarded.
    """

    is_yahtzee_roll: bool
    is_extra_yahtzee: bool
    bonus_awarded: int
    matching_upper_category: Category | None
    forced_upper_required: bool
    lower_joker_allowed: bool
    upper_zero_fallback_required: bool


def is_yahtzee(dice: tuple[int, ...] | list[int]) -> bool:
    return len(set(dice)) == 1


def is_n_of_a_kind(dice: tuple[int, ...] | list[int], n: int) -> bool:
    return max(Counter(dice).values()) >= n


def is_full_house(dice: tuple[int, ...] | list[int]) -> bool:
    c = sorted(Counter(dice).values())
    return c == [2, 3]


def is_small_straight(dice: tuple[int, ...] | list[int]) -> bool:
    s = set(dice)
    return any(run.issubset(s) for run in ({1, 2, 3, 4}, {2, 3, 4, 5}, {3, 4, 5, 6}))


def is_large_straight(dice: tuple[int, ...] | list[int]) -> bool:
    s = set(dice)
    return s == {1, 2, 3, 4, 5} or s == {2, 3, 4, 5, 6}


def matching_upper_category_for_yahtzee(dice: tuple[int, ...] | list[int]) -> Category:
    """Return the upper section category that matches a Yahtzee pip value."""
    if not is_yahtzee(dice):
        raise ValueError("Matching upper category only exists for Yahtzee rolls")
    return UPPER_CATEGORIES[dice[0] - 1]


def yahtzee_context(dice: tuple[int, ...] | list[int], scorecard: Scorecard) -> YahtzeeContext:
    """Classify the roll under official Yahtzee/Joker behavior.

    If Yahtzee box is filled (50 or 0), additional Yahtzees use Joker placement
    restrictions; +100 bonus is awarded only when the Yahtzee box is 50.
    """
    if not is_yahtzee(dice):
        return YahtzeeContext(False, False, 0, None, False, False, False)

    yahtzee_box = scorecard.scores[Category.YAHTZEE]
    if yahtzee_box is None:
        return YahtzeeContext(True, False, 0, matching_upper_category_for_yahtzee(dice), False, False, False)

    matching_upper = matching_upper_category_for_yahtzee(dice)
    forced_upper = not scorecard.is_filled(matching_upper)
    if forced_upper:
        return YahtzeeContext(True, True, 100 if yahtzee_box == 50 else 0, matching_upper, True, False, False)

    open_lower = [cat for cat in LOWER_CATEGORIES if not scorecard.is_filled(cat)]
    if open_lower:
        return YahtzeeContext(True, True, 100 if yahtzee_box == 50 else 0, matching_upper, False, True, False)

    return YahtzeeContext(True, True, 100 if yahtzee_box == 50 else 0, matching_upper, False, False, True)


def legal_categories_for_roll(dice: tuple[int, ...] | list[int], scorecard: Scorecard) -> list[Category]:
    """Return exact legal score categories for this final roll and scorecard."""
    open_categories = scorecard.open_categories()
    context = yahtzee_context(dice, scorecard)
    if not context.is_extra_yahtzee:
        return open_categories

    if context.forced_upper_required:
        if context.matching_upper_category is None:
            raise ValueError("Invalid Joker context: missing matching upper category")
        return [context.matching_upper_category]

    if context.lower_joker_allowed:
        return scorecard.open_lower_categories()

    if context.upper_zero_fallback_required:
        return scorecard.open_upper_categories()

    return open_categories
