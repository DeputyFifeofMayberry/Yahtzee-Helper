from __future__ import annotations

from yahtzee.input_parsing import dice_from_face_counts, face_counts_from_dice, parse_quick_dice_entry
from yahtzee.state import GameManager

TURN_ENTRY_MODE_KEY = "turn_entry_mode"
TURN_QUICK_ENTRY_KEY = "turn_quick_entry"
TURN_ROLL_KEY = "turn_roll_number"
TURN_FACE_COUNT_KEYS = [f"turn_face_count_{i}" for i in range(1, 7)]
TURN_DRAFT_KEYS = [TURN_ENTRY_MODE_KEY, TURN_QUICK_ENTRY_KEY, TURN_ROLL_KEY, *TURN_FACE_COUNT_KEYS]

ENTRY_MODE_QUICK = "Quick Entry"
ENTRY_MODE_COUNTS = "Face Counts"


def build_turn_draft_values(current_dice: list[int], roll_number: int) -> dict[str, int | str]:
    if len(current_dice) != 5:
        raise ValueError("current_dice must contain exactly 5 dice")
    counts = face_counts_from_dice(current_dice)
    return {
        TURN_ENTRY_MODE_KEY: ENTRY_MODE_QUICK,
        TURN_QUICK_ENTRY_KEY: " ".join(str(die) for die in current_dice),
        TURN_ROLL_KEY: int(roll_number),
        **{key: counts[i] for i, key in enumerate(TURN_FACE_COUNT_KEYS)},
    }


def seed_turn_draft_from_manager(session_state: dict, manager: GameManager, force: bool = False) -> None:
    values = build_turn_draft_values(manager.state.current_dice, manager.state.roll_number)
    if force:
        for key, value in values.items():
            session_state[key] = value
        return

    for key, value in values.items():
        session_state.setdefault(key, value)


def _read_roll_number(session_state: dict) -> int:
    try:
        roll_number = int(session_state.get(TURN_ROLL_KEY, 1))
    except (TypeError, ValueError) as exc:
        raise ValueError("Roll number must be 1, 2, or 3.") from exc
    if roll_number not in (1, 2, 3):
        raise ValueError("Roll number must be 1, 2, or 3.")
    return roll_number


def read_validated_turn_input(session_state: dict) -> tuple[list[int], int]:
    entry_mode = session_state.get(TURN_ENTRY_MODE_KEY, ENTRY_MODE_QUICK)
    if entry_mode == ENTRY_MODE_COUNTS:
        counts = []
        for key in TURN_FACE_COUNT_KEYS:
            value = session_state.get(key, 0)
            try:
                counts.append(int(value))
            except (TypeError, ValueError) as exc:
                raise ValueError("Face counts must be whole numbers.") from exc
        dice = dice_from_face_counts(counts)
    elif entry_mode == ENTRY_MODE_QUICK:
        dice = parse_quick_dice_entry(str(session_state.get(TURN_QUICK_ENTRY_KEY, "")))
    else:
        raise ValueError("Invalid entry mode.")

    roll_number = _read_roll_number(session_state)
    return dice, roll_number


def commit_turn_draft_to_manager(session_state: dict, manager: GameManager) -> None:
    dice, roll_number = read_validated_turn_input(session_state)
    manager.set_current_roll(dice, roll_number)


def sync_turn_draft_after_authoritative_change(session_state: dict, manager: GameManager) -> None:
    seed_turn_draft_from_manager(session_state, manager, force=True)
