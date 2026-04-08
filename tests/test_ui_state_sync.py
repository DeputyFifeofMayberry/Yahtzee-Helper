from yahtzee.models import GameState
from yahtzee.state import GameManager
from yahtzee.ui_state import (
    ENTRY_MODE_COUNTS,
    ENTRY_MODE_QUICK,
    TURN_DRAFT_KEYS,
    TURN_ENTRY_MODE_KEY,
    TURN_FACE_COUNT_KEYS,
    TURN_QUICK_ENTRY_KEY,
    TURN_ROLL_KEY,
    commit_turn_draft_to_manager,
    seed_turn_draft_from_manager,
)


def test_initial_seed_populates_draft_keys_from_manager_state():
    manager = GameManager(GameState(current_dice=[1, 1, 1, 1, 6], roll_number=2))
    session_state: dict[str, int | str] = {}

    seed_turn_draft_from_manager(session_state, manager)

    for key in TURN_DRAFT_KEYS:
        assert key in session_state
    assert session_state[TURN_ENTRY_MODE_KEY] == ENTRY_MODE_QUICK
    assert session_state[TURN_QUICK_ENTRY_KEY] == "1 1 1 1 6"
    assert session_state[TURN_ROLL_KEY] == 2
    assert [session_state[key] for key in TURN_FACE_COUNT_KEYS] == [4, 0, 0, 0, 0, 1]


def test_non_force_seed_does_not_overwrite_user_draft_edits():
    manager = GameManager(GameState(current_dice=[1, 1, 1, 1, 1], roll_number=2))
    session_state: dict[str, int | str] = {}

    seed_turn_draft_from_manager(session_state, manager)
    session_state[TURN_ROLL_KEY] = 3
    session_state[TURN_QUICK_ENTRY_KEY] = "6 6 6 6 6"
    session_state[TURN_FACE_COUNT_KEYS[5]] = 5

    seed_turn_draft_from_manager(session_state, manager)

    assert session_state[TURN_ROLL_KEY] == 3
    assert session_state[TURN_QUICK_ENTRY_KEY] == "6 6 6 6 6"
    assert session_state[TURN_FACE_COUNT_KEYS[5]] == 5


def test_force_seed_overwrites_from_manager_state():
    manager = GameManager(GameState(current_dice=[2, 2, 2, 2, 2], roll_number=2))
    session_state: dict[str, int | str] = {
        TURN_ENTRY_MODE_KEY: ENTRY_MODE_COUNTS,
        TURN_QUICK_ENTRY_KEY: "6 6 6 6 6",
        TURN_ROLL_KEY: 3,
        **{key: 0 for key in TURN_FACE_COUNT_KEYS},
    }

    seed_turn_draft_from_manager(session_state, manager, force=True)

    assert session_state[TURN_ENTRY_MODE_KEY] == ENTRY_MODE_QUICK
    assert session_state[TURN_QUICK_ENTRY_KEY] == "2 2 2 2 2"
    assert session_state[TURN_ROLL_KEY] == 2
    assert [session_state[key] for key in TURN_FACE_COUNT_KEYS] == [0, 5, 0, 0, 0, 0]


def test_commit_writes_parsed_dice_and_roll_number_to_manager_state():
    manager = GameManager(GameState(current_dice=[1, 1, 1, 1, 1], roll_number=1))
    session_state = {
        TURN_ENTRY_MODE_KEY: ENTRY_MODE_QUICK,
        TURN_QUICK_ENTRY_KEY: "6 2 3 4 5",
        TURN_ROLL_KEY: 3,
        **{key: 0 for key in TURN_FACE_COUNT_KEYS},
    }

    commit_turn_draft_to_manager(session_state, manager)

    assert manager.state.current_dice == [2, 3, 4, 5, 6]
    assert manager.state.roll_number == 3


def test_quick_mode_commit_canonicalizes_through_manager():
    manager = GameManager(GameState(current_dice=[1, 1, 1, 1, 1], roll_number=1))
    session_state = {
        TURN_ENTRY_MODE_KEY: ENTRY_MODE_QUICK,
        TURN_QUICK_ENTRY_KEY: "65124",
        TURN_ROLL_KEY: 2,
        **{key: 0 for key in TURN_FACE_COUNT_KEYS},
    }

    commit_turn_draft_to_manager(session_state, manager)

    assert manager.state.current_dice == [1, 2, 4, 5, 6]
    assert manager.state.roll_number == 2


def test_face_count_mode_commit_works_correctly():
    manager = GameManager(GameState(current_dice=[1, 1, 1, 1, 1], roll_number=1))
    session_state = {
        TURN_ENTRY_MODE_KEY: ENTRY_MODE_COUNTS,
        TURN_QUICK_ENTRY_KEY: "",
        TURN_ROLL_KEY: 3,
        TURN_FACE_COUNT_KEYS[0]: 3,
        TURN_FACE_COUNT_KEYS[1]: 0,
        TURN_FACE_COUNT_KEYS[2]: 0,
        TURN_FACE_COUNT_KEYS[3]: 0,
        TURN_FACE_COUNT_KEYS[4]: 0,
        TURN_FACE_COUNT_KEYS[5]: 2,
    }

    commit_turn_draft_to_manager(session_state, manager)

    assert manager.state.current_dice == [1, 1, 1, 6, 6]
    assert manager.state.roll_number == 3
