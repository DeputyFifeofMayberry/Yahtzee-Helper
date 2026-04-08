from pathlib import Path

from yahtzee.models import Category, GameState
from yahtzee.persistence import load_game, save_game
from yahtzee.state import GameManager


def test_apply_and_undo():
    m = GameManager(GameState())
    m.set_current_roll([2, 2, 3, 3, 3], 3)
    score = m.apply_score(Category.FULL_HOUSE)
    assert score == 25
    assert m.state.scorecard.scores[Category.FULL_HOUSE] == 25
    assert m.undo()
    assert m.state.scorecard.scores[Category.FULL_HOUSE] is None


def test_save_load(tmp_path: Path):
    p = tmp_path / "g.json"
    m = GameManager(GameState())
    m.set_current_roll([1, 1, 1, 1, 1], 3)
    m.apply_score(Category.YAHTZEE)
    save_game(m.state, str(p))
    loaded = load_game(str(p))
    assert loaded.scorecard.scores[Category.YAHTZEE] == 50


def test_backward_compatible_load_missing_new_fields(tmp_path: Path):
    p = tmp_path / "legacy.json"
    p.write_text(
        '{"scorecard":{"scores":{"Yahtzee":50}},"turn_index":2,"current_dice":[1,1,1,1,1],"roll_number":1,"history":[]}',
        encoding="utf-8",
    )
    loaded = load_game(str(p))
    assert loaded.turn_index == 2
    assert loaded.scorecard.scores[Category.YAHTZEE] == 50
    assert loaded.scorecard.yahtzee_bonus == 0


def test_save_load_preserves_current_visible_dice_order(tmp_path: Path):
    p = tmp_path / "visible-order.json"
    m = GameManager(GameState())
    m.set_current_roll([5, 4, 2, 4, 1], 2)
    save_game(m.state, str(p))

    loaded = load_game(str(p))
    assert loaded.current_dice == [5, 4, 2, 4, 1]
    assert loaded.roll_number == 2


def test_undo_restores_current_visible_dice_order():
    m = GameManager(GameState())
    m.set_current_roll([5, 4, 2, 4, 1], 3)
    m.apply_score(Category.CHANCE)

    assert m.undo()
    assert m.state.current_dice == [5, 4, 2, 4, 1]
    assert m.state.roll_number == 3
