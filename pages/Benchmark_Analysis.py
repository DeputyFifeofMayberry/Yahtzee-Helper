from __future__ import annotations

from dataclasses import asdict

import streamlit as st

from benchmark.page_helpers import (
    flatten_full_summary,
    flatten_oracle_summary,
    preset_name_for_settings,
    results_takeaway,
    settings_summary_text,
)
from benchmark.run import (
    MODE_PROFILES,
    BenchmarkRunResult,
    BenchmarkSettings,
    browser_guardrail_warnings,
    full_game_results_rows,
    oracle_records_rows,
    rows_to_csv,
    run_benchmark,
    summary_to_json,
)

st.set_page_config(page_title="Strategy Test Lab", layout="wide")

PRESETS: dict[str, BenchmarkSettings] = {
    "Fast Check": MODE_PROFILES["fast"],
    "Standard Comparison": MODE_PROFILES["standard"],
    "Deep Analysis": MODE_PROFILES["deep"],
}

PRESET_OPTIONS = ["Fast Check", "Standard Comparison", "Deep Analysis", "Custom (edited)"]

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
SESSION_PRESET_KEY = "benchmark_analysis_preset"


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
        "full_game_results": full_game_results_rows(result.full_game_results),
        "oracle_records": oracle_records_rows(result.oracle_records),
        "full_game_summary": result.full_game_summary,
        "oracle_summary": result.oracle_summary,
        "state_corpus_size": result.state_corpus_size,
        "states_compared": result.states_compared,
    }


