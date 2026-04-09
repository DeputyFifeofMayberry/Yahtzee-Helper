from __future__ import annotations

from dataclasses import asdict

from .run import BenchmarkPlan, BenchmarkSettings

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
    "rollout_reference": {
        "display_name": "Rollout reference strategy",
        "description": "Monte Carlo rollout reference for move-quality comparison only.",
        "speed_cost": "High",
        "purpose": "Reference quality check",
        "browser_safe_default": False,
        "reference_only": True,
    },
}


def strategy_display_name(strategy_key: str) -> str:
    meta = STRATEGY_METADATA.get(strategy_key)
    return strategy_key if not meta else str(meta["display_name"])


def strategy_summary_rows(strategy_keys: list[str] | tuple[str, ...]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for key in strategy_keys:
        meta = STRATEGY_METADATA.get(key)
        rows.append(
            {
                "Strategy": key if meta is None else meta["display_name"],
                "Description": "Unknown strategy" if meta is None else meta["description"],
                "Speed cost": "Unknown" if meta is None else meta["speed_cost"],
                "Purpose": "Unknown" if meta is None else meta["purpose"],
            }
        )
    return rows


def settings_equal(a: BenchmarkSettings, b: BenchmarkSettings) -> bool:
    return asdict(a) == asdict(b)


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
                "Average Zeros per Game": metrics.get("average_zeros_per_game", 0.0),
            }
        )
    return rows


def flatten_rollout_reference_summary(summary: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for policy_name, metrics in sorted(summary.items()):
        rows.append(
            {
                "Strategy": strategy_display_name(policy_name),
                "Strategy Key": policy_name,
                "Sampled Test States": metrics.get("comparisons", 0),
                "Reference Agreement Rate": metrics.get("reference_agreement_rate", 0.0),
                "Average Estimated Regret vs Reference": metrics.get("average_estimated_regret_vs_reference", 0.0),
                "Median Estimated Regret": metrics.get("median_estimated_regret_vs_reference", 0.0),
                "High-end Estimated Regret (P90)": metrics.get("p90_estimated_regret_vs_reference", 0.0),
                "Average Evaluation Rollouts": metrics.get("average_evaluation_rollouts", 0.0),
                "Cautions": " | ".join(metrics.get("cautions", [])),
            }
        )
    return rows


def plan_summary_lines(plan: BenchmarkPlan) -> list[str]:
    return [
        f"Mode: **{plan.mode}** ({'browser-safe' if plan.browser_safe_mode_used else 'advanced'})",
        f"Strategies included: {', '.join(strategy_display_name(k) for k in plan.strategies_included)}",
        f"Stages: full-game score={'yes' if plan.include_score_comparison else 'no'}, move-quality vs rollout reference={'yes' if plan.include_move_quality else 'no'}",
        (
            "Estimated workload: "
            f"{plan.workload['full_game_simulations']} full-game simulations, "
            f"{plan.workload['sampled_state_target']} sampled states, "
            f"{plan.workload['reference_evaluations']} rollout evaluations."
        ),
    ]


def results_takeaway(full_rows: list[dict[str, object]], reference_rows: list[dict[str, object]]) -> str:
    if not full_rows:
        return "No score comparison results were produced in this run."
    score_winner = max(full_rows, key=lambda row: float(row.get("Average Final Score", 0.0)))
    if not reference_rows:
        return f"Highest average score: {score_winner['Strategy']}. Move-quality stage was not run."

    sample_count = max(float(row.get("Sampled Test States", 0.0)) for row in reference_rows)
    caution = "Interpret move-quality cautiously due to small sample size." if sample_count < 30 else "Move-quality uses rollout estimates, not exact truth."
    return f"Highest average score: {score_winner['Strategy']}. {caution}"
