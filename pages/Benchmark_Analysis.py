from __future__ import annotations

from dataclasses import asdict

import streamlit as st

from benchmark.page_helpers import (
    STRATEGY_METADATA,
    flatten_full_summary,
    flatten_oracle_summary,
    plan_summary_lines,
    results_takeaway,
    strategy_display_name,
    strategy_summary_rows,
)
from benchmark.run import (
    MODE_PROFILES,
    BenchmarkRunResult,
    BenchmarkSettings,
    BenchmarkPlan,
    execute_benchmark_plan,
    full_game_results_rows,
    oracle_records_rows,
    plan_benchmark_run,
    rows_to_csv,
    summary_to_json,
)

st.set_page_config(page_title="Strategy Test Lab", layout="wide")

MODE_CHOICES = ["Quick Winner", "Balanced Benchmark", "Deep Dive", "Advanced Custom"]
MODE_TO_KEY = {
    "Quick Winner": "quick",
    "Balanced Benchmark": "balanced",
    "Deep Dive": "deep",
    "Advanced Custom": "advanced_custom",
}

SETTING_KEYS = {
    "full_games": "bench_full_games",
    "oracle_games": "bench_oracle_games",
    "state_sample_games": "bench_state_sample_games",
    "state_sample_size": "bench_state_sample_size",
    "state_sample_rate": "bench_state_sample_rate",
    "oracle_rollouts": "bench_oracle_rollouts",
    "seed": "bench_seed",
}
SESSION_RESULT_KEY = "benchmark_analysis_result"
SESSION_MODE_KEY = "benchmark_analysis_mode"


def _seed_controls_from_settings(settings: BenchmarkSettings) -> None:
    for name, key in SETTING_KEYS.items():
        st.session_state[key] = getattr(settings, name)


def _load_selected_settings() -> BenchmarkSettings:
    return BenchmarkSettings(
        full_games=int(st.session_state[SETTING_KEYS["full_games"]]),
        oracle_games=int(st.session_state[SETTING_KEYS["oracle_games"]]),
        state_sample_games=int(st.session_state[SETTING_KEYS["state_sample_games"]]),
        state_sample_size=int(st.session_state[SETTING_KEYS["state_sample_size"]]),
        state_sample_rate=float(st.session_state[SETTING_KEYS["state_sample_rate"]]),
        oracle_rollouts=int(st.session_state[SETTING_KEYS["oracle_rollouts"]]),
        seed=int(st.session_state[SETTING_KEYS["seed"]]),
    )


def _result_to_session_payload(result: BenchmarkRunResult) -> dict[str, object]:
    return {
        "settings": asdict(result.settings),
        "plan": asdict(result.plan),
        "full_game_results": full_game_results_rows(result.full_game_results),
        "oracle_records": oracle_records_rows(result.oracle_records),
        "full_game_summary": result.full_game_summary,
        "oracle_summary": result.oracle_summary,
        "state_corpus_size": result.state_corpus_size,
        "states_compared": result.states_compared,
        "stage_timings_seconds": result.stage_timings_seconds,
        "warnings": result.warnings,
        "auto_downgraded_settings": result.auto_downgraded_settings,
        "strategies_included": result.strategies_included,
        "strategies_skipped": result.strategies_skipped,
    }


st.title("🎯 Strategy Test Lab")
st.caption("Browser-safe Yahtzee strategy benchmark: quick winner first, deeper evidence second.")

st.info(
    "**What this tool compares**\n\n"
    "- **Score comparison**: full simulated games to compare end scores.\n"
    "- **Move-quality comparison**: sampled decision situations compared against a stronger reference strategy.\n\n"
    "The reference strategy is a **simulated checker**, not a normal human play style."
)

st.success(
    "**Start here**: Most users should choose **Balanced Benchmark**, keep advanced settings unchanged, and run once."
)

with st.expander("How this benchmark works", expanded=False):
    st.markdown(
        "1. Choose a run mode.\n"
        "2. Choose which strategy families to include.\n"
        "3. Run full-game score comparisons.\n"
        "4. Optionally collect sampled decision states.\n"
        "5. Optionally compare each strategy move against the reference rollout strategy.\n"
        "6. Summarize score and move-quality metrics with plain-English takeaways."
    )

if SESSION_MODE_KEY not in st.session_state:
    st.session_state[SESSION_MODE_KEY] = "Balanced Benchmark"
if SETTING_KEYS["seed"] not in st.session_state:
    _seed_controls_from_settings(MODE_PROFILES["balanced"])

