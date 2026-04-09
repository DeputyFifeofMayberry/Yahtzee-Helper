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
    snapshot_id: str
    score_signature: tuple[tuple[int | None, ...], int]
    dice: tuple[int, ...]
    roll_number: int
    turn_index: int
    provenance_source: str
    provenance_seed: int
    provenance_game_id: int
    provenance_policy: str
    tags: tuple[str, ...] = ()


@dataclass
class GameSimulationResult:
    policy_name: str
    seed: int
    game_id: int
    shared_seed_id: int
    final_score: int
    upper_bonus_hit: bool
    upper_subtotal: int
    yahtzee_scored: bool
    yahtzee_bonus_count: int
    category_scores: dict[str, int | None]
    zeroed_categories: tuple[str, ...]
    sampled_states: list[DecisionStateSnapshot] = field(default_factory=list)


@dataclass(frozen=True)
class RolloutReferenceComparisonRecord:
    policy_name: str
    snapshot_id: str
    provenance_source: str
    provenance_seed: int
    provenance_game_id: int
    provenance_policy: str
    dice: tuple[int, ...]
    turn_index: int
    roll_number: int
    score_signature: str
    policy_action: str
    reference_action: str
    matched_rollout_reference: bool
    estimated_policy_value: float
    estimated_reference_value: float
    estimated_regret_vs_reference: float
    evaluation_rollouts: int
    tags: tuple[str, ...] = ()
