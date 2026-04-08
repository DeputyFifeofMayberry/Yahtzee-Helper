from __future__ import annotations

from collections import Counter
from functools import lru_cache
from itertools import product

from yahtzee.rules import is_full_house, is_large_straight, is_n_of_a_kind, is_small_straight, is_yahtzee


@lru_cache(maxsize=None)
def reroll_distribution(num_dice: int) -> dict[tuple[int, ...], float]:
    if num_dice < 0 or num_dice > 5:
        raise ValueError("num_dice must be between 0 and 5")
    if num_dice == 0:
        return {(): 1.0}
    outcomes = Counter(tuple(sorted(o)) for o in product(range(1, 7), repeat=num_dice))
    total = 6**num_dice
    return {k: v / total for k, v in outcomes.items()}


def classify_final_dice(dice: tuple[int, ...]) -> str:
    """Mutually exclusive end-of-turn outcome class for probability reporting."""
    if is_yahtzee(dice):
        return "Yahtzee"
    if is_large_straight(dice):
        return "Large Straight"
    if is_full_house(dice):
        return "Full House"
    if is_n_of_a_kind(dice, 4):
        return "Four of a Kind"
    if is_small_straight(dice):
        return "Small Straight"
    if is_n_of_a_kind(dice, 3):
        return "Three of a Kind"
    return "Other"


def outcome_class_distribution(final_dice_dist: dict[tuple[int, ...], float]) -> dict[str, float]:
    classes = [
        "Yahtzee",
        "Large Straight",
        "Full House",
        "Four of a Kind",
        "Small Straight",
        "Three of a Kind",
        "Other",
    ]
    totals = {key: 0.0 for key in classes}
    for dice, probability in final_dice_dist.items():
        totals[classify_final_dice(dice)] += probability
    return totals
