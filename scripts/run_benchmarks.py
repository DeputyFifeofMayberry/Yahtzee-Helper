from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.run import (
    BenchmarkSettings,
    execute_benchmark_plan,
    full_game_results_rows,
    oracle_records_rows,
    plan_benchmark_run,
    profile_settings,
    rows_to_csv,
    run_result_to_dict,
    summary_to_json,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Yahtzee strategy benchmarks.")
    parser.add_argument("--mode", choices=["quick", "balanced", "deep", "advanced_custom"], default="balanced")
    parser.add_argument("--include-move-quality", action="store_true", help="Enable sampled-state reference checks.")
    parser.add_argument("--include-reference-full-games", action="store_true", help="Include rollout reference in full-game stage.")
    parser.add_argument("--include-advanced-strategies", action="store_true", help="Allow expensive strategies like exact_turn_ev.")
    parser.add_argument("--strategies", nargs="*", default=None, help="Explicit player strategy keys to compare.")

    parser.add_argument("--full-games", type=int)
    parser.add_argument("--oracle-games", type=int)
    parser.add_argument("--state-sample-games", type=int)
    parser.add_argument("--state-sample-size", type=int)
    parser.add_argument("--state-sample-rate", type=float)
    parser.add_argument("--oracle-rollouts", type=int)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--output-dir", type=Path, default=Path("benchmark_results"))
    return parser


def _settings_from_args(args: argparse.Namespace) -> BenchmarkSettings:
    base = profile_settings(args.mode, seed=args.seed)
    return BenchmarkSettings(
        full_games=base.full_games if args.full_games is None else args.full_games,
        oracle_games=base.oracle_games if args.oracle_games is None else args.oracle_games,
        state_sample_games=base.state_sample_games if args.state_sample_games is None else args.state_sample_games,
        state_sample_size=base.state_sample_size if args.state_sample_size is None else args.state_sample_size,
        state_sample_rate=base.state_sample_rate if args.state_sample_rate is None else args.state_sample_rate,
        oracle_rollouts=base.oracle_rollouts if args.oracle_rollouts is None else args.oracle_rollouts,
        seed=args.seed,
    )


def main() -> None:
    args = build_parser().parse_args()
    settings = _settings_from_args(args)
    plan = plan_benchmark_run(
        settings=settings,
        mode=args.mode,
        include_move_quality=args.include_move_quality,
        include_advanced_strategies=args.include_advanced_strategies,
        include_reference_full_games=args.include_reference_full_games,
        selected_player_strategies=args.strategies,
    )

    print("Benchmark plan:")
    print(json.dumps({
        "mode": plan.mode,
        "strategies_included": list(plan.strategies_included),
        "strategies_skipped": list(plan.strategies_skipped),
        "workload": plan.workload,
        "warnings": list(plan.warnings),
        "auto_downgraded_settings": list(plan.auto_downgraded_settings),
    }, indent=2))

    result = execute_benchmark_plan(plan)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "full_game_results.csv").write_text(rows_to_csv(full_game_results_rows(result.full_game_results)), encoding="utf-8")
    (args.output_dir / "oracle_comparisons.csv").write_text(rows_to_csv(oracle_records_rows(result.oracle_records)), encoding="utf-8")
    (args.output_dir / "full_game_summary.json").write_text(summary_to_json(result.full_game_summary), encoding="utf-8")
    (args.output_dir / "oracle_summary.json").write_text(summary_to_json(result.oracle_summary), encoding="utf-8")
    (args.output_dir / "run_result.json").write_text(json.dumps(run_result_to_dict(result), indent=2), encoding="utf-8")

    print("Run complete. Stage timings:")
    print(json.dumps(result.stage_timings_seconds, indent=2))


if __name__ == "__main__":
    main()
