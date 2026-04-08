from __future__ import annotations

from collections import Counter
from functools import lru_cache
from itertools import product

from yahtzee.models import Category
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


def final_outcome_distribution(held: tuple[int, ...], rerolls_left: int) -> dict[tuple[int, ...], float]:
    if rerolls_left == 0:
        return {tuple(sorted(held)): 1.0}
    missing = 5 - len(held)
    dist = reroll_distribution(missing)
    if rerolls_left == 1:
        return {tuple(sorted(held + outcome)): p for outcome, p in dist.items()}
    # Only used for probability reporting, not optimal decision chaining.
    merged: Counter[tuple[int, ...]] = Counter()
    for outcome, p in dist.items():
        dice = tuple(sorted(held + outcome))
        merged[dice] += p
    return dict(merged)


def category_probability(dist: dict[tuple[int, ...], float], category: Category) -> float:
    total = 0.0
    for dice, p in dist.items():
        if category == Category.YAHTZEE and is_yahtzee(dice):
            total += p
        elif category == Category.FULL_HOUSE and is_full_house(dice):
            total += p
        elif category == Category.SMALL_STRAIGHT and is_small_straight(dice):
            total += p
        elif category == Category.LARGE_STRAIGHT and is_large_straight(dice):
            total += p
        elif category == Category.THREE_KIND and is_n_of_a_kind(dice, 3):
            total += p
        elif category == Category.FOUR_KIND and is_n_of_a_kind(dice, 4):
            total += p
    return total
