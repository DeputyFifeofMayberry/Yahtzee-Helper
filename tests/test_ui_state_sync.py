from yahtzee.models import GameState
from yahtzee.state import GameManager
from yahtzee.ui_state import (
    ENTRY_MODE_COUNTS,
    ENTRY_MODE_QUICK,
    TURN_DRAFT_KEYS,
    TURN_DRAFT_PENDING_SYNC_KEY,
    TURN_DRAFT_SYNC_REQUESTED_KEY,
    TURN_ENTRY_MODE_KEY,
    TURN_FACE_COUNT_KEYS,
    TURN_QUICK_ENTRY_KEY,
    TURN_ROLL_KEY,
    build_hold_mask_for_current_dice,
    commit_turn_draft_to_manager,
    consume_pending_turn_draft_sync,
    request_turn_draft_sync_from_manager,
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


def test_deferred_sync_requests_and_consumes_widget_values():
    manager = GameManager(GameState(current_dice=[2, 3, 4, 5, 6], roll_number=3))
    session_state: dict[str, int | str | dict[str, int | str] | bool] = {}
    seed_turn_draft_from_manager(session_state, GameManager(GameState(current_dice=[1, 1, 1, 1, 1], roll_number=1)))

    request_turn_draft_sync_from_manager(session_state, manager)

    assert session_state[TURN_DRAFT_SYNC_REQUESTED_KEY] is True
    assert TURN_DRAFT_PENDING_SYNC_KEY in session_state

    consume_pending_turn_draft_sync(session_state)

    assert session_state[TURN_ROLL_KEY] == 3
    assert session_state[TURN_QUICK_ENTRY_KEY] == "2 3 4 5 6"
    assert session_state[TURN_DRAFT_SYNC_REQUESTED_KEY] is False
    assert TURN_DRAFT_PENDING_SYNC_KEY not in session_state


def test_build_hold_mask_is_duplicate_safe():
    mask = build_hold_mask_for_current_dice([1, 1, 1, 1, 6], (1, 1, 1, 1))
    assert mask == [True, True, True, True, False]


def test_build_hold_mask_requires_subset():
    try:
        build_hold_mask_for_current_dice([1, 1, 2, 3, 4], (1, 1, 1))
    except ValueError as exc:
        assert "subset" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid held dice")


def test_commit_writes_parsed_dice_and_roll_number_to_manager_state():
    manager = GameManager(GameState(current_dice=[1, 1, 1, 1, 1], roll_number=1))
    session_state = {
        TURN_ENTRY_MODE_KEY: ENTRY_MODE_QUICK,
        TURN_QUICK_ENTRY_KEY: "6 2 3 4 5",
        TURN_ROLL_KEY: 3,
        **{key: 0 for key in TURN_FACE_COUNT_KEYS},
    }

    commit_turn_draft_to_manager(session_state, manager)

    assert manager.state.current_dice == [6, 2, 3, 4, 5]
    assert manager.state.roll_number == 3


def test_quick_mode_commit_preserves_user_entered_die_order():
    manager = GameManager(GameState(current_dice=[1, 1, 1, 1, 1], roll_number=1))
    session_state = {
        TURN_ENTRY_MODE_KEY: ENTRY_MODE_QUICK,
        TURN_QUICK_ENTRY_KEY: "54241",
        TURN_ROLL_KEY: 2,
        **{key: 0 for key in TURN_FACE_COUNT_KEYS},
    }

    commit_turn_draft_to_manager(session_state, manager)

    assert manager.state.current_dice == [5, 4, 2, 4, 1]
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


def test_build_hold_mask_maps_held_duplicates_to_visible_order():
    mask = build_hold_mask_for_current_dice([5, 4, 2, 4, 1], (1, 4, 4))
    assert mask == [False, True, False, True, True]
