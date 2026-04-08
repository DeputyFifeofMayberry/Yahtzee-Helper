from __future__ import annotations

from yahtzee.state import GameManager

TURN_DIE_KEYS = [f"turn_die_{i}" for i in range(1, 6)]
TURN_ROLL_KEY = "turn_roll_number"
TURN_WIDGET_KEYS = [*TURN_DIE_KEYS, TURN_ROLL_KEY]


def build_turn_widget_values(current_dice: list[int], roll_number: int) -> dict[str, int]:
    if len(current_dice) != 5:
        raise ValueError("current_dice must contain exactly 5 dice")
    return {
        TURN_DIE_KEYS[0]: int(current_dice[0]),
        TURN_DIE_KEYS[1]: int(current_dice[1]),
        TURN_DIE_KEYS[2]: int(current_dice[2]),
        TURN_DIE_KEYS[3]: int(current_dice[3]),
        TURN_DIE_KEYS[4]: int(current_dice[4]),
        TURN_ROLL_KEY: int(roll_number),
    }


def sync_turn_widgets_from_manager(session_state: dict[str, int], manager: GameManager, force: bool = False) -> None:
    values = build_turn_widget_values(manager.state.current_dice, manager.state.roll_number)
    needs_seed = force or any(key not in session_state for key in TURN_WIDGET_KEYS)
    if not needs_seed:
        return
    for key, value in values.items():
        session_state[key] = value


def commit_turn_widgets_to_manager(session_state: dict[str, int], manager: GameManager) -> None:
    dice = [int(session_state[key]) for key in TURN_DIE_KEYS]
    roll_number = int(session_state[TURN_ROLL_KEY])
    manager.set_current_roll(dice, roll_number)
