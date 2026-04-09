from benchmark.run import BenchmarkSettings, plan_benchmark_run


def test_heavy_settings_trigger_auto_downgrade_in_browser_safe_mode():
    settings = BenchmarkSettings(full_games=300, state_sample_games=80, state_sample_size=300, oracle_rollouts=60)
    plan = plan_benchmark_run(settings=settings, mode="balanced", include_move_quality=True)
    assert plan.auto_downgraded_settings
    assert plan.settings.full_games <= 60
    assert plan.settings.state_sample_size <= 60


def test_invalid_empty_strategy_selection_raises_error():
    settings = BenchmarkSettings()
    try:
        plan_benchmark_run(settings=settings, mode="advanced_custom", selected_player_strategies=[])
    except ValueError as exc:
        assert "At least one" in str(exc)
    else:
        raise AssertionError("Expected ValueError for empty strategy selection")


def test_move_quality_disabled_resets_oracle_work():
    settings = BenchmarkSettings(state_sample_games=9, state_sample_size=12, oracle_rollouts=8)
    plan = plan_benchmark_run(settings=settings, mode="quick", include_move_quality=False)
    assert not plan.include_move_quality
    assert plan.settings.state_sample_games == 0
