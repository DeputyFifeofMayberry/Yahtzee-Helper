from __future__ import annotations

from collections import Counter


def is_yahtzee(dice: tuple[int, ...] | list[int]) -> bool:
    return len(set(dice)) == 1


def is_n_of_a_kind(dice: tuple[int, ...] | list[int], n: int) -> bool:
    return max(Counter(dice).values()) >= n


def is_full_house(dice: tuple[int, ...] | list[int]) -> bool:
    c = sorted(Counter(dice).values())
    return c == [2, 3]


def is_small_straight(dice: tuple[int, ...] | list[int]) -> bool:
    s = set(dice)
    runs = [
        {1, 2, 3, 4},
        {2, 3, 4, 5},
        {3, 4, 5, 6},
    ]
    return any(run.issubset(s) for run in runs)


def is_large_straight(dice: tuple[int, ...] | list[int]) -> bool:
    s = set(dice)
    return s == {1, 2, 3, 4, 5} or s == {2, 3, 4, 5, 6}
