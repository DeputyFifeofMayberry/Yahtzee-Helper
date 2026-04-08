from yahtzee.models import GameState
from yahtzee.state import GameManager
from yahtzee.ui_state import (
    TURN_DIE_KEYS,
    TURN_ROLL_KEY,
    build_turn_widget_values,
    commit_turn_widgets_to_manager,
    sync_turn_widgets_from_manager,
)


def test_sync_only_seeds_missing_values_without_overwriting_user_edits():
    manager = GameManager(GameState(current_dice=[1, 1, 1, 1, 1], roll_number=2))
    session_state: dict[str, int] = {}

    sync_turn_widgets_from_manager(session_state, manager)
    assert session_state[TURN_ROLL_KEY] == 2

    session_state[TURN_ROLL_KEY] = 3
    session_state[TURN_DIE_KEYS[4]] = 6

    sync_turn_widgets_from_manager(session_state, manager)
    assert session_state[TURN_ROLL_KEY] == 3
    assert session_state[TURN_DIE_KEYS[4]] == 6


def test_commit_writes_widget_values_to_manager_state():
    manager = GameManager(GameState(current_dice=[1, 1, 1, 1, 1], roll_number=1))
    session_state = {
        TURN_DIE_KEYS[0]: 6,
        TURN_DIE_KEYS[1]: 2,
        TURN_DIE_KEYS[2]: 3,
        TURN_DIE_KEYS[3]: 4,
        TURN_DIE_KEYS[4]: 5,
        TURN_ROLL_KEY: 3,
    }

    commit_turn_widgets_to_manager(session_state, manager)
    assert manager.state.current_dice == [2, 3, 4, 5, 6]
    assert manager.state.roll_number == 3


def test_force_sync_replaces_widgets_after_authoritative_backend_change():
    manager = GameManager(GameState(current_dice=[2, 2, 2, 2, 2], roll_number=2))
    session_state = build_turn_widget_values([6, 6, 6, 6, 6], 3)

    sync_turn_widgets_from_manager(session_state, manager, force=True)

    assert [session_state[key] for key in TURN_DIE_KEYS] == [2, 2, 2, 2, 2]
    assert session_state[TURN_ROLL_KEY] == 2
