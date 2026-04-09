from benchmark.run import BenchmarkSettings, plan_benchmark_run, profile_settings


def test_browser_safe_default_excludes_exact_turn_ev():
    settings = profile_settings("balanced", seed=5)
    plan = plan_benchmark_run(settings=settings, mode="balanced")
    assert "exact_turn_ev" not in plan.strategies_included
    assert "board_utility" in plan.strategies_included
    assert "human_heuristic" in plan.strategies_included


def test_advanced_mode_can_include_exact_turn_ev():
    settings = profile_settings("balanced", seed=5)
    plan = plan_benchmark_run(
        settings=settings,
        mode="advanced_custom",
        include_advanced_strategies=True,
        selected_player_strategies=["board_utility", "exact_turn_ev", "human_heuristic"],
    )
    assert "exact_turn_ev" in plan.strategies_included


def test_plan_contains_runtime_metadata_fields():
    settings = BenchmarkSettings(full_games=2, state_sample_games=0, state_sample_size=0, oracle_rollouts=0)
    plan = plan_benchmark_run(settings=settings, mode="balanced", include_move_quality=False)
    assert isinstance(plan.workload, dict)
    assert "full_game_simulations" in plan.workload
