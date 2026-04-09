from __future__ import annotations

import csv
import json
import random
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field, replace
from io import StringIO
from typing import Callable, Literal

from .metrics import summarize_game_results, summarize_paired_score_deltas, summarize_rollout_reference_results
from .models import GameSimulationResult, RolloutReferenceComparisonRecord
from .oracle import RolloutReferencePolicy, compare_policies_to_rollout_reference
from .policies import HumanHeuristicPolicy, ObjectivePolicy, Policy
from .simulator import CorpusMode, sample_state_corpus, simulate_full_game
from yahtzee.advisor import YahtzeeAdvisor
from yahtzee.models import OptimizationObjective

ProgressCallback = Callable[[str, float], None]
BenchmarkMode = Literal["quick", "balanced", "deep", "advanced_custom", "fast", "standard", "custom"]

STRATEGY_KEYS = ("board_utility", "exact_turn_ev", "human_heuristic", "rollout_reference")
PLAYER_STRATEGY_KEYS = ("board_utility", "exact_turn_ev", "human_heuristic")
REFERENCE_STRATEGY_KEY = "rollout_reference"
BROWSER_SAFE_PLAYER_KEYS = ("board_utility", "human_heuristic")
METHODOLOGY_VERSION = "2026.04-common-rng-rollout-reference-v1"


@dataclass(frozen=True)
class BenchmarkSettings:
    full_games: int = 24
    state_sample_games: int = 8
    state_sample_size: int = 24
    state_sample_rate: float = 0.2
    rollout_reference_rollouts: int = 16
    seed: int = 1337
    corpus_mode: CorpusMode = "neutral_canonical"


MODE_PROFILES: dict[str, BenchmarkSettings] = {
    "quick": BenchmarkSettings(full_games=10, state_sample_games=0, state_sample_size=0, state_sample_rate=0.1, rollout_reference_rollouts=0),
    "balanced": BenchmarkSettings(full_games=24, state_sample_games=8, state_sample_size=24, state_sample_rate=0.18, rollout_reference_rollouts=16),
    "deep": BenchmarkSettings(full_games=60, state_sample_games=24, state_sample_size=90, state_sample_rate=0.25, rollout_reference_rollouts=30),
}
MODE_PROFILES["fast"] = MODE_PROFILES["quick"]
MODE_PROFILES["standard"] = MODE_PROFILES["balanced"]


@dataclass(frozen=True)
class BenchmarkPlan:
    mode: str
    settings: BenchmarkSettings
    selected_player_strategies: tuple[str, ...]
    include_score_comparison: bool
    include_move_quality: bool
    include_reference_full_games: bool
    browser_safe_mode_used: bool
    strategies_included: tuple[str, ...]
    strategies_skipped: tuple[str, ...]
    auto_downgraded_settings: tuple[str, ...]
    warnings: tuple[str, ...]
    workload: dict[str, int | str]


@dataclass
class BenchmarkRunResult:
    settings: BenchmarkSettings
    plan: BenchmarkPlan
    full_game_results: list[GameSimulationResult]
    rollout_reference_records: list[RolloutReferenceComparisonRecord]
    full_game_summary: dict[str, dict[str, object]]
    rollout_reference_summary: dict[str, dict[str, object]]
    state_corpus_size: int
    states_compared: int
    paired_score_deltas: dict[str, dict[str, float]] = field(default_factory=dict)
    run_manifest: dict[str, object] = field(default_factory=dict)
    strategies_included: list[str] = field(default_factory=list)
    strategies_skipped: list[str] = field(default_factory=list)
    full_game_stage_ran: bool = False
    move_quality_stage_ran: bool = False
    stage_timings_seconds: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    auto_downgraded_settings: list[str] = field(default_factory=list)
    browser_safe_mode_used: bool = True


def _normalize_mode(mode: BenchmarkMode) -> str:
    return {"fast": "quick", "standard": "balanced", "custom": "advanced_custom"}.get(mode, mode)


def profile_settings(mode: BenchmarkMode, seed: int = 1337) -> BenchmarkSettings:
    normalized = _normalize_mode(mode)
    if normalized == "advanced_custom":
        return replace(MODE_PROFILES["balanced"], seed=seed)
    if normalized not in MODE_PROFILES:
        raise ValueError(f"Unknown benchmark mode: {mode}")
    return replace(MODE_PROFILES[normalized], seed=seed)