def _safe_metric(summary: dict[str, object] | None, key: str) -> float:
    if not summary:
        return 0.0
    value = summary.get(key, 0.0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


st.title("🎯 Strategy Test Lab")
st.caption("Compare Yahtzee strategies with a fast browser-friendly check or a deeper analysis run.")

st.info(
    "**How to read this page**\n\n"
    "- Higher **Average Final Score** is better.\n"
    "- Higher **Matched Best-Known Choice** percentage is better.\n"
    "- Lower **Average Points Lost vs Best-Known Choice** is better.\n"
    "- **Fast Check** is for quick feedback; deeper modes take much longer."
)

if SESSION_PRESET_KEY not in st.session_state:
    st.session_state[SESSION_PRESET_KEY] = "Fast Check"
    _seed_controls_from_settings(PRESETS["Fast Check"])

with st.container(border=True):
    st.subheader("Run Settings")
    st.markdown("**Basic settings**")

    selected_preset = st.selectbox("Preset", PRESET_OPTIONS, key=SESSION_PRESET_KEY)
    if selected_preset in PRESETS:
        _seed_controls_from_settings(PRESETS[selected_preset])

    basic_cols = st.columns(2)
    with basic_cols[0]:
        st.number_input("Seed", min_value=0, step=1, key=SETTING_KEYS["seed"])
    with basic_cols[1]:
        st.caption("Run Type")
        st.write(selected_preset)

    with st.expander("Advanced settings", expanded=False):
        st.markdown("**Advanced settings**")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.number_input("Full games", min_value=1, step=1, key=SETTING_KEYS["full_games"])
            st.number_input("Oracle games", min_value=0, step=1, key=SETTING_KEYS["oracle_games"])
        with c2:
            st.number_input("State sample games", min_value=0, step=1, key=SETTING_KEYS["state_sample_games"])
            st.number_input("State sample size", min_value=0, step=1, key=SETTING_KEYS["state_sample_size"])
        with c3:
            st.number_input(
                "State sample rate",
                min_value=0.01,
                max_value=1.0,
                step=0.01,
                format="%.2f",
                key=SETTING_KEYS["state_sample_rate"],
            )
            st.number_input("Oracle rollouts", min_value=0, step=1, key=SETTING_KEYS["oracle_rollouts"])

    settings = _load_selected_settings()
    derived_preset = preset_name_for_settings(settings, PRESETS)
    st.session_state[SESSION_PRESET_KEY] = derived_preset

    run_text, cost_text = settings_summary_text(settings)
    st.caption(run_text)
    st.caption(cost_text)

    for warning in browser_guardrail_warnings(settings):
        st.warning(warning)

    run_clicked = st.button("Run Strategy Comparison", type="primary", use_container_width=True)

if run_clicked:
    try:
        settings = _load_selected_settings()
        progress = st.progress(0.0, text="Starting run...")
        with st.status("Run in progress", expanded=True) as status:

            def _on_progress(label: str, pct: float) -> None:
                progress.progress(pct, text=label)
                status.write(f"{int(pct * 100)}% — {label}")

            mode = "deep"
            if settings == PRESETS["Fast Check"]:
                mode = "fast"
            elif settings == PRESETS["Standard Comparison"]:
                mode = "standard"

            result = run_benchmark(settings, on_progress=_on_progress, mode=mode)
            st.session_state[SESSION_RESULT_KEY] = _result_to_session_payload(result)
            status.update(label="Run complete", state="complete", expanded=False)
            progress.progress(1.0, text="Run complete")
    except ValueError as exc:
        st.error(f"Unable to run benchmark: {exc}")

run_data = st.session_state.get(SESSION_RESULT_KEY)
if not run_data:
    st.warning("No run results yet. Configure settings above and run a strategy comparison.")
    st.stop()

st.success(
    f"Loaded run with sampled test states: {run_data['states_compared']} out of {run_data['state_corpus_size']} captured states."
)

full_summary = run_data.get("full_game_summary", {})
oracle_summary = run_data.get("oracle_summary", {})
full_rows = flatten_full_summary(full_summary)
oracle_rows = flatten_oracle_summary(oracle_summary)

st.header("Best Overall Results")
st.info(results_takeaway(full_rows, oracle_rows))

simple_view = []
for row in full_rows:
    oracle_row = next((item for item in oracle_rows if item["Strategy"] == row["Strategy"]), None)
    simple_view.append(
        {
            "Strategy": row["Strategy"],
            "Average Final Score": row["Average Final Score"],
            "Most Consistent (Low-end Score P10)": row["Low-end Score (P10)"],
            "Matched Best-Known Choice": 0.0 if not oracle_row else oracle_row["Matched Best-Known Choice (oracle agreement rate)"],
            "Average Points Lost vs Best-Known Choice": 0.0 if not oracle_row else oracle_row[
                "Average Points Lost vs Best-Known Choice (regret)"
            ],
        }
    )
st.dataframe(simple_view, use_container_width=True)

st.header("How Each Strategy Scored")
st.dataframe(full_rows, use_container_width=True)

if oracle_rows:
    st.header("How Often Each Strategy Matched the Best Known Choice")
    st.caption(
        "Matched Best-Known Choice (oracle agreement rate): share of sampled test states where the strategy picked "
        "the same action as the best-known reference."
    )
    st.caption(
        "Average Points Lost vs Best-Known Choice (regret): average score difference compared with the best-known "
        "choice on sampled states. Lower is better."
    )
    st.caption("Low-end / High-end Score Range: P10/P90 shows typical worst-case and strong-case outcomes.")
    st.caption("Sampled test states: number of in-game decisions used in the best-known-choice comparison.")
    st.dataframe(oracle_rows, use_container_width=True)
else:
    st.info("This run skipped best-known-choice comparison to keep the run fast.")

with st.expander("Detailed strategy metrics", expanded=False):
    for policy_name, summary in sorted(full_summary.items()):
        st.subheader(policy_name)
        metric_cols = st.columns(3)
        metric_cols[0].metric(
            "Low-end / High-end Score Range",
            f"{summary.get('p10_final_score', 0)} / {summary.get('p90_final_score', 0)}",
            help="This shows a practical low-end and high-end score range, not the absolute min and max.",
        )
        metric_cols[1].metric(
            "Extra Yahtzee bonus rate",
            f"{summary.get('extra_yahtzee_bonus_rate', 0):.1%}",
            help="How often a game earned at least one extra Yahtzee bonus.",
        )
        metric_cols[2].metric(
            "Average zeros per game",
            f"{summary.get('average_zeros_per_game', 0):.2f}",
            help="Average number of boxes that ended up as zero in a completed game.",
        )

        zero_rows = [
            {"Category": category, "How Often This Box Ended Up as 0": rate}
            for category, rate in sorted(summary.get("zero_rate_by_category", {}).items())
        ]
        score_rows = [
            {"Category": category, "Average Score": score}
            for category, score in sorted(summary.get("average_score_by_category", {}).items())
        ]
        st.caption("How Often This Box Ended Up as 0")
        st.dataframe(zero_rows, use_container_width=True)
        st.caption("Average Score by Category")
        st.dataframe(score_rows, use_container_width=True)

with st.expander("Detailed Decision Comparison Data", expanded=False):
    if not oracle_summary:
        st.caption("No detailed decision comparison data for this run.")
    for policy_name, summary in sorted(oracle_summary.items()):
        st.subheader(policy_name)
        mcols = st.columns(3)
        mcols[0].metric(
            "Matched Best-Known Choice (oracle agreement rate)",
            f"{_safe_metric(summary, 'oracle_agreement_rate'):.1%}",
            help="How often this strategy picked the same move as the best-known reference.",
        )
        mcols[1].metric(
            "Average Points Lost vs Best-Known Choice (regret)",
            f"{_safe_metric(summary, 'average_regret'):.3f}",
            help="Average points lost compared with the best-known move in sampled situations.",
        )
        mcols[2].metric("Sampled test states", int(_safe_metric(summary, "comparisons")))

        by_roll_rows = []
        for roll_name, values in sorted((summary.get("by_roll_number") or {}).items()):
            by_roll_rows.append(
                {
                    "Roll": roll_name,
                    "Matched Best-Known Choice": values.get("oracle_agreement_rate", 0.0),
                    "Average Points Lost": values.get("average_regret", 0.0),
                    "High-end Points Lost (P90)": values.get("p90_regret", 0.0),
                    "Samples": values.get("count", 0.0),
                }
            )
        st.caption("Breakdown by Roll Number")
        st.dataframe(by_roll_rows, use_container_width=True)

        by_tag_rows = []
        for tag, values in sorted((summary.get("by_tag") or {}).items()):
            by_tag_rows.append(
                {
                    "State Type": tag,
                    "Matched Best-Known Choice": values.get("oracle_agreement_rate", 0.0),
                    "Average Points Lost": values.get("average_regret", 0.0),
                    "High-end Points Lost (P90)": values.get("p90_regret", 0.0),
                    "Samples": values.get("count", 0.0),
                }
            )
        st.caption("Breakdown by State Type")
        st.dataframe(by_tag_rows, use_container_width=True)

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
        summary_to_json(full_summary),
        file_name="full_game_summary.json",
        mime="application/json",
    )
    st.download_button(
        "Download decision summary (JSON)",
        summary_to_json(oracle_summary),
        file_name="oracle_summary.json",
        mime="application/json",
    )
