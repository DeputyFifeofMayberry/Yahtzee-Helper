from benchmark.run import BenchmarkSettings, execute_benchmark_plan, plan_benchmark_run


def test_progress_callback_emits_stage_aware_updates_for_score_stage():
    settings = BenchmarkSettings(
        full_games=1,
        oracle_games=0,
        state_sample_games=0,
        state_sample_size=0,
        state_sample_rate=0.2,
        oracle_rollouts=0,
        seed=3,
    )
    plan = plan_benchmark_run(settings=settings, mode="quick", include_move_quality=False)
    labels: list[str] = []

    def on_progress(label: str, _: float) -> None:
        labels.append(label)

    execute_benchmark_plan(plan, on_progress=on_progress)
    assert any("Stage 1/4" in label for label in labels)
    assert any("Stage 2/4 skipped" in label for label in labels)
    assert labels[-1] == "Done"
