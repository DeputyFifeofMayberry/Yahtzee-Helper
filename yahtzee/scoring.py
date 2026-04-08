from __future__ import annotations

from dataclasses import dataclass

from yahtzee.models import ALL_CATEGORIES, Category, LOWER_CATEGORIES, Scorecard, UPPER_CATEGORIES
from yahtzee.rules import (
    is_full_house,
    is_large_straight,
    is_n_of_a_kind,
    is_small_straight,
    is_yahtzee,
    legal_categories_for_roll,
    yahtzee_context,
)


@dataclass(frozen=True)
class ScoringResult:
    score: int
    yahtzee_bonus_awarded: int
    rule_metadata: dict[str, str | bool | int]


def ordinary_category_score(dice: tuple[int, ...] | list[int], category: Category) -> int:
    """Score category using ordinary (non-Joker override) semantics."""
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
        return total if is_n_of_a_kind(dice, 3) else 0
    if category == Category.FOUR_KIND:
        return total if is_n_of_a_kind(dice, 4) else 0
    if category == Category.FULL_HOUSE:
        return 25 if is_full_house(dice) else 0
    if category == Category.SMALL_STRAIGHT:
        return 30 if is_small_straight(dice) else 0
    if category == Category.LARGE_STRAIGHT:
        return 40 if is_large_straight(dice) else 0
    if category == Category.YAHTZEE:
        return 50 if is_yahtzee(dice) else 0
    if category == Category.CHANCE:
        return total
    raise ValueError(f"Unsupported category: {category}")


def joker_category_score(dice: tuple[int, ...] | list[int], category: Category) -> int:
    """Score category under Joker scoring semantics (lower section only)."""
    total = sum(dice)
    if category == Category.THREE_KIND:
        return total
    if category == Category.FOUR_KIND:
        return total
    if category == Category.FULL_HOUSE:
        return 25
    if category == Category.SMALL_STRAIGHT:
        return 30
    if category == Category.LARGE_STRAIGHT:
        return 40
    if category == Category.CHANCE:
        return total
    if category in UPPER_CATEGORIES:
        return ordinary_category_score(dice, category)
    if category == Category.YAHTZEE:
        return ordinary_category_score(dice, category)
    raise ValueError(f"Unsupported category for Joker scoring: {category}")


def preview_score_for_category(dice: tuple[int, ...] | list[int], category: Category, scorecard: Scorecard) -> ScoringResult:
    """Compute legal score application result without mutating scorecard."""
    if category not in ALL_CATEGORIES:
        raise ValueError(f"Unsupported category: {category}")
    if scorecard.is_filled(category):
        raise ValueError(f"Category already filled: {category.value}")

    legal_categories = legal_categories_for_roll(dice, scorecard)
    if category not in legal_categories:
        legal_names = ", ".join(c.value for c in legal_categories)
        raise ValueError(f"Illegal category for roll. Legal options: {legal_names}")

    context = yahtzee_context(dice, scorecard)

    score = ordinary_category_score(dice, category)
    applied_rule = "ordinary"

    if context.is_extra_yahtzee:
        if context.forced_upper_required:
            score = ordinary_category_score(dice, category)
            applied_rule = "joker_forced_upper"
        elif context.lower_joker_allowed:
            score = joker_category_score(dice, category)
            applied_rule = "joker_lower"
        elif context.upper_zero_fallback_required:
            if context.matching_upper_category == category:
                score = ordinary_category_score(dice, category)
            else:
                score = 0
            applied_rule = "joker_upper_fallback"

    return ScoringResult(
        score=score,
        yahtzee_bonus_awarded=context.bonus_awarded,
        rule_metadata={
            "is_yahtzee_roll": context.is_yahtzee_roll,
            "is_extra_yahtzee": context.is_extra_yahtzee,
            "applied_rule": applied_rule,
            "forced_upper_required": context.forced_upper_required,
            "lower_joker_allowed": context.lower_joker_allowed,
            "upper_zero_fallback_required": context.upper_zero_fallback_required,
        },
    )


def apply_score_to_scorecard(
    dice: tuple[int, ...] | list[int],
    category: Category,
    scorecard: Scorecard,
) -> ScoringResult:
    """Apply a legal score and any Yahtzee bonus to the provided scorecard."""
    result = preview_score_for_category(dice, category, scorecard)
    scorecard.scores[category] = result.score
    scorecard.yahtzee_bonus += result.yahtzee_bonus_awarded
    return result


# Backward-compatible aliases for existing imports.
def raw_category_score(dice: tuple[int, ...] | list[int], category: Category, joker_active: bool = False) -> int:
    return joker_category_score(dice, category) if joker_active else ordinary_category_score(dice, category)


def score_roll_in_category(dice: tuple[int, ...] | list[int], category: Category, scorecard: Scorecard) -> ScoringResult:
    return preview_score_for_category(dice, category, scorecard)


def score_with_scorecard(dice: tuple[int, ...] | list[int], category: Category, scorecard: Scorecard) -> tuple[int, int]:
    result = preview_score_for_category(dice, category, scorecard)
    return result.score, result.yahtzee_bonus_awarded
