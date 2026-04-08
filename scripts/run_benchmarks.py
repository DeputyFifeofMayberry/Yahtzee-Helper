from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

from benchmark.metrics import summarize_game_results, summarize_oracle_results
from benchmark.oracle import RolloutOraclePolicy, compare_policies_to_oracle
from benchmark.policies import HumanHeuristicPolicy, ObjectivePolicy
from benchmark.simulator import sample_state_corpus, simulate_full_game
from yahtzee.advisor import YahtzeeAdvisor
from yahtzee.models import OptimizationObjective


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
    advisor = YahtzeeAdvisor()

    board_policy = ObjectivePolicy("board_utility", OptimizationObjective.BOARD_UTILITY)
    exact_policy = ObjectivePolicy("exact_turn_ev", OptimizationObjective.EXACT_TURN_EV)
    heuristic_policy = HumanHeuristicPolicy()
    oracle_policy = RolloutOraclePolicy(rollouts_per_action=args.oracle_rollouts, continuation_policy=board_policy)

    policies = [board_policy, exact_policy, heuristic_policy, oracle_policy]
    cheap_policies = [board_policy, exact_policy, heuristic_policy]

    args.output_dir.mkdir(parents=True, exist_ok=True)

    full_game_results = []
    for idx, policy in enumerate(policies):
        game_count = args.oracle_games if policy.name == oracle_policy.name else args.full_games
        for game_number in range(game_count):
            seed = args.seed + (idx * 1_000_000) + game_number
            full_game_results.append(simulate_full_game(policy, seed=seed, advisor=advisor))

    grouped_games: dict[str, list] = defaultdict(list)
    for result in full_game_results:
        grouped_games[result.policy_name].append(result)

    full_game_summary = {
        policy_name: summarize_game_results(results)
        for policy_name, results in sorted(grouped_games.items())
    }

    corpus = sample_state_corpus(
        cheap_policies,
        games_per_policy=args.state_sample_games,
        seed=args.seed + 9_000_000,
        advisor=advisor,
        state_sample_rate=args.state_sample_rate,
    )
    rng = random.Random(args.seed + 19_000_000)
    if len(corpus) > args.state_sample_size:
        snapshots = rng.sample(corpus, args.state_sample_size)
    else:
        snapshots = corpus

    oracle_records = compare_policies_to_oracle(snapshots, policies, oracle_policy, advisor=advisor)
    grouped_oracle: dict[str, list] = defaultdict(list)
    for record in oracle_records:
        grouped_oracle[record.policy_name].append(record)

    oracle_summary = {
        policy_name: summarize_oracle_results(records)
        for policy_name, records in sorted(grouped_oracle.items())
    }

    _write_full_game_csv(args.output_dir / "full_game_results.csv", full_game_results)
    _write_oracle_csv(args.output_dir / "oracle_comparisons.csv", oracle_records)

    (args.output_dir / "full_game_summary.json").write_text(json.dumps(full_game_summary, indent=2), encoding="utf-8")
    (args.output_dir / "oracle_summary.json").write_text(json.dumps(oracle_summary, indent=2), encoding="utf-8")

    console_summary = {
        "full_games": full_game_summary,
        "oracle_comparison": oracle_summary,
        "state_corpus_size": len(corpus),
        "states_compared": len(snapshots),
    }
    print(json.dumps(console_summary, indent=2))


def _write_full_game_csv(path: Path, results: list) -> None:
    rows = []
    for result in results:
        row = {
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

    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_oracle_csv(path: Path, records: list) -> None:
    rows = [
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
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
