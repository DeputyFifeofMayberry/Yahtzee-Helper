from __future__ import annotations

from copy import deepcopy

from yahtzee.models import Category, GameState, TurnRecord
from yahtzee.scoring import score_roll_in_category
from yahtzee.utils import canonical_dice


class GameManager:
    def __init__(self, state: GameState | None = None):
        self.state = state or GameState()
        self._undo_stack: list[GameState] = []

    def set_current_roll(self, dice: list[int], roll_number: int) -> None:
        self.state.current_dice = list(canonical_dice(dice))
        if roll_number < 1 or roll_number > 3:
            raise ValueError("roll_number must be 1..3")
        self.state.roll_number = roll_number

    def apply_score(self, category: Category) -> int:
        if self.state.scorecard.is_filled(category):
            raise ValueError(f"Category already filled: {category.value}")
        self._undo_stack.append(deepcopy(self.state))
        result = score_roll_in_category(self.state.current_dice, category, self.state.scorecard)
        self.state.scorecard.scores[category] = result.score
        self.state.scorecard.yahtzee_bonus += result.yahtzee_bonus_awarded
        score = result.score
        self.state.history.append(
            TurnRecord(
                dice=list(self.state.current_dice),
                roll_number=self.state.roll_number,
                action="SCORE",
                category_scored=category,
                score_awarded=score,
            )
        )
        self.state.turn_index += 1
        self.state.roll_number = 1
        self.state.current_dice = [1, 1, 1, 1, 1]
        return score

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        self.state = self._undo_stack.pop()
        return True

    def reset_current_turn(self) -> None:
        self.state.current_dice = [1, 1, 1, 1, 1]
        self.state.roll_number = 1
