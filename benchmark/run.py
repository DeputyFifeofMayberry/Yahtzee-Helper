from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
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
BenchmarkMode = Literal["fast", "standard", "deep", "custom"]


@dataclass(frozen=True)
class BenchmarkSettings:
    full_games: int = 250
    oracle_games: int = 40
    state_sample_games: int = 80
    state_sample_size: int = 120
    state_sample_rate: float = 0.35
    oracle_rollouts: int = 40
    seed: int = 1337


MODE_PROFILES: dict[str, BenchmarkSettings] = {
    "fast": BenchmarkSettings(
        full_games=14,
        oracle_games=3,
        state_sample_games=4,
        state_sample_size=8,
        state_sample_rate=0.08,
        oracle_rollouts=4,
    ),
    "standard": BenchmarkSettings(
        full_games=60,
        oracle_games=12,
        state_sample_games=16,
        state_sample_size=40,
        state_sample_rate=0.2,
        oracle_rollouts=12,
    ),
    "deep": BenchmarkSettings(
        full_games=220,
        oracle_games=50,
        state_sample_games=65,
        state_sample_size=120,
        state_sample_rate=0.4,
        oracle_rollouts=45,
    ),
}


@dataclass
class BenchmarkRunResult:
    settings: BenchmarkSettings
    full_game_results: list[GameSimulationResult]
    oracle_records: list[OracleComparisonRecord]
    full_game_summary: dict[str, dict[str, object]]
    oracle_summary: dict[str, dict[str, object]]
    state_corpus_size: int
    states_compared: int


def profile_settings(mode: BenchmarkMode, seed: int = 1337) -> BenchmarkSettings:
    if mode == "custom":
        return replace(MODE_PROFILES["standard"], seed=seed)
    if mode not in MODE_PROFILES:
        raise ValueError(f"Unknown benchmark mode: {mode}")
    return replace(MODE_PROFILES[mode], seed=seed)


def mode_allows_oracle(settings: BenchmarkSettings) -> bool:
    return (
        settings.state_sample_games > 0
        and settings.state_sample_size > 0
        and settings.oracle_rollouts > 0
    )


def estimate_run_cost(settings: BenchmarkSettings) -> tuple[str, int, int]:
    full_game_total = (settings.full_games * 3) + settings.oracle_games
    estimated_states = min(settings.state_sample_size, int(settings.state_sample_games * 39 * settings.state_sample_rate * 3))
    oracle_work = estimated_states * max(1, settings.oracle_rollouts)
    score = full_game_total + (oracle_work * 0.6)
    if score <= 180:
        return "Fast", full_game_total, estimated_states
    if score <= 1_200:
        return "Moderate", full_game_total, estimated_states
    return "Heavy", full_game_total, estimated_states


def browser_guardrail_warnings(settings: BenchmarkSettings) -> list[str]:
    warnings: list[str] = []
    if settings.full_games > 220:
        warnings.append("Full games is very high for browser usage and may feel slow.")
    if settings.state_sample_size > 150:
        warnings.append("State sample size is very high and can make oracle comparison expensive.")
    if settings.oracle_rollouts > 45:
        warnings.append("Oracle rollouts is very high; this is the biggest cost driver.")
    if mode_allows_oracle(settings) and (settings.state_sample_size * settings.oracle_rollouts) > 4_000:
        warnings.append("Combined oracle workload is heavy for an in-browser run.")
    return warnings


def build_policies(settings: BenchmarkSettings) -> tuple[list[Policy], list[Policy], RolloutOraclePolicy]:
    board_policy = ObjectivePolicy("board_utility", OptimizationObjective.BOARD_UTILITY)
    exact_policy = ObjectivePolicy("exact_turn_ev", OptimizationObjective.EXACT_TURN_EV)
    heuristic_policy = HumanHeuristicPolicy()
    oracle_policy = RolloutOraclePolicy(
        rollouts_per_action=settings.oracle_rollouts,
        continuation_policy=board_policy,
    )

    policies: list[Policy] = [board_policy, exact_policy, heuristic_policy, oracle_policy]
    cheap_policies: list[Policy] = [board_policy, exact_policy, heuristic_policy]
    return policies, cheap_policies, oracle_policy


def run_benchmark(
    settings: BenchmarkSettings,
    advisor: YahtzeeAdvisor | None = None,
    on_progress: ProgressCallback | None = None,
    mode: BenchmarkMode = "custom",
) -> BenchmarkRunResult:
    _validate_settings(settings)
    advisor = advisor or YahtzeeAdvisor()
    policies, cheap_policies, oracle_policy = build_policies(settings)

    total_full_games = (len(cheap_policies) * settings.full_games) + settings.oracle_games
    _progress(on_progress, f"Scoring whole games (0/{total_full_games})", 0.02)

    full_game_results: list[GameSimulationResult] = []
    completed_full_games = 0
    for idx, policy in enumerate(policies):
        game_count = settings.oracle_games if policy.name == oracle_policy.name else settings.full_games
        for game_number in range(game_count):
            seed = settings.seed + (idx * 1_000_000) + game_number
            full_game_results.append(simulate_full_game(policy, seed=seed, advisor=advisor))
            completed_full_games += 1
            fraction = completed_full_games / max(1, total_full_games)
            _progress(
                on_progress,
                f"Scoring whole games ({completed_full_games}/{total_full_games})",
                0.02 + (0.5 * fraction),
            )

    grouped_games: dict[str, list[GameSimulationResult]] = defaultdict(list)
    for result in full_game_results:
        grouped_games[result.policy_name].append(result)

    corpus = []
    snapshots = []
    if mode_allows_oracle(settings):
        _progress(on_progress, "Building sampled test positions", 0.55)
        corpus = sample_state_corpus(
            cheap_policies,
            games_per_policy=settings.state_sample_games,
            seed=settings.seed + 9_000_000,
            advisor=advisor,
            state_sample_rate=settings.state_sample_rate,
        )

        rng = random.Random(settings.seed + 19_000_000)
        if len(corpus) > settings.state_sample_size:
            snapshots = rng.sample(corpus, settings.state_sample_size)
        else:
            snapshots = corpus

        eval_rollouts = max(4, settings.oracle_rollouts // 3)
        _progress(
            on_progress,
            f"Checking choices against best-known reference ({len(snapshots)} states, {eval_rollouts} rollouts)",
            0.72,
        )
        oracle_records = compare_policies_to_oracle(
            snapshots,
            policies,
            oracle_policy,
            advisor=advisor,
            evaluation_rollouts=eval_rollouts,
        )
    else:
        _progress(on_progress, "Skipping best-known reference check for this fast run", 0.72)
        oracle_records = []

    _progress(on_progress, "Summarizing results", 0.92)
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

    _progress(on_progress, "Done", 1.0)
    return BenchmarkRunResult(
        settings=settings,
        full_game_results=full_game_results,
        oracle_records=oracle_records,
        full_game_summary=full_game_summary,
        oracle_summary=oracle_summary,
        state_corpus_size=len(corpus),
        states_compared=len(snapshots),
    )


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
        "state_corpus_size": result.state_corpus_size,
        "states_compared": result.states_compared,
        "full_game_summary": result.full_game_summary,
        "oracle_summary": result.oracle_summary,
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
