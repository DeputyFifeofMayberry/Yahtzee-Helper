from __future__ import annotations

from dataclasses import asdict

from benchmark.run import BenchmarkSettings, estimate_run_cost


def settings_equal(a: BenchmarkSettings, b: BenchmarkSettings) -> bool:
    return asdict(a) == asdict(b)


def preset_name_for_settings(settings: BenchmarkSettings, presets: dict[str, BenchmarkSettings]) -> str:
    for preset_name, preset_settings in presets.items():
        if settings_equal(settings, preset_settings):
            return preset_name
    return "Custom (edited)"


def flatten_full_summary(summary: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for policy_name, metrics in sorted(summary.items()):
        rows.append(
            {
                "Strategy": policy_name,
                "Games Played": metrics.get("games", 0),
                "Average Final Score": metrics.get("average_final_score", 0.0),
                "Median Final Score": metrics.get("median_final_score", 0.0),
                "Low-end Score (P10)": metrics.get("p10_final_score", 0.0),
                "High-end Score (P90)": metrics.get("p90_final_score", 0.0),
                "Upper Bonus Hit Rate": metrics.get("upper_bonus_hit_rate", 0.0),
                "Yahtzee Rate": metrics.get("yahtzee_rate", 0.0),
                "Extra Yahtzee Bonus Rate": metrics.get("extra_yahtzee_bonus_rate", 0.0),
                "Average Zeros per Game": metrics.get("average_zeros_per_game", 0.0),
            }
        )
    return rows


def flatten_oracle_summary(summary: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for policy_name, metrics in sorted(summary.items()):
        rows.append(
            {
                "Strategy": policy_name,
                "Sampled Test States": metrics.get("comparisons", 0),
                "Matched Best-Known Choice (oracle agreement rate)": metrics.get("oracle_agreement_rate", 0.0),
                "Average Points Lost vs Best-Known Choice (regret)": metrics.get("average_regret", 0.0),
                "Median Points Lost": metrics.get("median_regret", 0.0),
                "High-end Points Lost (P90)": metrics.get("p90_regret", 0.0),
            }
        )
    return rows


def settings_summary_text(settings: BenchmarkSettings) -> tuple[str, str]:
    speed, full_games, sampled_states = estimate_run_cost(settings)
    run_text = (
        f"This run will simulate about {full_games} full games and compare about {sampled_states} decision snapshots."
    )
    return run_text, f"Estimated run cost: **{speed}**."


def results_takeaway(full_rows: list[dict[str, object]], oracle_rows: list[dict[str, object]]) -> str:
    if not full_rows:
        return "No results yet."

    score_winner = max(full_rows, key=lambda row: float(row.get("Average Final Score", 0.0)))
    consistent = max(full_rows, key=lambda row: float(row.get("Low-end Score (P10)", 0.0)))

    if oracle_rows:
        match_winner = max(
            oracle_rows,
            key=lambda row: float(row.get("Matched Best-Known Choice (oracle agreement rate)", 0.0)),
        )
        return (
            f"{score_winner['Strategy']} scored highest overall, {consistent['Strategy']} had the strongest low-end scores, "
            f"and {match_winner['Strategy']} most often matched the best-known choice."
        )

    return (
        f"{score_winner['Strategy']} scored highest overall, and {consistent['Strategy']} was the most consistent. "
        "Best-known-choice matching was skipped in this fast run."
    )
