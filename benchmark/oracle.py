from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from .models import DecisionStateSnapshot, OracleComparisonRecord, PolicyDecision
from .policies import Policy
from .simulator import apply_decision_once, clone_state, ensure_active_roll
from yahtzee.advisor import YahtzeeAdvisor
from yahtzee.models import ActionType, GameState, OptimizationObjective, Scorecard
from yahtzee.state import GameManager
from yahtzee.utils import distinct_holds


DecisionKey = tuple[str, tuple[int, ...], int, int, str, tuple[int, ...], str | None]


def scorecard_from_snapshot(snapshot: DecisionStateSnapshot) -> Scorecard:
    return Scorecard.from_signature(snapshot.score_signature)


def state_from_snapshot(snapshot: DecisionStateSnapshot) -> GameState:
    return GameState(
        scorecard=scorecard_from_snapshot(snapshot),
        turn_index=snapshot.turn_index,
        current_dice=list(snapshot.dice),
        roll_number=snapshot.roll_number,
    )


def enumerate_candidate_decisions(state: GameState) -> list[PolicyDecision]:
    candidates: list[PolicyDecision] = []
    if state.roll_number < 3:
        for hold in distinct_holds(state.current_dice):
            candidates.append(
                PolicyDecision(
                    action_type=ActionType.HOLD_AND_REROLL,
                    held_dice=tuple(hold),
                    description=f"Hold {list(hold) if hold else 'nothing'}",
                )
            )
    for category in state.scorecard.legal_scoring_categories(state.current_dice):
        candidates.append(
            PolicyDecision(
                action_type=ActionType.SCORE_NOW,
                category=category,
                description=f"Score {category.value}",
            )
        )
    return candidates


@dataclass
class RolloutOraclePolicy:
    name: str = "rollout_oracle"
    rollouts_per_action: int = 60
    continuation_policy: Policy | None = None

    def decide(self, state: GameState, advisor: YahtzeeAdvisor) -> PolicyDecision:
        candidates = enumerate_candidate_decisions(state)
        if not candidates:
            raise ValueError("No candidate decisions available for rollout oracle.")
        evaluation_seeds = self._evaluation_seeds(state, self.rollouts_per_action)

        best_decision: PolicyDecision | None = None
        best_value = float("-inf")
        for candidate in candidates:
            value = self._estimate_action_value(state, candidate, advisor, evaluation_seeds)
            if value > best_value:
                best_value = value
                best_decision = candidate

        if best_decision is None:
            raise ValueError("Rollout oracle failed to choose an action.")
        return best_decision

    def _estimate_action_value(
        self,
        state: GameState,
        decision: PolicyDecision,
        advisor: YahtzeeAdvisor,
        rollout_seeds: list[int],
        decision_cache: dict[DecisionKey, float] | None = None,
    ) -> float:
        continuation = self.continuation_policy or ObjectivePolicyAdapter(OptimizationObjective.BOARD_UTILITY)
        cache_key = _decision_cache_key(state, decision, rollout_seeds, continuation.name)
        if decision_cache is not None and cache_key in decision_cache:
            return decision_cache[cache_key]

        total = 0.0
        for seed in rollout_seeds:
            rng = random.Random(seed)
            advanced_state = apply_decision_once(state, decision, rng)
            if advanced_state.turn_index > 13:
                total += advanced_state.scorecard.grand_total
                continue
            total += simulate_from_active_state(advanced_state, continuation, seed + 17, advisor)

        value = total / max(1, len(rollout_seeds))
        if decision_cache is not None:
            decision_cache[cache_key] = value
        return value

    def _evaluation_seeds(self, state: GameState, count: int) -> list[int]:
        base = self._seed_from_state(state)
        return [base + idx + 1 for idx in range(max(1, count))]

    @staticmethod
    def _seed_from_state(state: GameState) -> int:
        signature = state.scorecard.score_signature()
        hashable = (tuple(state.current_dice), state.roll_number, state.turn_index, signature)
        return abs(hash(hashable)) % (2**31 - 1)


