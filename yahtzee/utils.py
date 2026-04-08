from __future__ import annotations

from collections import Counter
from itertools import combinations


def validate_dice(dice: list[int] | tuple[int, ...]) -> None:
    if len(dice) != 5:
        raise ValueError("Exactly 5 dice are required.")
    if any(d < 1 or d > 6 for d in dice):
        raise ValueError("Dice values must be between 1 and 6.")


def canonical_dice(dice: list[int] | tuple[int, ...]) -> tuple[int, ...]:
    validate_dice(dice)
    return tuple(sorted(dice))


def dice_counts(dice: list[int] | tuple[int, ...]) -> Counter[int]:
    validate_dice(dice)
    return Counter(dice)


def distinct_holds(dice: list[int] | tuple[int, ...]) -> list[tuple[int, ...]]:
    """Return all unique holds (multiset-aware) from a 5-dice roll."""
    d = tuple(dice)
    validate_dice(d)
    holds: set[tuple[int, ...]] = set()
    for k in range(6):
        for idxs in combinations(range(5), k):
            held = tuple(sorted(d[i] for i in idxs))
            holds.add(held)
    return sorted(holds)
