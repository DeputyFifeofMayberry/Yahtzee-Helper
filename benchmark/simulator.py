from __future__ import annotations

import random
from collections import Counter
from copy import deepcopy
from typing import Callable, Literal

from .models import DecisionStateSnapshot, GameSimulationResult, PolicyDecision
from .policies import Policy
from yahtzee.advisor import YahtzeeAdvisor
from yahtzee.models import Category, GameState, Scorecard
from yahtzee.rules import is_full_house, is_large_straight, is_n_of_a_kind, is_small_straight, is_yahtzee
from yahtzee.state import GameManager

CorpusMode = Literal["neutral_canonical", "on_policy"]


def roll_five_dice(rng: random.Random) -> list[int]:
    return [rng.randint(1, 6) for _ in range(5)]


def reroll_from_hold(current_dice: list[int], held_dice: tuple[int, ...], rng: random.Random) -> list[int]:
    current_counts = Counter(current_dice)
    held_counts = Counter(held_dice)
    for value, count in held_counts.items():
        if count > current_counts.get(value, 0):
            raise ValueError("Held dice must be a subset of the current dice.")
    rerolled = [rng.randint(1, 6) for _ in range(5 - len(held_dice))]
    return list(held_dice) + rerolled


def ensure_active_roll(manager: GameManager, rng: random.Random) -> None:
    if manager.state.turn_index > 13:
        return
    if manager.state.current_dice == [1, 1, 1, 1, 1] and manager.state.roll_number == 1:
        manager.set_current_roll(roll_five_dice(rng), 1)


def classify_state(state: GameState) -> tuple[str, ...]:
    tags: list[str] = []
    tags.append(f"roll_{state.roll_number}")

    if state.turn_index <= 4:
        tags.append("phase_early")
    elif state.turn_index <= 9:
        tags.append("phase_mid")
    else:
        tags.append("phase_late")

    dice = tuple(sorted(state.current_dice))
    if is_full_house(dice):
        tags.append("made_full_house")
    if is_large_straight(dice):
        tags.append("made_large_straight")
    elif is_small_straight(dice):
        tags.append("made_small_straight")
    if is_n_of_a_kind(dice, 4) and not is_yahtzee(dice):
        tags.append("made_four_kind")
        if state.roll_number == 1:
            tags.append("opening_four_kind")

    open_upper = state.scorecard.open_upper_categories()
    if open_upper:
        points_needed = max(0, 63 - state.scorecard.upper_subtotal)
        if 1 <= points_needed <= 24:
            tags.append("upper_bonus_pressure")

    if _is_bailout_state(dice, state.scorecard):
        tags.append("bailout_state")

    return tuple(tags)


def _is_bailout_state(dice: tuple[int, ...], scorecard: Scorecard) -> bool:
    if is_full_house(dice) or is_small_straight(dice) or is_large_straight(dice) or is_n_of_a_kind(dice, 3):
        return False
    return sum(dice) <= 18 and Category.CHANCE in scorecard.open_categories()


def snapshot_state(
    state: GameState,
    *,
    snapshot_id: str,
    provenance_source: str,
    provenance_seed: int,
    provenance_game_id: int,
    provenance_policy: str,
) -> DecisionStateSnapshot:
    return DecisionStateSnapshot(
        snapshot_id=snapshot_id,
        score_signature=state.scorecard.score_signature(),
        dice=tuple(state.current_dice),
        roll_number=state.roll_number,
        turn_index=state.turn_index,
        provenance_source=provenance_source,
        provenance_seed=provenance_seed,
        provenance_game_id=provenance_game_id,
        provenance_policy=provenance_policy,
        tags=classify_state(state),
    )


def clone_state(state: GameState) -> GameState:
    return GameState.from_dict(deepcopy(state.to_dict()))


def apply_decision_once(state: GameState, decision: PolicyDecision, rng: random.Random) -> GameState:
    manager = GameManager(clone_state(state))
    if decision.is_score:
        if decision.category is None:
            raise ValueError("Score decisions must include a category.")
        manager.apply_score(decision.category)
        ensure_active_roll(manager, rng)
        return manager.state

    if decision.held_dice is None:
        raise ValueError("Hold decisions must include held_dice.")
    if manager.state.roll_number >= 3:
        raise ValueError("Cannot hold and reroll on roll 3.")
    next_dice = reroll_from_hold(manager.state.current_dice, decision.held_dice, rng)
    manager.set_current_roll(next_dice, manager.state.roll_number + 1)
    return manager.state