@dataclass
class ObjectivePolicyAdapter:
    objective: OptimizationObjective

    @property
    def name(self) -> str:
        return self.objective.value.lower()

    def decide(self, state: GameState, advisor: YahtzeeAdvisor) -> PolicyDecision:
        rec = advisor.recommend(list(state.current_dice), state.roll_number, state.scorecard, objective=self.objective)
        best = rec.best_action
        return PolicyDecision(
            action_type=best.action_type,
            held_dice=tuple(best.held_dice) if best.held_dice is not None else None,
            category=best.category,
            description=best.description,
        )


def simulate_from_active_state(
    initial_state: GameState,
    policy: Policy,
    seed: int,
    advisor: YahtzeeAdvisor | None = None,
) -> int:
    rng = random.Random(seed)
    advisor = advisor or YahtzeeAdvisor()
    manager = GameManager(clone_state(initial_state))
    ensure_active_roll(manager, rng)

    while manager.state.turn_index <= 13:
        decision = policy.decide(clone_state(manager.state), advisor)
        if decision.is_score:
            if decision.category is None:
                raise ValueError("Continuation policy returned a score decision without a category.")
            manager.apply_score(decision.category)
            ensure_active_roll(manager, rng)
            continue

        if decision.held_dice is None:
            raise ValueError("Continuation policy returned a hold decision without held_dice.")
        if manager.state.roll_number >= 3:
            raise ValueError("Continuation policy attempted to reroll on roll 3.")
        advanced_state = apply_decision_once(manager.state, decision, rng)
        manager = GameManager(advanced_state)

    return manager.state.scorecard.grand_total


def compare_policies_to_oracle(
    snapshots: list[DecisionStateSnapshot],
    policies: list[Policy],
    oracle: RolloutOraclePolicy,
    advisor: YahtzeeAdvisor | None = None,
    evaluation_rollouts: int | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[OracleComparisonRecord]:
    advisor = advisor or YahtzeeAdvisor()
    records: list[OracleComparisonRecord] = []
    decision_cache: dict[DecisionKey, float] = {}
    state_decision_cache: dict[tuple[str, tuple[int, ...], int, int], PolicyDecision] = {}

    total_states = len(snapshots)
    for idx, snapshot in enumerate(snapshots, start=1):
        state = state_from_snapshot(snapshot)
        state_key = (snapshot.score_signature, snapshot.dice, snapshot.roll_number, snapshot.turn_index)
        oracle_decision = state_decision_cache.get(state_key)
        if oracle_decision is None:
            oracle_decision = oracle.decide(clone_state(state), advisor)
            state_decision_cache[state_key] = oracle_decision

        rollout_count = evaluation_rollouts if evaluation_rollouts is not None else max(8, oracle.rollouts_per_action // 3)
        evaluation_seeds = oracle._evaluation_seeds(state, rollout_count)
        oracle_value = oracle._estimate_action_value(
            state,
            oracle_decision,
            advisor,
            evaluation_seeds,
            decision_cache=decision_cache,
        )

        for policy in policies:
            decision = policy.decide(clone_state(state), advisor)
            matched = _decisions_match(decision, oracle_decision)
            if matched:
                policy_value = oracle_value
            else:
                policy_value = oracle._estimate_action_value(
                    state,
                    decision,
                    advisor,
                    evaluation_seeds,
                    decision_cache=decision_cache,
                )
            records.append(
                OracleComparisonRecord(
                    policy_name=policy.name,
                    matched_oracle=matched,
                    regret=max(0.0, oracle_value - policy_value),
                    turn_index=snapshot.turn_index,
                    roll_number=snapshot.roll_number,
                    tags=snapshot.tags,
                )
            )
        if on_progress is not None:
            on_progress(idx, total_states)
    return records


def _decision_cache_key(
    state: GameState,
    decision: PolicyDecision,
    rollout_seeds: list[int],
    continuation_name: str | None,
) -> DecisionKey:
    action = decision.action_type.value
    held = tuple(decision.held_dice or ())
    category = decision.category.value if decision.category is not None else None
    return (
        state.scorecard.score_signature(),
        tuple(state.current_dice),
        state.roll_number,
        state.turn_index,
        f"{action}|{held}|{category}",
        tuple(rollout_seeds),
        continuation_name,
    )


def _decisions_match(a: PolicyDecision, b: PolicyDecision) -> bool:
    return a.action_type == b.action_type and a.held_dice == b.held_dice and a.category == b.category
