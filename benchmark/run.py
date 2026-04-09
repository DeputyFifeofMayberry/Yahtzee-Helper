from __future__ import annotations

import csv
import json
import random
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field, replace
from io import StringIO
from typing import Callable, Literal

from .metrics import summarize_game_results, summarize_oracle_results
from .models import GameSimulationResult, OracleComparisonRecord
from .oracle import RolloutOraclePolicy, compare_policies_to_oracle
from .policies import HumanHeuristicPolicy, ObjectivePolicy, Policy
from .simulator import sample_state_corpus, simulate_full_game
from yahtzee.advisor import YahtzeeAdvisor
from yahtzee.models import OptimizationObjective

ProgressCallback = Callable[[str, float], None]
BenchmarkMode = Literal[
    "quick",
    "balanced",
    "deep",
    "advanced_custom",
    "fast",
    "standard",
    "custom",
]


STRATEGY_KEYS = ("board_utility", "exact_turn_ev", "human_heuristic", "rollout_oracle")
PLAYER_STRATEGY_KEYS = ("board_utility", "exact_turn_ev", "human_heuristic")
REFERENCE_STRATEGY_KEY = "rollout_oracle"
BROWSER_SAFE_PLAYER_KEYS = ("board_utility", "human_heuristic")


@dataclass(frozen=True)
class BenchmarkSettings:
    full_games: int = 24
    oracle_games: int = 0
    state_sample_games: int = 8
    state_sample_size: int = 24
    state_sample_rate: float = 0.2
    oracle_rollouts: int = 8
    seed: int = 1337


MODE_PROFILES: dict[str, BenchmarkSettings] = {
    "quick": BenchmarkSettings(
        full_games=10,
        oracle_games=0,
        state_sample_games=0,
        state_sample_size=0,
        state_sample_rate=0.1,
        oracle_rollouts=0,
    ),
    "balanced": BenchmarkSettings(
        full_games=22,
        oracle_games=0,
        state_sample_games=8,
        state_sample_size=20,
        state_sample_rate=0.16,
        oracle_rollouts=8,
    ),
    "deep": BenchmarkSettings(
        full_games=45,
        oracle_games=4,
        state_sample_games=20,
        state_sample_size=60,
        state_sample_rate=0.25,
        oracle_rollouts=16,
    ),
}

# Backwards compatibility aliases.
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
    oracle_records: list[OracleComparisonRecord]
    full_game_summary: dict[str, dict[str, object]]
    oracle_summary: dict[str, dict[str, object]]
    state_corpus_size: int
    states_compared: int
    strategies_included: list[str] = field(default_factory=list)
    strategies_skipped: list[str] = field(default_factory=list)
    full_game_stage_ran: bool = False
    move_quality_stage_ran: bool = False
    stage_timings_seconds: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    auto_downgraded_settings: list[str] = field(default_factory=list)
    browser_safe_mode_used: bool = True


def _normalize_mode(mode: BenchmarkMode) -> str:
    return {
        "fast": "quick",
        "standard": "balanced",
        "custom": "advanced_custom",
    }.get(mode, mode)


def profile_settings(mode: BenchmarkMode, seed: int = 1337) -> BenchmarkSettings:
    normalized = _normalize_mode(mode)
    if normalized == "advanced_custom":
        return replace(MODE_PROFILES["balanced"], seed=seed)
    if normalized not in MODE_PROFILES:
        raise ValueError(f"Unknown benchmark mode: {mode}")
    return replace(MODE_PROFILES[normalized], seed=seed)


def mode_allows_oracle(settings: BenchmarkSettings) -> bool:
    return (
        settings.state_sample_games > 0
        and settings.state_sample_size > 0
        and settings.oracle_rollouts > 0
    )


def estimate_run_cost(settings: BenchmarkSettings) -> tuple[str, int, int]:
    full_game_total = settings.full_games * len(BROWSER_SAFE_PLAYER_KEYS)
    estimated_states = min(
        settings.state_sample_size,
        int(settings.state_sample_games * 39 * settings.state_sample_rate * len(BROWSER_SAFE_PLAYER_KEYS)),
    )
    oracle_work = estimated_states * max(1, settings.oracle_rollouts)
    score = full_game_total + int(oracle_work * 0.8)
    if score <= 120:
        return "Fast", full_game_total, estimated_states
    if score <= 700:
        return "Moderate", full_game_total, estimated_states
    return "Heavy", full_game_total, estimated_states


