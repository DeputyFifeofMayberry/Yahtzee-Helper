from __future__ import annotations

from dataclasses import asdict

import streamlit as st

from benchmark.page_helpers import (
    STRATEGY_METADATA,
    flatten_full_summary,
    flatten_rollout_reference_summary,
    plan_summary_lines,
    results_takeaway,
    strategy_display_name,
    strategy_summary_rows,
)
from benchmark.run import (
    MODE_PROFILES,
    BenchmarkPlan,
    BenchmarkRunResult,
    BenchmarkSettings,
    execute_benchmark_plan,
    full_game_results_rows,
    plan_benchmark_run,
    rollout_reference_records_rows,
    rows_to_csv,
    summary_to_json,
)

st.set_page_config(page_title="Benchmark Analysis", layout="wide")
st.title("📊 Benchmark Analysis")
st.caption("Fair, reproducible Yahtzee benchmark using common random numbers and rollout-reference move checks.")

MODE_CHOICES = ["Quick", "Balanced", "Deep", "Advanced Custom"]
MODE_TO_KEY = {"Quick": "quick", "Balanced": "balanced", "Deep": "deep", "Advanced Custom": "advanced_custom"}
SETTING_KEYS = {
    "full_games": "bench_full_games",
    "state_sample_games": "bench_state_sample_games",
    "state_sample_size": "bench_state_sample_size",
    "state_sample_rate": "bench_state_sample_rate",
    "rollout_reference_rollouts": "bench_rollout_reference_rollouts",
    "seed": "bench_seed",
}
SESSION_RESULT_KEY = "benchmark_analysis_result"


def _seed_controls_from_settings(settings: BenchmarkSettings) -> None:
    for name, key in SETTING_KEYS.items():
        st.session_state[key] = getattr(settings, name)


def _load_selected_settings() -> BenchmarkSettings:
    return BenchmarkSettings(
        full_games=int(st.session_state[SETTING_KEYS["full_games"]]),
        state_sample_games=int(st.session_state[SETTING_KEYS["state_sample_games"]]),
        state_sample_size=int(st.session_state[SETTING_KEYS["state_sample_size"]]),
        state_sample_rate=float(st.session_state[SETTING_KEYS["state_sample_rate"]]),
        rollout_reference_rollouts=int(st.session_state[SETTING_KEYS["rollout_reference_rollouts"]]),
        seed=int(st.session_state[SETTING_KEYS["seed"]]),
    )


def _result_to_session_payload(result: BenchmarkRunResult) -> dict[str, object]:
    return {
        "settings": asdict(result.settings),
        "plan": asdict(result.plan),
        "full_game_results": full_game_results_rows(result.full_game_results),
        "rollout_reference_records": rollout_reference_records_rows(result.rollout_reference_records),
        "full_game_summary": result.full_game_summary,
        "rollout_reference_summary": result.rollout_reference_summary,
        "run_manifest": result.run_manifest,
        "paired_score_deltas": result.paired_score_deltas,
        "warnings": result.warnings,
        "auto_downgraded_settings": result.auto_downgraded_settings,
    }


if SETTING_KEYS["seed"] not in st.session_state:
    _seed_controls_from_settings(MODE_PROFILES["balanced"])

mode_label = st.selectbox("Mode", MODE_CHOICES)
mode_key = MODE_TO_KEY[mode_label]
include_move_quality = st.toggle("Include move-quality vs rollout reference", value=mode_key in {"balanced", "deep", "advanced_custom"})
include_reference_full_games = st.toggle("Include rollout reference in full-game stage", value=False)
allow_expensive = st.toggle("Allow advanced expensive strategies", value=False)

selected_strategies = st.multiselect(
    "Player strategies to compare",
    options=[k for k, v in STRATEGY_METADATA.items() if not bool(v.get("reference_only"))],
    default=["board_utility", "human_heuristic"],
    format_func=strategy_display_name,
)
st.dataframe(strategy_summary_rows(selected_strategies), use_container_width=True)

with st.expander("Advanced settings"):
    st.number_input("Seed", min_value=0, step=1, key=SETTING_KEYS["seed"])
    st.number_input("Full games per strategy", min_value=1, step=1, key=SETTING_KEYS["full_games"])
    st.number_input("Sample corpus games", min_value=0, step=1, key=SETTING_KEYS["state_sample_games"])
    st.number_input("Sampled state cap", min_value=0, step=1, key=SETTING_KEYS["state_sample_size"])
    st.number_input("Rollout reference rollouts", min_value=0, step=1, key=SETTING_KEYS["rollout_reference_rollouts"])
    st.number_input("State sample rate", min_value=0.01, max_value=1.0, step=0.01, format="%.2f", key=SETTING_KEYS["state_sample_rate"])

settings = _load_selected_settings()
plan: BenchmarkPlan | None = None
try:
    plan = plan_benchmark_run(
        settings=settings,
        mode=mode_key,
        include_move_quality=include_move_quality,
        include_advanced_strategies=allow_expensive,
        include_reference_full_games=include_reference_full_games,
        selected_player_strategies=selected_strategies,
    )
    for line in plan_summary_lines(plan):
        st.markdown(f"- {line}")
    for msg in plan.warnings:
        st.warning(msg)
    for msg in plan.auto_downgraded_settings:
        st.info(f"Auto-adjustment: {msg}")
except ValueError as exc:
    st.error(f"Configuration issue: {exc}")

if st.button("Run benchmark", type="primary", disabled=plan is None) and plan is not None:
    progress = st.progress(0.0, text="Starting")

    def _on_progress(label: str, pct: float) -> None:
        progress.progress(pct, text=label)

    result = execute_benchmark_plan(plan, on_progress=_on_progress)
    st.session_state[SESSION_RESULT_KEY] = _result_to_session_payload(result)

run_data = st.session_state.get(SESSION_RESULT_KEY)
if run_data:
    full_rows = flatten_full_summary(run_data.get("full_game_summary", {}))
    reference_rows = flatten_rollout_reference_summary(run_data.get("rollout_reference_summary", {}))
    st.info(results_takeaway(full_rows, reference_rows))
    st.dataframe(full_rows, use_container_width=True)
    if reference_rows:
        st.dataframe(reference_rows, use_container_width=True)
    st.json({"paired_score_deltas": run_data.get("paired_score_deltas", {}), "run_manifest": run_data.get("run_manifest", {})})

    st.download_button("Download rollout reference rows (CSV)", rows_to_csv(run_data.get("rollout_reference_records", [])), file_name="rollout_reference_comparisons.csv", mime="text/csv")
    st.download_button("Download rollout reference summary (JSON)", summary_to_json(run_data.get("rollout_reference_summary", {})), file_name="rollout_reference_summary.json", mime="application/json")
