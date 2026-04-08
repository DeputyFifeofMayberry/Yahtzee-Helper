from __future__ import annotations

import re
from collections.abc import Mapping


def parse_quick_dice_entry(raw: str) -> list[int]:
    text = str(raw or "").strip()
    if not text:
        raise ValueError("Enter exactly 5 dice values.")

    if not re.fullmatch(r"[\d\s,]+", text):
        raise ValueError("Use only digits, spaces, or commas.")

    compact = text.replace(" ", "").replace(",", "")
    if compact.isdigit() and len(compact) == 5:
        dice = [int(ch) for ch in compact]
    else:
        normalized = re.sub(r"\s*,\s*", " ", text)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        tokens = normalized.split(" ") if normalized else []
        if len(tokens) != 5:
            raise ValueError("Enter exactly 5 dice values.")
        dice = [int(token) for token in tokens]

    if len(dice) != 5:
        raise ValueError("Enter exactly 5 dice values.")
    if any(die < 1 or die > 6 for die in dice):
        raise ValueError("Dice values must be between 1 and 6.")
    return dice


def _validate_count(value: int, *, allow_zero: bool = True) -> int:
    if not isinstance(value, int):
        raise ValueError("Face counts must be whole numbers.")
    if value < 0 or (not allow_zero and value == 0):
        raise ValueError("Face counts must be non-negative integers.")
    return value


def dice_from_face_counts(counts: list[int] | dict[int, int]) -> list[int]:
    if isinstance(counts, Mapping):
        expected_keys = set(range(1, 7))
        if set(counts.keys()) != expected_keys:
            raise ValueError("Face count keys must be 1 through 6.")
        ordered_counts = [_validate_count(counts[face]) for face in range(1, 7)]
    else:
        if len(counts) != 6:
            raise ValueError("Provide exactly 6 face counts.")
        ordered_counts = [_validate_count(value) for value in counts]

    total = sum(ordered_counts)
    if total != 5:
        raise ValueError("Face counts must total exactly 5 dice.")

    dice: list[int] = []
    for face, count in enumerate(ordered_counts, start=1):
        dice.extend([face] * count)
    return dice


def face_counts_from_dice(dice: list[int]) -> list[int]:
    if len(dice) != 5:
        raise ValueError("Dice must contain exactly 5 values.")
    counts = [0] * 6
    for die in dice:
        if not isinstance(die, int) or die < 1 or die > 6:
            raise ValueError("Dice values must be between 1 and 6.")
        counts[die - 1] += 1
    return counts
