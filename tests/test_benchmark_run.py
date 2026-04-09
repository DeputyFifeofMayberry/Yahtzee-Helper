from benchmark.run import (
    BenchmarkSettings,
    full_game_results_rows,
    oracle_records_rows,
    rows_to_csv,
    run_benchmark,
    summary_to_json,
)


def test_run_benchmark_returns_expected_shapes():
    settings = BenchmarkSettings(
        full_games=1,
        oracle_games=1,
        state_sample_games=1,
        state_sample_size=1,
        state_sample_rate=0.5,
        oracle_rollouts=2,
        seed=7,
    )
    result = run_benchmark(settings)

    assert len(result.full_game_results) == 4
    assert set(result.full_game_summary.keys()) == {
        "board_utility",
        "exact_turn_ev",
        "human_heuristic",
        "rollout_oracle",
    }
    assert set(result.oracle_summary.keys()) == {
        "board_utility",
        "exact_turn_ev",
        "human_heuristic",
        "rollout_oracle",
    }


def test_download_rows_and_serializers_are_stable():
    settings = BenchmarkSettings(
        full_games=1,
        oracle_games=1,
        state_sample_games=1,
        state_sample_size=1,
        state_sample_rate=0.5,
        oracle_rollouts=2,
        seed=11,
    )
    result = run_benchmark(settings)

    full_rows = full_game_results_rows(result.full_game_results)
    oracle_rows = oracle_records_rows(result.oracle_records)

    assert full_rows
    assert "final_score" in full_rows[0]
    full_csv = rows_to_csv(full_rows)
    assert "policy_name" in full_csv

    oracle_csv = rows_to_csv(oracle_rows)
    assert "regret" in oracle_csv or oracle_csv == ""

    full_json = summary_to_json(result.full_game_summary)
    oracle_json = summary_to_json(result.oracle_summary)
    assert "average_final_score" in full_json
    assert "oracle_agreement_rate" in oracle_json


def test_invalid_settings_raise_friendly_error():
    bad = BenchmarkSettings(full_games=0)
    try:
        run_benchmark(bad)
    except ValueError as exc:
        assert "full_games" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid benchmark settings.")
