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
    rows_to_csv,
    run_benchmark,
    summary_to_json,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Yahtzee policy benchmarks.")
    parser.add_argument("--full-games", type=int, default=250, help="Full games to simulate for non-oracle policies.")
    parser.add_argument("--oracle-games", type=int, default=40, help="Full games to simulate for the rollout oracle policy.")
    parser.add_argument("--state-sample-games", type=int, default=80, help="Games per non-oracle policy for building the state corpus.")
    parser.add_argument("--state-sample-size", type=int, default=120, help="Number of sampled states to compare against the oracle.")
    parser.add_argument("--state-sample-rate", type=float, default=0.35, help="Per-decision sampling rate when building the state corpus.")
    parser.add_argument("--oracle-rollouts", type=int, default=40, help="Rollouts per candidate action for the rollout oracle.")
    parser.add_argument("--seed", type=int, default=1337, help="Base random seed.")
    parser.add_argument("--output-dir", type=Path, default=Path("benchmark_results"), help="Directory for CSV/JSON outputs.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = BenchmarkSettings(
        full_games=args.full_games,
        oracle_games=args.oracle_games,
        state_sample_games=args.state_sample_games,
        state_sample_size=args.state_sample_size,
        state_sample_rate=args.state_sample_rate,
        oracle_rollouts=args.oracle_rollouts,
        seed=args.seed,
    )

    result = run_benchmark(settings)

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
        "full_games": result.full_game_summary,
        "oracle_comparison": result.oracle_summary,
        "state_corpus_size": result.state_corpus_size,
        "states_compared": result.states_compared,
    }
    print(json.dumps(console_summary, indent=2))


if __name__ == "__main__":
    main()
