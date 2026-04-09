from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from benchmark.metrics import summarize_rollout_reference_results
from benchmark.models import GameSimulationResult, RolloutReferenceComparisonRecord
from benchmark.policies import HumanHeuristicPolicy, ObjectivePolicy
from benchmark.run import BenchmarkSettings, execute_benchmark_plan, plan_benchmark_run, rollout_reference_records_rows
from benchmark.simulator import sample_state_corpus
from yahtzee.models import OptimizationObjective


def test_reproducible_across_subprocess_and_pythonhashseed(tmp_path: Path):
    script = tmp_path / "repro.py"
    script.write_text(
        """
import json
from benchmark.run import BenchmarkSettings, plan_benchmark_run, execute_benchmark_plan, full_game_results_rows
settings = BenchmarkSettings(full_games=1, state_sample_games=0, state_sample_size=0, rollout_reference_rollouts=0, seed=42)
plan = plan_benchmark_run(settings=settings, mode='quick', include_move_quality=False, selected_player_strategies=['human_heuristic'])
result = execute_benchmark_plan(plan)
print(json.dumps({'full': full_game_results_rows(result.full_game_results)}, sort_keys=True))
""",
        encoding="utf-8",
    )

    outputs = []
    repo_root = Path(__file__).resolve().parents[1]
    for hash_seed in ("1", "999"):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = hash_seed
        env["PYTHONPATH"] = str(repo_root)
        proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, check=True, env=env, cwd=repo_root)
        outputs.append(proc.stdout.strip())
    assert outputs[0] == outputs[1]


def test_cli_documented_example_runs(tmp_path: Path):
    out_dir = tmp_path / "out"
    cmd = [
        sys.executable,
        "scripts/run_benchmarks.py",
        "--mode",
        "quick",
        "--skip-move-quality",
        "--full-games",
        "1",
        "--strategies",
        "human_heuristic",
        "--output-dir",
        str(out_dir),
    ]
    subprocess.run(cmd, check=True, cwd=Path(__file__).resolve().parents[1])
    assert (out_dir / "run_manifest.json").exists()


def test_full_game_comparison_uses_common_seed_identities(monkeypatch):
    settings = BenchmarkSettings(full_games=3, state_sample_games=0, state_sample_size=0, rollout_reference_rollouts=0, seed=10)
    plan = plan_benchmark_run(settings=settings, mode="advanced_custom", include_move_quality=False, selected_player_strategies=["board_utility", "human_heuristic"])

    def fake_sim(policy, seed, advisor=None, state_sample_rate=0.0, game_id=-1, shared_seed_id=-1, provenance_source="full_game_run"):
        return GameSimulationResult(
            policy_name=policy.name,
            seed=seed,
            game_id=game_id,
            shared_seed_id=shared_seed_id,
            final_score=100,
            upper_bonus_hit=False,
            upper_subtotal=0,
            yahtzee_scored=False,
            yahtzee_bonus_count=0,
            category_scores={},
            zeroed_categories=(),
        )

    monkeypatch.setattr("benchmark.run.simulate_full_game", fake_sim)
    result = execute_benchmark_plan(plan)
    by_policy: dict[str, set[int]] = {}
    for row in result.full_game_results:
        by_policy.setdefault(row.policy_name, set()).add(row.shared_seed_id)
    assert by_policy["board_utility"] == by_policy["human_heuristic"] == {0, 1, 2}


def test_neutral_corpus_is_deterministic_and_policy_order_independent():
    p1 = ObjectivePolicy("board_utility", OptimizationObjective.BOARD_UTILITY)
    p2 = HumanHeuristicPolicy()
    corpus_a = sample_state_corpus(corpus_mode="neutral_canonical", policies=[p1, p2], canonical_policy=p1, games_per_policy=0, seed=7)
    corpus_b = sample_state_corpus(corpus_mode="neutral_canonical", policies=[p2, p1], canonical_policy=p1, games_per_policy=0, seed=7)
    assert corpus_a == corpus_b == []


def test_small_sample_contains_caution_metadata():
    records = [
        RolloutReferenceComparisonRecord(
            policy_name="human_heuristic",
            snapshot_id="s1",
            provenance_source="neutral_canonical",
            provenance_seed=1,
            provenance_game_id=1,
            provenance_policy="board_utility",
            dice=(1, 1, 2, 3, 4),
            turn_index=3,
            roll_number=2,
            score_signature="{}",
            policy_action="hold:1,1",
            reference_action="score:chance",
            matched_rollout_reference=False,
            estimated_policy_value=15.0,
            estimated_reference_value=18.0,
            estimated_regret_vs_reference=3.0,
            evaluation_rollouts=8,
            tags=("roll_2",),
        )
    ]
    summary = summarize_rollout_reference_results(records)
    assert "cautions" in summary
    assert summary["cautions"]


def test_output_rows_include_audit_fields():
    rows = rollout_reference_records_rows(
        [
            RolloutReferenceComparisonRecord(
                policy_name="human_heuristic",
                snapshot_id="snap-1",
                provenance_source="neutral_canonical",
                provenance_seed=1,
                provenance_game_id=2,
                provenance_policy="board_utility",
                dice=(1, 2, 3, 4, 5),
                turn_index=5,
                roll_number=2,
                score_signature="sig",
                policy_action="hold:1,2",
                reference_action="score:small_straight",
                matched_rollout_reference=False,
                estimated_policy_value=10.0,
                estimated_reference_value=12.0,
                estimated_regret_vs_reference=2.0,
                evaluation_rollouts=16,
                tags=("phase_mid",),
            )
        ]
    )
    required = {
        "snapshot_id",
        "provenance_source",
        "dice",
        "roll_number",
        "turn_index",
        "score_signature",
        "policy_action",
        "reference_action",
        "matched_rollout_reference",
        "estimated_policy_value",
        "estimated_reference_value",
        "estimated_regret_vs_reference",
        "evaluation_rollouts",
    }
    assert required.issubset(set(rows[0].keys()))


def test_dead_oracle_games_setting_removed():
    settings = BenchmarkSettings()
    assert not hasattr(settings, "oracle_games")


def test_browser_safe_downgrade_recorded_in_manifest(monkeypatch):
    settings = BenchmarkSettings(full_games=300, state_sample_games=100, state_sample_size=200, rollout_reference_rollouts=100)
    plan = plan_benchmark_run(settings=settings, mode="balanced", include_move_quality=False)

    def fake_sim(policy, seed, advisor=None, state_sample_rate=0.0, game_id=-1, shared_seed_id=-1, provenance_source="full_game_run"):
        return GameSimulationResult(
            policy_name=policy.name,
            seed=seed,
            game_id=game_id,
            shared_seed_id=shared_seed_id,
            final_score=100,
            upper_bonus_hit=False,
            upper_subtotal=0,
            yahtzee_scored=False,
            yahtzee_bonus_count=0,
            category_scores={},
            zeroed_categories=(),
        )

    monkeypatch.setattr("benchmark.run.simulate_full_game", fake_sim)
    result = execute_benchmark_plan(plan)
    assert result.auto_downgraded_settings
    assert result.run_manifest["auto_adjustments"]
    assert result.run_manifest["effective_settings"]["full_games"] <= 80