with st.container(border=True):
    st.subheader("1) Choose mode and strategy scope")
    selected_mode = st.selectbox("Run mode", MODE_CHOICES, key=SESSION_MODE_KEY)
    mode_key = MODE_TO_KEY[selected_mode]

    if st.button("Apply mode defaults"):
        base = MODE_PROFILES.get(mode_key, MODE_PROFILES["balanced"])
        _seed_controls_from_settings(base)

    c1, c2 = st.columns(2)
    with c1:
        include_move_quality = st.toggle(
            "Run move-quality comparison",
            value=mode_key in {"balanced", "deep", "advanced_custom"},
            help="Compares sampled decisions against a stronger reference strategy.",
        )
    with c2:
        include_reference_full_games = st.toggle(
            "Include reference strategy in full-game scoring",
            value=mode_key == "deep",
            help="Usually leave off for browser speed. Mostly useful for advanced diagnostics.",
        )

    st.subheader("2) Strategy selection")
    allow_expensive = st.toggle(
        "Enable advanced expensive strategies (includes Turn-score maximizer)",
        value=False,
        help="Advanced Custom only. This can slow browser runs significantly.",
    )

    strategy_options = [k for k, v in STRATEGY_METADATA.items() if not bool(v.get("reference_only"))]
    default_selected = ["board_utility", "human_heuristic"]
    selected_strategies = st.multiselect(
        "Player strategies to compare",
        options=strategy_options,
        default=default_selected,
        format_func=strategy_display_name,
    )

    st.caption("What is being compared in this run?")
    st.dataframe(strategy_summary_rows(selected_strategies), use_container_width=True)

    with st.expander("Advanced settings", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.number_input("Seed", min_value=0, step=1, key=SETTING_KEYS["seed"])
            st.number_input("Full games per strategy", min_value=1, step=1, key=SETTING_KEYS["full_games"])
        with c2:
            st.number_input("Reference full games", min_value=0, step=1, key=SETTING_KEYS["oracle_games"])
            st.number_input("Sample corpus games", min_value=0, step=1, key=SETTING_KEYS["state_sample_games"])
        with c3:
            st.number_input("Sampled state cap", min_value=0, step=1, key=SETTING_KEYS["state_sample_size"])
            st.number_input("Reference rollouts", min_value=0, step=1, key=SETTING_KEYS["oracle_rollouts"])
            st.number_input(
                "State sample rate",
                min_value=0.01,
                max_value=1.0,
                step=0.01,
                format="%.2f",
                key=SETTING_KEYS["state_sample_rate"],
            )

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
        st.subheader("3) Pre-run summary")
        for line in plan_summary_lines(plan):
            st.markdown(f"- {line}")
        for msg in plan.warnings:
            st.warning(msg)
        for msg in plan.auto_downgraded_settings:
            st.info(f"Auto-downgrade applied: {msg}")
    except ValueError as exc:
        st.error(f"Configuration issue: {exc}")

    run_clicked = st.button("Run benchmark", type="primary", use_container_width=True, disabled=plan is None)

if run_clicked and plan is not None:
    progress = st.progress(0.0, text="Starting run...")
    with st.status("Run in progress", expanded=True) as status:

        def _on_progress(label: str, pct: float) -> None:
            progress.progress(pct, text=label)
            status.write(f"{int(pct * 100)}% — {label}")

        result = execute_benchmark_plan(plan=plan, on_progress=_on_progress)
        st.session_state[SESSION_RESULT_KEY] = _result_to_session_payload(result)
        status.update(label="Run complete", state="complete", expanded=False)
        progress.progress(1.0, text="Run complete")

run_data = st.session_state.get(SESSION_RESULT_KEY)
if not run_data:
    st.warning("No run results yet.")
else:
    full_rows = flatten_full_summary(run_data.get("full_game_summary", {}))
    oracle_rows = flatten_oracle_summary(run_data.get("oracle_summary", {}))

    st.header("Quick answer")
    st.info(results_takeaway(full_rows, oracle_rows))

    st.markdown("**How this conclusion was reached**")
    st.markdown(
        "- Best overall scorer: highest **Average Final Score**.\n"
        "- Most consistent scorer: highest **Low-end Score (P10)**.\n"
        "- Best move-quality agreement: highest **Matched Best-Known Choice**."
    )

    st.subheader("Beginner summary table")
    simple_view = []
    for row in full_rows:
        oracle_row = next((item for item in oracle_rows if item["Strategy Key"] == row["Strategy Key"]), None)
        simple_view.append(
            {
                "Strategy": row["Strategy"],
                "Purpose": STRATEGY_METADATA.get(row["Strategy Key"], {}).get("purpose", ""),
                "Average Final Score": row["Average Final Score"],
                "Low-end Score (P10)": row["Low-end Score (P10)"],
                "Matched Best-Known Choice": 0.0
                if not oracle_row
                else oracle_row["Matched Best-Known Choice (oracle agreement rate)"],
            }
        )
    st.dataframe(simple_view, use_container_width=True)

    st.subheader("Run metadata")
    st.json(
        {
            "strategies_included": run_data.get("strategies_included", []),
            "strategies_skipped": run_data.get("strategies_skipped", []),
            "stage_timings_seconds": run_data.get("stage_timings_seconds", {}),
            "warnings": run_data.get("warnings", []),
            "auto_downgraded_settings": run_data.get("auto_downgraded_settings", []),
        }
    )

    with st.expander("Advanced detail", expanded=False):
        st.subheader("Full score comparison")
        st.dataframe(full_rows, use_container_width=True)
        st.subheader("Move-quality comparison")
        if oracle_rows:
            st.dataframe(oracle_rows, use_container_width=True)
        else:
            st.caption("Move-quality stage was not enabled or was skipped by safety guardrails.")

    with st.expander("Downloads", expanded=False):
        st.download_button(
            "Download full game rows (CSV)",
            rows_to_csv(run_data.get("full_game_results", [])),
            file_name="full_game_results.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download decision comparison rows (CSV)",
            rows_to_csv(run_data.get("oracle_records", [])),
            file_name="oracle_comparisons.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download full game summary (JSON)",
            summary_to_json(run_data.get("full_game_summary", {})),
            file_name="full_game_summary.json",
            mime="application/json",
        )
        st.download_button(
            "Download decision summary (JSON)",
            summary_to_json(run_data.get("oracle_summary", {})),
            file_name="oracle_summary.json",
            mime="application/json",
        )