def simulate_full_game(
    policy: Policy,
    seed: int,
    advisor: YahtzeeAdvisor | None = None,
    state_sample_rate: float = 0.0,
    game_id: int = -1,
    shared_seed_id: int = -1,
    provenance_source: str = "full_game_run",
) -> GameSimulationResult:
    rng = random.Random(seed)
    advisor = advisor or YahtzeeAdvisor()
    manager = GameManager(GameState())
    sampled_states: list[DecisionStateSnapshot] = []
    sample_counter = 0

    while manager.state.turn_index <= 13:
        ensure_active_roll(manager, rng)
        if state_sample_rate > 0.0 and rng.random() < state_sample_rate:
            sample_counter += 1
            sampled_states.append(
                snapshot_state(
                    manager.state,
                    snapshot_id=f"{provenance_source}|{policy.name}|g{game_id}|s{sample_counter}",
                    provenance_source=provenance_source,
                    provenance_seed=seed,
                    provenance_game_id=game_id,
                    provenance_policy=policy.name,
                )
            )
        decision = policy.decide(clone_state(manager.state), advisor)
        if decision.is_score:
            if decision.category is None:
                raise ValueError(f"Policy {policy.name} returned a score decision without a category.")
            manager.apply_score(decision.category)
        else:
            if decision.held_dice is None:
                raise ValueError(f"Policy {policy.name} returned a hold decision without held_dice.")
            if manager.state.roll_number >= 3:
                raise ValueError(f"Policy {policy.name} attempted to reroll on roll {manager.state.roll_number}.")
            next_dice = reroll_from_hold(manager.state.current_dice, decision.held_dice, rng)
            manager.set_current_roll(next_dice, manager.state.roll_number + 1)

    final = manager.state.scorecard
    zeroed_categories = tuple(category.value for category, score in final.scores.items() if score == 0)
    return GameSimulationResult(
        policy_name=policy.name,
        seed=seed,
        game_id=game_id,
        shared_seed_id=shared_seed_id,
        final_score=final.grand_total,
        upper_bonus_hit=final.upper_bonus > 0,
        upper_subtotal=final.upper_subtotal,
        yahtzee_scored=(final.scores[Category.YAHTZEE] == 50),
        yahtzee_bonus_count=final.yahtzee_bonus // 100,
        category_scores={category.value: score for category, score in final.scores.items()},
        zeroed_categories=zeroed_categories,
        sampled_states=sampled_states,
    )


def sample_state_corpus(
    *,
    corpus_mode: CorpusMode,
    policies: list[Policy],
    canonical_policy: Policy,
    games_per_policy: int,
    seed: int,
    advisor: YahtzeeAdvisor | None = None,
    state_sample_rate: float = 0.35,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[DecisionStateSnapshot]:
    advisor = advisor or YahtzeeAdvisor()
    corpus: list[DecisionStateSnapshot] = []

    if corpus_mode == "neutral_canonical":
        total_games = max(0, games_per_policy)
        for game_idx in range(total_games):
            game_seed = seed + game_idx
            result = simulate_full_game(
                canonical_policy,
                seed=game_seed,
                advisor=advisor,
                state_sample_rate=state_sample_rate,
                game_id=game_idx,
                shared_seed_id=game_idx,
                provenance_source="neutral_canonical",
            )
            corpus.extend(result.sampled_states)
            if on_progress is not None:
                on_progress(game_idx + 1, total_games)
        return corpus

    sorted_policies = sorted(policies, key=lambda p: p.name)
    total_games = len(sorted_policies) * max(0, games_per_policy)
    done = 0
    for offset, policy in enumerate(sorted_policies):
        for game_idx in range(games_per_policy):
            game_seed = seed + (offset * 1_000_000) + game_idx
            result = simulate_full_game(
                policy,
                seed=game_seed,
                advisor=advisor,
                state_sample_rate=state_sample_rate,
                game_id=game_idx,
                shared_seed_id=game_idx,
                provenance_source="on_policy",
            )
            corpus.extend(result.sampled_states)
            done += 1
            if on_progress is not None:
                on_progress(done, total_games)
    return corpus
