from __future__ import annotations

from dataclasses import dataclass, field

from yahtzee.models import ActionType, Category


@dataclass(frozen=True)
class PolicyDecision:
    action_type: ActionType
    held_dice: tuple[int, ...] | None = None
    category: Category | None = None
    description: str = ""

    @property
    def is_hold(self) -> bool:
        return self.action_type == ActionType.HOLD_AND_REROLL

    @property
    def is_score(self) -> bool:
        return self.action_type == ActionType.SCORE_NOW


@dataclass(frozen=True)
class DecisionStateSnapshot:
    score_signature: tuple[tuple[int | None, ...], int]
    dice: tuple[int, ...]
    roll_number: int
    turn_index: int
    tags: tuple[str, ...] = ()


@dataclass
class GameSimulationResult:
    policy_name: str
    seed: int
    final_score: int
    upper_bonus_hit: bool
    upper_subtotal: int
    yahtzee_scored: bool
    yahtzee_bonus_count: int
    category_scores: dict[str, int | None]
    zeroed_categories: tuple[str, ...]
    sampled_states: list[DecisionStateSnapshot] = field(default_factory=list)


@dataclass(frozen=True)
class OracleComparisonRecord:
    policy_name: str
    matched_oracle: bool
    regret: float
    turn_index: int
    roll_number: int
    tags: tuple[str, ...] = ()
