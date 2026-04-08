from __future__ import annotations

from dataclasses import dataclass

from yahtzee.models import ALL_CATEGORIES, Category, LOWER_CATEGORIES, Scorecard, UPPER_CATEGORIES
from yahtzee.rules import is_full_house, is_large_straight, is_n_of_a_kind, is_small_straight, is_yahtzee


@dataclass(frozen=True)
class ScoringResult:
    score: int
    yahtzee_bonus_awarded: int
    joker_active: bool


def raw_category_score(dice: tuple[int, ...] | list[int], category: Category, joker_active: bool = False) -> int:
    total = sum(dice)
    if category == Category.ONES:
        return sum(d for d in dice if d == 1)
    if category == Category.TWOS:
        return sum(d for d in dice if d == 2)
    if category == Category.THREES:
        return sum(d for d in dice if d == 3)
    if category == Category.FOURS:
        return sum(d for d in dice if d == 4)
    if category == Category.FIVES:
        return sum(d for d in dice if d == 5)
    if category == Category.SIXES:
        return sum(d for d in dice if d == 6)
    if category == Category.THREE_KIND:
        return total if is_n_of_a_kind(dice, 3) or joker_active else 0
    if category == Category.FOUR_KIND:
        return total if is_n_of_a_kind(dice, 4) or joker_active else 0
    if category == Category.FULL_HOUSE:
        return 25 if is_full_house(dice) or joker_active else 0
    if category == Category.SMALL_STRAIGHT:
        return 30 if is_small_straight(dice) or joker_active else 0
    if category == Category.LARGE_STRAIGHT:
        return 40 if is_large_straight(dice) or joker_active else 0
    if category == Category.YAHTZEE:
        return 50 if is_yahtzee(dice) else 0
    if category == Category.CHANCE:
        return total
    raise ValueError(f"Unsupported category: {category}")


def joker_forced_upper_category(dice: tuple[int, ...] | list[int]) -> Category:
    pip = dice[0]
    return UPPER_CATEGORIES[pip - 1]


def legal_categories_for_roll(dice: tuple[int, ...] | list[int], scorecard: Scorecard) -> list[Category]:
    """Return legal categories for this final roll under standard Yahtzee + Joker rule.

    Behavior implemented:
    - Yahtzee box not scored 50 yet (open or 0): no extra Yahtzee bonus/Joker override.
      Any open category is legal.
    - Extra Yahtzee when Yahtzee box is 50:
      * matching upper box open => forced to that upper category.
      * matching upper closed => may score in any open lower category using Joker semantics;
        if all lower categories are filled, any open upper category is legal.
    """
    open_categories = scorecard.open_categories()
    if not is_yahtzee(dice):
        return open_categories

    yahtzee_box = scorecard.scores[Category.YAHTZEE]
    if yahtzee_box != 50:
        return open_categories

    forced_upper = joker_forced_upper_category(dice)
    if not scorecard.is_filled(forced_upper):
        return [forced_upper]

    open_lower = [c for c in LOWER_CATEGORIES if not scorecard.is_filled(c)]
    if open_lower:
        return open_lower

    return [c for c in UPPER_CATEGORIES if not scorecard.is_filled(c)]


def score_roll_in_category(dice: tuple[int, ...] | list[int], category: Category, scorecard: Scorecard) -> ScoringResult:
    if category not in ALL_CATEGORIES:
        raise ValueError(f"Unsupported category: {category}")
    if scorecard.is_filled(category):
        raise ValueError(f"Category already filled: {category.value}")

    legal_categories = legal_categories_for_roll(dice, scorecard)
    if category not in legal_categories:
        legal_names = ", ".join(c.value for c in legal_categories)
        raise ValueError(f"Illegal category for roll. Legal options: {legal_names}")

    yahtzee_bonus = 100 if is_yahtzee(dice) and scorecard.scores[Category.YAHTZEE] == 50 else 0
    forced_upper = joker_forced_upper_category(dice) if is_yahtzee(dice) else None
    joker_active = (
        yahtzee_bonus > 0
        and forced_upper is not None
        and scorecard.is_filled(forced_upper)
        and category in LOWER_CATEGORIES
    )

    return ScoringResult(
        score=raw_category_score(dice, category, joker_active=joker_active),
        yahtzee_bonus_awarded=yahtzee_bonus,
        joker_active=joker_active,
    )


# Backward-compatible aliases for existing imports.
def category_score(dice: tuple[int, ...] | list[int], category: Category, joker_active: bool = False) -> int:
    return raw_category_score(dice, category, joker_active=joker_active)


def score_with_scorecard(dice: tuple[int, ...] | list[int], category: Category, scorecard: Scorecard) -> tuple[int, int]:
    result = score_roll_in_category(dice, category, scorecard)
    return result.score, result.yahtzee_bonus_awarded
