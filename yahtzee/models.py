from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Category(str, Enum):
    ONES = "Ones"
    TWOS = "Twos"
    THREES = "Threes"
    FOURS = "Fours"
    FIVES = "Fives"
    SIXES = "Sixes"
    THREE_KIND = "Three of a Kind"
    FOUR_KIND = "Four of a Kind"
    FULL_HOUSE = "Full House"
    SMALL_STRAIGHT = "Small Straight"
    LARGE_STRAIGHT = "Large Straight"
    YAHTZEE = "Yahtzee"
    CHANCE = "Chance"


UPPER_CATEGORIES = [
    Category.ONES,
    Category.TWOS,
    Category.THREES,
    Category.FOURS,
    Category.FIVES,
    Category.SIXES,
]

LOWER_CATEGORIES = [
    Category.THREE_KIND,
    Category.FOUR_KIND,
    Category.FULL_HOUSE,
    Category.SMALL_STRAIGHT,
    Category.LARGE_STRAIGHT,
    Category.YAHTZEE,
    Category.CHANCE,
]

ALL_CATEGORIES = UPPER_CATEGORIES + LOWER_CATEGORIES


class ActionType(str, Enum):
    HOLD_AND_REROLL = "HOLD_AND_REROLL"
    SCORE_NOW = "SCORE_NOW"


class OptimizationObjective(str, Enum):
    BOARD_UTILITY = "BOARD_UTILITY"
    EXACT_TURN_EV = "EXACT_TURN_EV"
    MAXIMIZE_YAHTZEE_PROBABILITY = "MAXIMIZE_YAHTZEE_PROBABILITY"


@dataclass
class Scorecard:
    scores: dict[Category, int | None] = field(default_factory=lambda: {c: None for c in ALL_CATEGORIES})
    yahtzee_bonus: int = 0

    def is_filled(self, category: Category) -> bool:
        return self.scores[category] is not None

    def open_categories(self) -> list[Category]:
        return [c for c in ALL_CATEGORIES if self.scores[c] is None]

    def filled_categories(self) -> list[Category]:
        return [c for c in ALL_CATEGORIES if self.scores[c] is not None]

    @property
    def is_complete(self) -> bool:
        return len(self.filled_categories()) == len(ALL_CATEGORIES)

    def open_upper_categories(self) -> list[Category]:
        return [c for c in UPPER_CATEGORIES if self.scores[c] is None]

    def open_lower_categories(self) -> list[Category]:
        return [c for c in LOWER_CATEGORIES if self.scores[c] is None]

    def filled_categories_signature(self) -> tuple[str, ...]:
        return tuple(c.value for c in self.filled_categories())

    def score_signature(self) -> tuple[tuple[int | None, ...], int]:
        """Canonical exact board-state signature for advisory caching.

        Includes each category score/unfilled state in fixed order and the
        accumulated Yahtzee bonus, so materially different boards never collide.
        """
        return tuple(self.scores[c] for c in ALL_CATEGORIES), self.yahtzee_bonus

    @classmethod
    def from_signature(cls, signature: tuple[tuple[int | None, ...], int]) -> "Scorecard":
        values, yahtzee_bonus = signature
        if len(values) != len(ALL_CATEGORIES):
            raise ValueError("Invalid scorecard signature length")
        card = cls()
        for cat, value in zip(ALL_CATEGORIES, values, strict=True):
            card.scores[cat] = value
        card.yahtzee_bonus = int(yahtzee_bonus)
        return card

    def legal_scoring_categories(self, dice: tuple[int, ...] | list[int]) -> list[Category]:
        from yahtzee.rules import legal_categories_for_roll

        return legal_categories_for_roll(dice, self)

    def legal_score_previews(self, dice: tuple[int, ...] | list[int]) -> dict[Category, int]:
        from yahtzee.scoring import score_roll_in_category

        return {cat: score_roll_in_category(dice, cat, self).score for cat in self.legal_scoring_categories(dice)}

    @property
    def upper_subtotal(self) -> int:
        return sum(self.scores[c] or 0 for c in UPPER_CATEGORIES)

    @property
    def upper_bonus(self) -> int:
        return 35 if self.upper_subtotal >= 63 else 0

    @property
    def lower_subtotal(self) -> int:
        return sum(self.scores[c] or 0 for c in LOWER_CATEGORIES) + self.yahtzee_bonus

    @property
    def grand_total(self) -> int:
        return self.upper_subtotal + self.upper_bonus + self.lower_subtotal

    def to_dict(self) -> dict[str, Any]:
        return {
            "scores": {c.value: self.scores[c] for c in ALL_CATEGORIES},
            "yahtzee_bonus": self.yahtzee_bonus,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Scorecard":
        card = cls()
        for c in ALL_CATEGORIES:
            card.scores[c] = payload.get("scores", {}).get(c.value)
        card.yahtzee_bonus = int(payload.get("yahtzee_bonus", 0))
        return card


@dataclass
class TurnRecord:
    dice: list[int]
    roll_number: int
    action: str
    category_scored: Category | None
    score_awarded: int | None


@dataclass
class GameState:
    scorecard: Scorecard = field(default_factory=Scorecard)
    turn_index: int = 1
    # Display-order dice for the active turn (preserves user-entered order).
    current_dice: list[int] = field(default_factory=lambda: [1, 1, 1, 1, 1])
    roll_number: int = 1
    history: list[TurnRecord] = field(default_factory=list)

    @property
    def is_game_over(self) -> bool:
        return self.scorecard.is_complete

    def to_dict(self) -> dict[str, Any]:
        return {
            "scorecard": self.scorecard.to_dict(),
            "turn_index": self.turn_index,
            "current_dice": self.current_dice,
            "roll_number": self.roll_number,
            "history": [
                {
                    "dice": h.dice,
                    "roll_number": h.roll_number,
                    "action": h.action,
                    "category_scored": h.category_scored.value if h.category_scored else None,
                    "score_awarded": h.score_awarded,
                }
                for h in self.history
            ],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GameState":
        history = [
            TurnRecord(
                dice=r["dice"],
                roll_number=r["roll_number"],
                action=r["action"],
                category_scored=Category(r["category_scored"]) if r["category_scored"] else None,
                score_awarded=r["score_awarded"],
            )
            for r in payload.get("history", [])
        ]
        return cls(
            scorecard=Scorecard.from_dict(payload.get("scorecard", {})),
            turn_index=int(payload.get("turn_index", 1)),
            current_dice=list(payload.get("current_dice", [1, 1, 1, 1, 1])),
            roll_number=int(payload.get("roll_number", 1)),
            history=history,
        )


@dataclass
class CandidateAction:
    action_type: ActionType
    held_dice: tuple[int, ...] | None = None
    category: Category | None = None
    expected_value: float = 0.0
    exact_turn_ev: float = 0.0
    board_adjustment: float = 0.0
    description: str = ""
    probabilities: dict[str, float] = field(default_factory=dict)
    yahtzee_probability: float = 0.0


@dataclass
class Recommendation:
    best_action: CandidateAction
    top_actions: list[CandidateAction]
    best_stop_category: Category
    best_stop_score: int
    explanation: str
    objective: OptimizationObjective
    recommended_line_yahtzee_probability: float
    max_yahtzee_probability: float