def mode_allows_rollout_reference(settings: BenchmarkSettings) -> bool:
    return settings.state_sample_games > 0 and settings.state_sample_size > 0 and settings.rollout_reference_rollouts > 0


def estimate_run_cost(settings: BenchmarkSettings) -> tuple[str, int, int]:
    full_games = settings.full_games * len(BROWSER_SAFE_PLAYER_KEYS)
    sampled_states = settings.state_sample_size
    cost = full_games + sampled_states * max(1, settings.rollout_reference_rollouts // 2)
    if cost <= 150:
        return "Fast", full_games, sampled_states
    if cost <= 800:
        return "Moderate", full_games, sampled_states
    return "Heavy", full_games, sampled_states


def _build_policy(key: str, settings: BenchmarkSettings) -> Policy:
    if key == "board_utility":
        return ObjectivePolicy("board_utility", OptimizationObjective.BOARD_UTILITY)
    if key == "exact_turn_ev":
        return ObjectivePolicy("exact_turn_ev", OptimizationObjective.EXACT_TURN_EV)
    if key == "human_heuristic":
        return HumanHeuristicPolicy()
    if key == "rollout_reference":
        return RolloutReferencePolicy(
            rollouts_per_action=max(8, settings.rollout_reference_rollouts),
            continuation_policy=ObjectivePolicy("board_utility", OptimizationObjective.BOARD_UTILITY),
        )
    raise ValueError(f"Unknown strategy key: {key}")


def plan_benchmark_run(
    settings: BenchmarkSettings,
    mode: BenchmarkMode = "balanced",
    include_move_quality: bool | None = None,
    include_advanced_strategies: bool = False,
    include_reference_full_games: bool = False,
    selected_player_strategies: list[str] | None = None,
) -> BenchmarkPlan:
    _validate_settings(settings)
    normalized_mode = _normalize_mode(mode)
    if normalized_mode not in {"quick", "balanced", "deep", "advanced_custom"}:
        raise ValueError(f"Unknown benchmark mode: {mode}")

    auto_downgrades: list[str] = []
    warnings: list[str] = []
    browser_safe = normalized_mode != "advanced_custom"

    if selected_player_strategies is None:
        selected_player_strategies = list(BROWSER_SAFE_PLAYER_KEYS)
        if include_advanced_strategies and normalized_mode == "advanced_custom":
            selected_player_strategies.append("exact_turn_ev")

    selected = [s for s in selected_player_strategies if s in PLAYER_STRATEGY_KEYS]
    if browser_safe and "exact_turn_ev" in selected:
        selected = [s for s in selected if s != "exact_turn_ev"]
        auto_downgrades.append("Removed exact_turn_ev from browser-safe mode.")

    if normalized_mode in {"quick", "balanced", "deep"} and "exact_turn_ev" in selected:
        selected = [s for s in selected if s != "exact_turn_ev"]
        auto_downgrades.append("Removed exact_turn_ev because only Advanced Custom mode allows expensive strategies.")

    if not selected:
        raise ValueError("At least one non-reference strategy must be selected.")

    if include_move_quality is None:
        include_move_quality = normalized_mode in {"balanced", "deep", "advanced_custom"}

    capped_settings = settings
    if browser_safe:
        adjusted = asdict(settings)
        if adjusted["full_games"] > 80:
            adjusted["full_games"] = 80
            auto_downgrades.append("Capped full games to 80 for browser-safe mode.")
        if adjusted["state_sample_size"] > 100:
            adjusted["state_sample_size"] = 100
            auto_downgrades.append("Capped sampled states to 100 for browser-safe mode.")
        if adjusted["rollout_reference_rollouts"] > 24:
            adjusted["rollout_reference_rollouts"] = 24
            auto_downgrades.append("Capped rollout reference rollouts to 24 for browser-safe mode.")
        if adjusted["state_sample_games"] > 40:
            adjusted["state_sample_games"] = 40
            auto_downgrades.append("Capped sample games to 40 for browser-safe mode.")
        capped_settings = BenchmarkSettings(**adjusted)

    if not include_move_quality:
        capped_settings = replace(capped_settings, state_sample_games=0, state_sample_size=0, rollout_reference_rollouts=0)

    if not mode_allows_rollout_reference(capped_settings):
        include_move_quality = False

    strategies_included = list(selected)
    if include_reference_full_games:
        strategies_included.append(REFERENCE_STRATEGY_KEY)

    skipped = [s for s in STRATEGY_KEYS if s not in strategies_included]
    workload = {
        "full_game_simulations": len(strategies_included) * capped_settings.full_games,
        "sampled_state_target": capped_settings.state_sample_size,
        "reference_evaluations": capped_settings.state_sample_size * max(1, capped_settings.rollout_reference_rollouts),
        "likely_runtime_driver": "move_quality" if include_move_quality else "full_games",
    }
    if include_move_quality and capped_settings.corpus_mode != "neutral_canonical":
        warnings.append("Using on-policy corpus mode can bias move-quality distributions.")

    return BenchmarkPlan(
        mode=normalized_mode,
        settings=capped_settings,
        selected_player_strategies=tuple(selected),
        include_score_comparison=True,
        include_move_quality=include_move_quality,
        include_reference_full_games=include_reference_full_games,
        browser_safe_mode_used=browser_safe,
        strategies_included=tuple(strategies_included),
        strategies_skipped=tuple(skipped),
        auto_downgraded_settings=tuple(auto_downgrades),
        warnings=tuple(warnings),
        workload=workload,
    )


def execute_benchmark_plan(
    plan: BenchmarkPlan,
    advisor: YahtzeeAdvisor | None = None,
    on_progress: ProgressCallback | None = None,
) -> BenchmarkRunResult:
    advisor = advisor or YahtzeeAdvisor()
    settings = plan.settings

    player_policies = [_build_policy(key, settings) for key in plan.selected_player_strategies]
    reference_policy = _build_policy(REFERENCE_STRATEGY_KEY, settings)
    full_game_policies = list(player_policies)
    if plan.include_reference_full_games:
        full_game_policies.append(reference_policy)

    stage_times: dict[str, float] = {}
    full_game_results: list[GameSimulationResult] = []
    rollout_reference_records: list[RolloutReferenceComparisonRecord] = []

    shared_game_seeds = [settings.seed + i for i in range(settings.full_games)]

    total_games = len(full_game_policies) * settings.full_games
    _progress(on_progress, f"Stage 1/4: running full-game comparisons with common seeds (0/{total_games})", 0.02)
    start = time.perf_counter()
    completed = 0
    for idx, policy in enumerate(full_game_policies):
        for game_id, game_seed in enumerate(shared_game_seeds):
            full_game_results.append(
                simulate_full_game(
                    policy,
                    seed=game_seed,
                    advisor=advisor,
                    game_id=game_id,
                    shared_seed_id=game_id,
                )
            )
            completed += 1
            frac = completed / max(1, total_games)
            _progress(
                on_progress,
                f"Stage 1/4: strategy {idx + 1} of {len(full_game_policies)} ({completed}/{total_games} games)",
                0.02 + (0.44 * frac),
            )
    stage_times["full_games"] = round(time.perf_counter() - start, 3)

    corpus: list = []
    snapshots: list = []
    if plan.include_move_quality:
        _progress(on_progress, "Stage 2/4: collecting sampled decision corpus (0/?)", 0.48)
        start = time.perf_counter()

        def _corpus_progress(done: int, total: int) -> None:
            frac = done / max(1, total)
            _progress(on_progress, f"Stage 2/4: collecting sample situations ({done}/{total} games)", 0.48 + (0.14 * frac))

        corpus = sample_state_corpus(
            corpus_mode=settings.corpus_mode,
            policies=player_policies,
            canonical_policy=ObjectivePolicy("board_utility", OptimizationObjective.BOARD_UTILITY),
            games_per_policy=settings.state_sample_games,
            seed=settings.seed + 9_000_000,
            advisor=advisor,
            state_sample_rate=settings.state_sample_rate,
            on_progress=_corpus_progress,
        )
        rng = random.Random(settings.seed + 19_000_000)
        snapshots = rng.sample(corpus, settings.state_sample_size) if len(corpus) > settings.state_sample_size else list(corpus)
        stage_times["collect_states"] = round(time.perf_counter() - start, 3)

        eval_rollouts = max(8, settings.rollout_reference_rollouts)
        _progress(on_progress, f"Stage 3/4: comparing policies vs rollout reference (0/{len(snapshots)} states)", 0.64)
        start = time.perf_counter()

        def _reference_progress(done: int, total: int) -> None:
            frac = done / max(1, total)
            _progress(on_progress, f"Stage 3/4: comparing policies vs rollout reference ({done}/{total} states)", 0.64 + (0.26 * frac))

        rollout_reference_records = compare_policies_to_rollout_reference(
            snapshots,
            player_policies,
            reference_policy,  # type: ignore[arg-type]
            advisor=advisor,
            evaluation_rollouts=eval_rollouts,
            on_progress=_reference_progress,
        )
        stage_times["move_quality"] = round(time.perf_counter() - start, 3)
    else:
        _progress(on_progress, "Stage 2/4 skipped: move-quality comparison disabled for this run", 0.64)

    _progress(on_progress, "Stage 4/4: summarizing benchmark results", 0.92)
    start = time.perf_counter()
    grouped_games: dict[str, list[GameSimulationResult]] = defaultdict(list)
    for result in full_game_results:
        grouped_games[result.policy_name].append(result)
    full_game_summary = {policy_name: summarize_game_results(results) for policy_name, results in sorted(grouped_games.items())}

    grouped_reference: dict[str, list[RolloutReferenceComparisonRecord]] = defaultdict(list)
    for record in rollout_reference_records:
        grouped_reference[record.policy_name].append(record)
    rollout_reference_summary = {
        policy_name: summarize_rollout_reference_results(records)
        for policy_name, records in sorted(grouped_reference.items())
    }
    paired_deltas = summarize_paired_score_deltas(full_game_results)
    stage_times["summarize"] = round(time.perf_counter() - start, 3)

    manifest = {
        "methodology_version": METHODOLOGY_VERSION,
        "mode": plan.mode,
        "requested_settings": asdict(settings),
        "effective_settings": asdict(plan.settings),
        "strategy_set": list(plan.strategies_included),
        "rng_scheme": "common-random-numbers-for-full-games; stable-sha256-state-seeds-for-rollout-reference",
        "browser_safe_mode_used": plan.browser_safe_mode_used,
        "corpus_mode": settings.corpus_mode,
        "warnings": list(plan.warnings),
        "auto_adjustments": list(plan.auto_downgraded_settings),
    }

    _progress(on_progress, "Done", 1.0)
    return BenchmarkRunResult(
        settings=settings,
        plan=plan,
        full_game_results=full_game_results,
        rollout_reference_records=rollout_reference_records,
        full_game_summary=full_game_summary,
        rollout_reference_summary=rollout_reference_summary,
        state_corpus_size=len(corpus),
        states_compared=len(snapshots),
        paired_score_deltas=paired_deltas,
        run_manifest=manifest,
        strategies_included=list(plan.strategies_included),
        strategies_skipped=list(plan.strategies_skipped),
        full_game_stage_ran=plan.include_score_comparison,
        move_quality_stage_ran=plan.include_move_quality,
        stage_timings_seconds=stage_times,
        warnings=list(plan.warnings),
        auto_downgraded_settings=list(plan.auto_downgraded_settings),
        browser_safe_mode_used=plan.browser_safe_mode_used,
    )


def run_benchmark(
    settings: BenchmarkSettings,
    advisor: YahtzeeAdvisor | None = None,
    on_progress: ProgressCallback | None = None,
    mode: BenchmarkMode = "advanced_custom",
) -> BenchmarkRunResult:
    plan = plan_benchmark_run(settings=settings, mode=mode)
    return execute_benchmark_plan(plan, advisor=advisor, on_progress=on_progress)


def full_game_results_rows(results: list[GameSimulationResult]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for result in results:
        row: dict[str, object] = {
            "policy_name": result.policy_name,
            "seed": result.seed,
            "game_id": result.game_id,
            "shared_seed_id": result.shared_seed_id,
            "final_score": result.final_score,
            "upper_bonus_hit": int(result.upper_bonus_hit),
            "upper_subtotal": result.upper_subtotal,
            "yahtzee_scored": int(result.yahtzee_scored),
            "yahtzee_bonus_count": result.yahtzee_bonus_count,
            "zeroed_categories": "|".join(result.zeroed_categories),
        }
        row.update({f"category::{name}": score for name, score in result.category_scores.items()})
        rows.append(row)
    return rows


def rollout_reference_records_rows(records: list[RolloutReferenceComparisonRecord]) -> list[dict[str, object]]:
    return [
        {
            "policy_name": record.policy_name,
            "snapshot_id": record.snapshot_id,
            "provenance_source": record.provenance_source,
            "provenance_seed": record.provenance_seed,
            "provenance_game_id": record.provenance_game_id,
            "provenance_policy": record.provenance_policy,
            "dice": "|".join(str(v) for v in record.dice),
            "turn_index": record.turn_index,
            "roll_number": record.roll_number,
            "score_signature": record.score_signature,
            "policy_action": record.policy_action,
            "reference_action": record.reference_action,
            "matched_rollout_reference": int(record.matched_rollout_reference),
            "estimated_policy_value": record.estimated_policy_value,
            "estimated_reference_value": record.estimated_reference_value,
            "estimated_regret_vs_reference": record.estimated_regret_vs_reference,
            "evaluation_rollouts": record.evaluation_rollouts,
            "tags": "|".join(record.tags),
        }
        for record in records
    ]


def rows_to_csv(rows: list[dict[str, object]]) -> str:
    if not rows:
        return ""
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def summary_to_json(summary: dict[str, dict[str, object]]) -> str:
    return json.dumps(summary, indent=2, sort_keys=True)


def run_result_to_dict(result: BenchmarkRunResult) -> dict[str, object]:
    return {
        "settings": asdict(result.settings),
        "plan": {
            "mode": result.plan.mode,
            "strategies_included": list(result.plan.strategies_included),
            "strategies_skipped": list(result.plan.strategies_skipped),
            "include_score_comparison": result.plan.include_score_comparison,
            "include_move_quality": result.plan.include_move_quality,
            "include_reference_full_games": result.plan.include_reference_full_games,
            "workload": result.plan.workload,
            "warnings": list(result.plan.warnings),
            "auto_downgraded_settings": list(result.plan.auto_downgraded_settings),
            "browser_safe_mode_used": result.plan.browser_safe_mode_used,
        },
        "state_corpus_size": result.state_corpus_size,
        "states_compared": result.states_compared,
        "full_game_summary": result.full_game_summary,
        "rollout_reference_summary": result.rollout_reference_summary,
        "paired_score_deltas": result.paired_score_deltas,
        "run_manifest": result.run_manifest,
        "stage_timings_seconds": result.stage_timings_seconds,
        "full_game_stage_ran": result.full_game_stage_ran,
        "move_quality_stage_ran": result.move_quality_stage_ran,
        "strategies_included": result.strategies_included,
        "strategies_skipped": result.strategies_skipped,
        "warnings": result.warnings,
        "auto_downgraded_settings": result.auto_downgraded_settings,
        "browser_safe_mode_used": result.browser_safe_mode_used,
    }


def _validate_settings(settings: BenchmarkSettings) -> None:
    if settings.full_games <= 0:
        raise ValueError("full_games must be greater than 0.")
    if settings.state_sample_games < 0:
        raise ValueError("state_sample_games must be 0 or greater.")
    if settings.state_sample_size < 0:
        raise ValueError("state_sample_size must be 0 or greater.")
    if not 0.0 < settings.state_sample_rate <= 1.0:
        raise ValueError("state_sample_rate must be in the range (0.0, 1.0].")
    if settings.rollout_reference_rollouts < 0:
        raise ValueError("rollout_reference_rollouts must be 0 or greater.")


def _progress(on_progress: ProgressCallback | None, label: str, fraction: float) -> None:
    if on_progress is not None:
        on_progress(label, max(0.0, min(1.0, fraction)))
