from __future__ import annotations

from dataclasses import asdict

from .run import BenchmarkPlan, BenchmarkSettings, estimate_run_cost


STRATEGY_METADATA: dict[str, dict[str, object]] = {
    "board_utility": {
        "display_name": "Board-aware strategy",
        "description": "Balances immediate points with board flexibility for later turns.",
        "speed_cost": "Medium",
        "purpose": "General-purpose scorer",
        "browser_safe_default": True,
        "reference_only": False,
    },
    "exact_turn_ev": {
        "display_name": "Turn-score maximizer (advanced)",
        "description": "Optimizes immediate turn EV and is computationally expensive.",
        "speed_cost": "Very high",
        "purpose": "Advanced diagnostic strategy",
        "browser_safe_default": False,
        "reference_only": False,
    },
    "human_heuristic": {
        "display_name": "Human-style heuristic",
        "description": "Rule-based strategy that is fast and easier to reason about.",
        "speed_cost": "Low",
        "purpose": "Fast baseline",
        "browser_safe_default": True,
        "reference_only": False,
    },
    "rollout_oracle": {
        "display_name": "Reference rollout strategy",
        "description": "Stronger simulated checker for move-quality comparison, not normal play.",
        "speed_cost": "High",
        "purpose": "Reference quality check",
        "browser_safe_default": False,
        "reference_only": True,
    },
}


def strategy_display_name(strategy_key: str) -> str:
    meta = STRATEGY_METADATA.get(strategy_key)
    if not meta:
        return strategy_key
    return str(meta["display_name"])


def strategy_summary_rows(strategy_keys: list[str] | tuple[str, ...]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for key in strategy_keys:
        meta = STRATEGY_METADATA.get(key)
        if meta is None:
            rows.append({"Strategy": key, "Description": "Unknown strategy", "Speed cost": "Unknown", "Purpose": "Unknown"})
            continue
        rows.append(
            {
                "Strategy": meta["display_name"],
                "Description": meta["description"],
                "Speed cost": meta["speed_cost"],
                "Purpose": meta["purpose"],
            }
        )
    return rows


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
                "Strategy": strategy_display_name(policy_name),
                "Strategy Key": policy_name,
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
                "Strategy": strategy_display_name(policy_name),
                "Strategy Key": policy_name,
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
        f"This run is estimated to simulate about {full_games} full games and compare about {sampled_states} decision snapshots."
    )
    return run_text, f"Estimated run cost: **{speed}**."


def plan_summary_lines(plan: BenchmarkPlan) -> list[str]:
    lines = [
        f"Mode: **{plan.mode}** ({'browser-safe' if plan.browser_safe_mode_used else 'advanced'})",
        f"Strategies included: {', '.join(strategy_display_name(k) for k in plan.strategies_included)}",
        f"Strategies skipped: {', '.join(strategy_display_name(k) for k in plan.strategies_skipped)}",
        f"Stages: score comparison={'yes' if plan.include_score_comparison else 'no'}, move-quality={'yes' if plan.include_move_quality else 'no'}",
        (
            "Estimated workload: "
            f"{plan.workload['full_game_simulations']} full-game simulations, "
            f"{plan.workload['sampled_state_target']} sampled states, "
            f"{plan.workload['reference_evaluations']} reference evaluations."
        ),
        f"Likely runtime driver: **{plan.workload['likely_runtime_driver']}**.",
    ]
    return lines


def results_takeaway(full_rows: list[dict[str, object]], oracle_rows: list[dict[str, object]]) -> str:
    if not full_rows:
        return "No score comparison results were produced in this run."

    score_winner = max(full_rows, key=lambda row: float(row.get("Average Final Score", 0.0)))
    consistent = max(full_rows, key=lambda row: float(row.get("Low-end Score (P10)", 0.0)))

    if oracle_rows:
        match_winner = max(
            oracle_rows,
            key=lambda row: float(row.get("Matched Best-Known Choice (oracle agreement rate)", 0.0)),
        )
        return (
            f"Best scorer: {score_winner['Strategy']}. Most consistent low-end: {consistent['Strategy']}. "
            f"Best move-quality agreement: {match_winner['Strategy']}."
        )

    return (
        f"Best scorer: {score_winner['Strategy']}. Most consistent low-end: {consistent['Strategy']}. "
        "Move-quality comparison was not run."
    )
