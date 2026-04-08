from __future__ import annotations

from yahtzee.models import Category, Scorecard, UPPER_CATEGORIES
from yahtzee.rules import is_full_house, is_large_straight, is_n_of_a_kind, is_small_straight, is_yahtzee


def category_score(dice: tuple[int, ...] | list[int], category: Category, joker_active: bool = False) -> int:
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


def score_with_scorecard(dice: tuple[int, ...] | list[int], category: Category, scorecard: Scorecard) -> tuple[int, int]:
    """Return (score, yahtzee_bonus_awarded)."""
    yahtzee = is_yahtzee(dice)
    yahtzee_box = scorecard.scores[Category.YAHTZEE]
    yahtzee_bonus = 0

    joker_active = False
    if yahtzee and yahtzee_box == 50:
        yahtzee_bonus = 100
        forced_upper = joker_forced_upper_category(dice)
        if scorecard.scores[forced_upper] is None and category != forced_upper:
            raise ValueError(f"Joker rule: must score in {forced_upper.value} while open.")
        joker_active = category not in UPPER_CATEGORIES

    score = category_score(dice, category, joker_active=joker_active)
    return score, yahtzee_bonus
