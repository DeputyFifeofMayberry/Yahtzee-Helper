from __future__ import annotations

from dataclasses import asdict

import streamlit as st

from benchmark.run import (
    BenchmarkRunResult,
    BenchmarkSettings,
    full_game_results_rows,
    oracle_records_rows,
    rows_to_csv,
    run_benchmark,
    summary_to_json,
)

st.set_page_config(page_title="Benchmark Analysis", layout="wide")

PRESETS: dict[str, BenchmarkSettings] = {
    "Quick": BenchmarkSettings(
        full_games=40,
        oracle_games=12,
        state_sample_games=16,
        state_sample_size=36,
        state_sample_rate=0.2,
        oracle_rollouts=12,
        seed=1337,
    ),
    "Standard": BenchmarkSettings(
        full_games=100,
        oracle_games=24,
        state_sample_games=36,
        state_sample_size=72,
        state_sample_rate=0.3,
        oracle_rollouts=24,
        seed=1337,
    ),
    "Deep": BenchmarkSettings(
        full_games=220,
        oracle_games=50,
        state_sample_games=65,
        state_sample_size=120,
        state_sample_rate=0.4,
        oracle_rollouts=45,
        seed=1337,
    ),
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


def _collect_policies(run_data: dict[str, object]) -> list[str]:
    full_keys = set((run_data.get("full_game_summary") or {}).keys())
    oracle_keys = set((run_data.get("oracle_summary") or {}).keys())
    return sorted(full_keys | oracle_keys)


st.title("📊 Benchmark Analysis")
st.caption("Run policy benchmarks in-browser and inspect full-game plus oracle-comparison performance.")

if SESSION_PRESET_KEY not in st.session_state:
    st.session_state[SESSION_PRESET_KEY] = "Quick"
    _seed_controls_from_settings(PRESETS["Quick"])

with st.container(border=True):
    st.subheader("Benchmark Controls")
    preset = st.selectbox("Preset", ["Quick", "Standard", "Deep", "Custom"], key=SESSION_PRESET_KEY)

    if preset != "Custom":
        _seed_controls_from_settings(PRESETS[preset])

    disabled = preset != "Custom"
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.number_input("Full games", min_value=1, step=1, key=SETTING_KEYS["full_games"], disabled=disabled)
        st.number_input("Oracle games", min_value=1, step=1, key=SETTING_KEYS["oracle_games"], disabled=disabled)
    with c2:
        st.number_input("State sample games", min_value=1, step=1, key=SETTING_KEYS["state_sample_games"], disabled=disabled)
        st.number_input("State sample size", min_value=1, step=1, key=SETTING_KEYS["state_sample_size"], disabled=disabled)
    with c3:
        st.number_input(
            "State sample rate",
            min_value=0.01,
            max_value=1.0,
            step=0.01,
            format="%.2f",
            key=SETTING_KEYS["state_sample_rate"],
            disabled=disabled,
        )
        st.number_input("Oracle rollouts", min_value=1, step=1, key=SETTING_KEYS["oracle_rollouts"], disabled=disabled)
    with c4:
        st.number_input("Seed", min_value=0, step=1, key=SETTING_KEYS["seed"])

    st.info(
        "Runtime note: rollout_oracle is intentionally expensive. Larger oracle rollouts and sample sizes can be much slower. "
        "For browser use, Quick or Standard presets are usually best."
    )

    run_clicked = st.button("Run Benchmark", type="primary", use_container_width=True)

if run_clicked:
    try:
        settings = _load_selected_settings()
        progress = st.progress(0.0, text="Starting benchmark...")
        with st.status("Benchmark in progress", expanded=True) as status:

            def _on_progress(label: str, pct: float) -> None:
                progress.progress(pct, text=label)
                status.write(f"{int(pct * 100)}% — {label}")

            result = run_benchmark(settings, on_progress=_on_progress)

            st.session_state[SESSION_RESULT_KEY] = _result_to_session_payload(result)
            status.update(label="Benchmark completed", state="complete", expanded=False)
            progress.progress(1.0, text="Benchmark completed")
    except ValueError as exc:
        st.error(f"Unable to run benchmark: {exc}")

run_data = st.session_state.get(SESSION_RESULT_KEY)
if not run_data:
    st.warning("No benchmark results yet. Configure settings above and run a benchmark.")
    st.stop()

st.success(
    f"Loaded results for settings: {run_data['settings']} | state corpus={run_data['state_corpus_size']} | "
    f"states compared={run_data['states_compared']}"
)

full_summary = run_data.get("full_game_summary", {})
oracle_summary = run_data.get("oracle_summary", {})
policies = _collect_policies(run_data)

st.header("Executive Summary")
exec_rows: list[dict[str, float | str]] = []
for policy_name in policies:
    game = full_summary.get(policy_name)
    oracle = oracle_summary.get(policy_name)
    exec_rows.append(
        {
            "policy": policy_name,
            "avg_final_score": _safe_metric(game, "average_final_score"),
            "median_final_score": _safe_metric(game, "median_final_score"),
            "p90_final_score": _safe_metric(game, "p90_final_score"),
            "upper_bonus_hit_rate": _safe_metric(game, "upper_bonus_hit_rate"),
            "yahtzee_rate": _safe_metric(game, "yahtzee_rate"),
            "avg_zeros_per_game": _safe_metric(game, "average_zeros_per_game"),
            "oracle_agreement_rate": _safe_metric(oracle, "oracle_agreement_rate"),
            "avg_regret": _safe_metric(oracle, "average_regret"),
        }
    )
st.dataframe(exec_rows, use_container_width=True)

st.header("Charts")
chart_cols = st.columns(2)
with chart_cols[0]:
    st.caption("Average final score by policy")
    st.bar_chart({row["policy"]: row["avg_final_score"] for row in exec_rows})
    st.caption("Upper bonus hit rate by policy")
    st.bar_chart({row["policy"]: row["upper_bonus_hit_rate"] for row in exec_rows})
    st.caption("Yahtzee rate by policy")
    st.bar_chart({row["policy"]: row["yahtzee_rate"] for row in exec_rows})
with chart_cols[1]:
    st.caption("Oracle agreement rate by policy")
    st.bar_chart({row["policy"]: row["oracle_agreement_rate"] for row in exec_rows})
    st.caption("Average regret by policy")
    st.bar_chart({row["policy"]: row["avg_regret"] for row in exec_rows})

st.header("Full-game Performance")
st.dataframe(full_summary, use_container_width=True)
with st.expander("Full-game details"):
    for policy_name in policies:
        summary = full_summary.get(policy_name)
        if not summary:
            continue
        st.subheader(policy_name)
        metric_cols = st.columns(4)
        metric_cols[0].metric("P10 / P90", f"{summary.get('p10_final_score', 0)} / {summary.get('p90_final_score', 0)}")
        metric_cols[1].metric("Min / Max", f"{summary.get('min_final_score', 0)} / {summary.get('max_final_score', 0)}")
        metric_cols[2].metric("Avg upper subtotal", f"{summary.get('average_upper_subtotal', 0)}")
        metric_cols[3].metric("Extra Yahtzee bonus rate", f"{summary.get('extra_yahtzee_bonus_rate', 0):.1%}")
        st.caption("Zero rate by category")
        st.dataframe(summary.get("zero_rate_by_category", {}), use_container_width=True)
        st.caption("Average score by category")
        st.dataframe(summary.get("average_score_by_category", {}), use_container_width=True)

st.header("Oracle Comparison")
if not oracle_summary:
    st.warning("No oracle comparison rows were generated for this run.")
else:
    st.dataframe(oracle_summary, use_container_width=True)
    with st.expander("Oracle details and slices"):
        for policy_name in policies:
            summary = oracle_summary.get(policy_name)
            if not summary:
                continue
            st.subheader(policy_name)
            mcols = st.columns(3)
            mcols[0].metric("Agreement", f"{_safe_metric(summary, 'oracle_agreement_rate'):.1%}")
            mcols[1].metric("Avg regret", f"{_safe_metric(summary, 'average_regret'):.3f}")
            mcols[2].metric("Median / P90 regret", f"{_safe_metric(summary, 'median_regret'):.3f} / {_safe_metric(summary, 'p90_regret'):.3f}")
            mcols2 = st.columns(2)
            mcols2[0].metric("Severe miss >3", f"{_safe_metric(summary, 'severe_miss_rate_gt_3'):.1%}")
            mcols2[1].metric("Severe miss >5", f"{_safe_metric(summary, 'severe_miss_rate_gt_5'):.1%}")

            st.caption("By roll number")
            st.dataframe(summary.get("by_roll_number", {}), use_container_width=True)

            st.caption("By tag / state type")
            st.dataframe(summary.get("by_tag", {}), use_container_width=True)

st.header("Downloads")
full_rows = run_data.get("full_game_results", [])
oracle_rows = run_data.get("oracle_records", [])

download_cols = st.columns(4)
download_cols[0].download_button(
    "Download full-game CSV",
    data=rows_to_csv(full_rows),
    file_name="full_game_results.csv",
    mime="text/csv",
)
download_cols[1].download_button(
    "Download oracle CSV",
    data=rows_to_csv(oracle_rows),
    file_name="oracle_comparisons.csv",
    mime="text/csv",
)
download_cols[2].download_button(
    "Download full-game summary JSON",
    data=summary_to_json(full_summary),
    file_name="full_game_summary.json",
    mime="application/json",
)
download_cols[3].download_button(
    "Download oracle summary JSON",
    data=summary_to_json(oracle_summary),
    file_name="oracle_summary.json",
    mime="application/json",
)

with st.expander("Raw full-game result rows"):
    st.dataframe(full_rows, use_container_width=True)

with st.expander("Raw oracle comparison rows"):
    if oracle_rows:
        st.dataframe(oracle_rows, use_container_width=True)
    else:
        st.info("This run produced no oracle comparison rows.")
