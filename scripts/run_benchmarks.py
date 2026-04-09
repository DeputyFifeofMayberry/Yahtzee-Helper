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
    full_game_results_rows,
    oracle_records_rows,
    profile_settings,
    rows_to_csv,
    run_benchmark,
    summary_to_json,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Yahtzee policy benchmarks.")
    parser.add_argument(
        "--mode",
        choices=["fast", "standard", "deep", "custom"],
        default="standard",
        help="Run profile. Use custom to only use explicit numeric flags.",
    )
    parser.add_argument("--full-games", type=int, help="Full games to simulate for non-oracle policies.")
    parser.add_argument("--oracle-games", type=int, help="Full games to simulate for the rollout oracle policy.")
    parser.add_argument("--state-sample-games", type=int, help="Games per non-oracle policy for building the state corpus.")
    parser.add_argument("--state-sample-size", type=int, help="Number of sampled states to compare against the oracle.")
    parser.add_argument("--state-sample-rate", type=float, help="Per-decision sampling rate when building the state corpus.")
    parser.add_argument("--oracle-rollouts", type=int, help="Rollouts per candidate action for the rollout oracle.")
    parser.add_argument("--seed", type=int, default=1337, help="Base random seed.")
    parser.add_argument("--output-dir", type=Path, default=Path("benchmark_results"), help="Directory for CSV/JSON outputs.")
    return parser


def _settings_from_args(args: argparse.Namespace) -> BenchmarkSettings:
    if args.mode == "custom":
        settings = BenchmarkSettings(seed=args.seed)
    else:
        settings = profile_settings(args.mode, seed=args.seed)

    overrides = {
        "full_games": args.full_games,
        "oracle_games": args.oracle_games,
        "state_sample_games": args.state_sample_games,
        "state_sample_size": args.state_sample_size,
        "state_sample_rate": args.state_sample_rate,
        "oracle_rollouts": args.oracle_rollouts,
    }
    return BenchmarkSettings(
        full_games=settings.full_games if overrides["full_games"] is None else overrides["full_games"],
        oracle_games=settings.oracle_games if overrides["oracle_games"] is None else overrides["oracle_games"],
        state_sample_games=settings.state_sample_games if overrides["state_sample_games"] is None else overrides["state_sample_games"],
        state_sample_size=settings.state_sample_size if overrides["state_sample_size"] is None else overrides["state_sample_size"],
        state_sample_rate=settings.state_sample_rate if overrides["state_sample_rate"] is None else overrides["state_sample_rate"],
        oracle_rollouts=settings.oracle_rollouts if overrides["oracle_rollouts"] is None else overrides["oracle_rollouts"],
        seed=args.seed,
    )


def main() -> None:
    args = build_parser().parse_args()
    settings = _settings_from_args(args)

    result = run_benchmark(settings, mode=args.mode)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "full_game_results.csv").write_text(
        rows_to_csv(full_game_results_rows(result.full_game_results)),
        encoding="utf-8",
    )
    (args.output_dir / "oracle_comparisons.csv").write_text(
        rows_to_csv(oracle_records_rows(result.oracle_records)),
        encoding="utf-8",
    )
    (args.output_dir / "full_game_summary.json").write_text(
        summary_to_json(result.full_game_summary),
        encoding="utf-8",
    )
    (args.output_dir / "oracle_summary.json").write_text(
        summary_to_json(result.oracle_summary),
        encoding="utf-8",
    )

    console_summary = {
        "settings": vars(settings),
        "full_games": result.full_game_summary,
        "oracle_comparison": result.oracle_summary,
        "state_corpus_size": result.state_corpus_size,
        "states_compared": result.states_compared,
    }
    print(json.dumps(console_summary, indent=2))


if __name__ == "__main__":
    main()
