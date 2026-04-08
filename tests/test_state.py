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