def browser_guardrail_warnings(settings: BenchmarkSettings) -> list[str]:
    warnings: list[str] = []
    if settings.full_games > 80:
        warnings.append("Full games is high for browser usage and may feel slow.")
    if settings.state_sample_size > 100:
        warnings.append("State sample size is high and can make move-quality comparison expensive.")
    if settings.oracle_rollouts > 20:
        warnings.append("Reference rollouts is high; this is typically the largest runtime driver.")
    if mode_allows_oracle(settings) and (settings.state_sample_size * settings.oracle_rollouts) > 2_000:
        warnings.append("Combined move-quality workload is heavy for in-browser use.")
    return warnings


def _build_policy(key: str, settings: BenchmarkSettings) -> Policy:
    if key == "board_utility":
        return ObjectivePolicy("board_utility", OptimizationObjective.BOARD_UTILITY)
    if key == "exact_turn_ev":
        return ObjectivePolicy("exact_turn_ev", OptimizationObjective.EXACT_TURN_EV)
    if key == "human_heuristic":
        return HumanHeuristicPolicy()
    if key == "rollout_oracle":
        return RolloutOraclePolicy(
            rollouts_per_action=max(1, settings.oracle_rollouts),
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
    warnings = browser_guardrail_warnings(settings)
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

    include_score = True
    if not include_score and not include_move_quality:
        raise ValueError("At least one stage must be enabled.")

    capped_settings = settings
    if browser_safe:
        adjusted = asdict(settings)
        if adjusted["full_games"] > 60:
            adjusted["full_games"] = 60
            auto_downgrades.append("Capped full games to 60 for browser-safe mode.")
        if adjusted["state_sample_size"] > 60:
            adjusted["state_sample_size"] = 60
            auto_downgrades.append("Capped sampled states to 60 for browser-safe mode.")
        if adjusted["oracle_rollouts"] > 16:
            adjusted["oracle_rollouts"] = 16
            auto_downgrades.append("Capped reference rollouts to 16 for browser-safe mode.")
        if adjusted["state_sample_games"] > 30:
            adjusted["state_sample_games"] = 30
            auto_downgrades.append("Capped sample games to 30 for browser-safe mode.")
        capped_settings = BenchmarkSettings(**adjusted)

    if not include_move_quality:
        capped_settings = replace(capped_settings, state_sample_games=0, state_sample_size=0, oracle_rollouts=0)

    if not mode_allows_oracle(capped_settings):
        include_move_quality = False

    full_game_strategy_count = len(selected) + (1 if include_reference_full_games else 0)
    estimated_states = min(
        capped_settings.state_sample_size,
        int(capped_settings.state_sample_games * 39 * capped_settings.state_sample_rate * len(selected)),
    )
    ref_evals = estimated_states * max(1, capped_settings.oracle_rollouts // 2)
    dominant = "move_quality" if ref_evals > full_game_strategy_count * capped_settings.full_games else "full_games"

    strategies_included = list(selected)
    if include_reference_full_games:
        strategies_included.append(REFERENCE_STRATEGY_KEY)

    skipped = [s for s in STRATEGY_KEYS if s not in strategies_included]
    workload = {
        "full_game_simulations": full_game_strategy_count * capped_settings.full_games,
        "sampled_state_target": estimated_states,
        "reference_evaluations": ref_evals,
        "likely_runtime_driver": dominant,
    }

    return BenchmarkPlan(
        mode=normalized_mode,
        settings=capped_settings,
        selected_player_strategies=tuple(selected),
        include_score_comparison=include_score,
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
    oracle_records: list[OracleComparisonRecord] = []

    if plan.include_score_comparison:
        total_games = len(full_game_policies) * settings.full_games
        _progress(on_progress, f"Stage 1/4: running full-game comparisons (0/{total_games})", 0.02)
        start = time.perf_counter()
        completed = 0
        for idx, policy in enumerate(full_game_policies):
            for game_number in range(settings.full_games):
                seed = settings.seed + (idx * 1_000_000) + game_number
                full_game_results.append(simulate_full_game(policy, seed=seed, advisor=advisor))
                completed += 1
                frac = completed / max(1, total_games)
                _progress(
                    on_progress,
                    f"Stage 1/4: simulating strategy {idx + 1} of {len(full_game_policies)} ({completed}/{total_games} games)",
                    0.02 + (0.44 * frac),
                )
        stage_times["full_games"] = round(time.perf_counter() - start, 3)

    corpus = []
    snapshots = []
    if plan.include_move_quality:
        _progress(on_progress, "Stage 2/4: collecting sampled decision situations (0/?)", 0.48)
        start = time.perf_counter()

        def _corpus_progress(done: int, total: int) -> None:
            frac = done / max(1, total)
            _progress(
                on_progress,
                f"Stage 2/4: collecting sample situations ({done}/{total} games)",
                0.48 + (0.14 * frac),
            )

        corpus = sample_state_corpus(
            player_policies,
            games_per_policy=settings.state_sample_games,
            seed=settings.seed + 9_000_000,
            advisor=advisor,
            state_sample_rate=settings.state_sample_rate,
            on_progress=_corpus_progress,
        )
        rng = random.Random(settings.seed + 19_000_000)
        snapshots = rng.sample(corpus, settings.state_sample_size) if len(corpus) > settings.state_sample_size else corpus
        stage_times["collect_states"] = round(time.perf_counter() - start, 3)

        eval_rollouts = max(4, settings.oracle_rollouts // 2)
        _progress(
            on_progress,
            f"Stage 3/4: checking move quality against reference (0/{len(snapshots)} states)",
            0.64,
        )
        start = time.perf_counter()

        def _oracle_progress(done: int, total: int) -> None:
            frac = done / max(1, total)
            _progress(
                on_progress,
                f"Stage 3/4: checking move quality against reference ({done}/{total} states)",
                0.64 + (0.26 * frac),
            )

        oracle_records = compare_policies_to_oracle(
            snapshots,
            player_policies,
            reference_policy,  # type: ignore[arg-type]
            advisor=advisor,
            evaluation_rollouts=eval_rollouts,
            on_progress=_oracle_progress,
        )
        stage_times["move_quality"] = round(time.perf_counter() - start, 3)
    else:
        _progress(on_progress, "Stage 2/4 skipped: move-quality comparison disabled for this run", 0.64)

    _progress(on_progress, "Stage 4/4: summarizing benchmark results", 0.92)
    start = time.perf_counter()
    grouped_games: dict[str, list[GameSimulationResult]] = defaultdict(list)
    for result in full_game_results:
        grouped_games[result.policy_name].append(result)
    full_game_summary = {
        policy_name: summarize_game_results(results)
        for policy_name, results in sorted(grouped_games.items())
    }

    grouped_oracle: dict[str, list[OracleComparisonRecord]] = defaultdict(list)
    for record in oracle_records:
        grouped_oracle[record.policy_name].append(record)
    oracle_summary = {
        policy_name: summarize_oracle_results(records)
        for policy_name, records in sorted(grouped_oracle.items())
    }
    stage_times["summarize"] = round(time.perf_counter() - start, 3)

    _progress(on_progress, "Done", 1.0)
    return BenchmarkRunResult(
        settings=settings,
        plan=plan,
        full_game_results=full_game_results,
        oracle_records=oracle_records,
        full_game_summary=full_game_summary,
        oracle_summary=oracle_summary,
        state_corpus_size=len(corpus),
        states_compared=len(snapshots),
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


def oracle_records_rows(records: list[OracleComparisonRecord]) -> list[dict[str, object]]:
    return [
        {
            "policy_name": record.policy_name,
            "matched_oracle": int(record.matched_oracle),
            "regret": record.regret,
            "turn_index": record.turn_index,
            "roll_number": record.roll_number,
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
        "oracle_summary": result.oracle_summary,
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
    if settings.oracle_games < 0:
        raise ValueError("oracle_games must be 0 or greater.")
    if settings.state_sample_games < 0:
        raise ValueError("state_sample_games must be 0 or greater.")
    if settings.state_sample_size < 0:
        raise ValueError("state_sample_size must be 0 or greater.")
    if not 0.0 < settings.state_sample_rate <= 1.0:
        raise ValueError("state_sample_rate must be in the range (0.0, 1.0].")
    if settings.oracle_rollouts < 0:
        raise ValueError("oracle_rollouts must be 0 or greater.")


def _progress(on_progress: ProgressCallback | None, label: str, fraction: float) -> None:
    if on_progress is not None:
        on_progress(label, max(0.0, min(1.0, fraction)))
