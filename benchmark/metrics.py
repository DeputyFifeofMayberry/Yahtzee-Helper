from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean, median, stdev

from .models import GameSimulationResult, RolloutReferenceComparisonRecord


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    ordered = sorted(values)
    index = (len(ordered) - 1) * pct
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return float(ordered[int(index)])
    lower_value = ordered[lower]
    upper_value = ordered[upper]
    fraction = index - lower
    return float(lower_value + (upper_value - lower_value) * fraction)


def summarize_game_results(results: list[GameSimulationResult]) -> dict[str, object]:
    if not results:
        return {"games": 0}

    final_scores = [result.final_score for result in results]
    zero_counter: dict[str, int] = defaultdict(int)
    category_score_totals: dict[str, list[int]] = defaultdict(list)

    for result in results:
        for category in result.zeroed_categories:
            zero_counter[category] += 1
        for category, score in result.category_scores.items():
            if score is not None:
                category_score_totals[category].append(score)

    return {
        "games": len(results),
        "average_final_score": round(mean(final_scores), 3),
        "median_final_score": round(median(final_scores), 3),
        "p10_final_score": round(percentile(final_scores, 0.10), 3),
        "p90_final_score": round(percentile(final_scores, 0.90), 3),
        "min_final_score": min(final_scores),
        "max_final_score": max(final_scores),
        "upper_bonus_hit_rate": round(mean(1.0 if result.upper_bonus_hit else 0.0 for result in results), 4),
        "average_upper_subtotal": round(mean(result.upper_subtotal for result in results), 3),
        "yahtzee_rate": round(mean(1.0 if result.yahtzee_scored else 0.0 for result in results), 4),
        "extra_yahtzee_bonus_rate": round(mean(1.0 if result.yahtzee_bonus_count > 0 else 0.0 for result in results), 4),
        "average_extra_yahtzee_bonus_count": round(mean(result.yahtzee_bonus_count for result in results), 4),
        "average_zeros_per_game": round(mean(len(result.zeroed_categories) for result in results), 4),
        "zero_rate_by_category": {category: round(count / len(results), 4) for category, count in sorted(zero_counter.items())},
        "average_score_by_category": {
            category: round(mean(scores), 3)
            for category, scores in sorted(category_score_totals.items())
        },
    }


def summarize_rollout_reference_results(records: list[RolloutReferenceComparisonRecord]) -> dict[str, object]:
    if not records:
        return {"comparisons": 0, "cautions": ["No move-quality comparisons were run."]}

    regrets = [record.estimated_regret_vs_reference for record in records]
    overall = {
        "comparisons": len(records),
        "reference_agreement_rate": round(mean(1.0 if record.matched_rollout_reference else 0.0 for record in records), 4),
        "average_estimated_regret_vs_reference": round(mean(regrets), 4),
        "median_estimated_regret_vs_reference": round(median(regrets), 4),
        "p90_estimated_regret_vs_reference": round(percentile(regrets, 0.90), 4),
        "severe_miss_rate_gt_3": round(mean(1.0 if record.estimated_regret_vs_reference > 3.0 else 0.0 for record in records), 4),
        "severe_miss_rate_gt_5": round(mean(1.0 if record.estimated_regret_vs_reference > 5.0 else 0.0 for record in records), 4),
        "average_evaluation_rollouts": round(mean(record.evaluation_rollouts for record in records), 2),
    }

    cautions: list[str] = []
    if len(records) < 30:
        cautions.append("Small sample size: move-quality estimates may be unstable.")
    if overall["average_evaluation_rollouts"] < 16:
        cautions.append("Low rollout count: reference values have high Monte Carlo noise.")
    if not cautions:
        cautions.append("Rollout reference is approximate and not a mathematical optimum.")

    by_tag: dict[str, list[RolloutReferenceComparisonRecord]] = defaultdict(list)
    by_roll: dict[int, list[RolloutReferenceComparisonRecord]] = defaultdict(list)
    for record in records:
        by_roll[record.roll_number].append(record)
        for tag in record.tags:
            by_tag[tag].append(record)

    overall["by_roll_number"] = {f"roll_{roll}": _summarize_record_group(group) for roll, group in sorted(by_roll.items())}
    overall["by_tag"] = {tag: _summarize_record_group(group) for tag, group in sorted(by_tag.items())}
    overall["cautions"] = cautions
    return overall


def summarize_paired_score_deltas(results: list[GameSimulationResult]) -> dict[str, dict[str, float]]:
    by_policy: dict[str, dict[int, int]] = defaultdict(dict)
    for result in results:
        by_policy[result.policy_name][result.shared_seed_id] = result.final_score

    deltas: dict[str, dict[str, float]] = {}
    policies = sorted(by_policy.keys())
    if not policies:
        return deltas
    baseline = policies[0]
    for policy in policies[1:]:
        common_ids = sorted(set(by_policy[baseline]) & set(by_policy[policy]))
        if not common_ids:
            continue
        paired = [by_policy[policy][idx] - by_policy[baseline][idx] for idx in common_ids]
        mu = mean(paired)
        ci = 0.0
        if len(paired) > 1:
            ci = 1.96 * (stdev(paired) / math.sqrt(len(paired)))
        deltas[policy] = {
            "baseline_policy": baseline,
            "paired_games": float(len(common_ids)),
            "mean_score_delta": round(mu, 4),
            "ci95_half_width": round(ci, 4),
        }
    return deltas


def _summarize_record_group(group: list[RolloutReferenceComparisonRecord]) -> dict[str, float]:
    regrets = [record.estimated_regret_vs_reference for record in group]
    return {
        "count": float(len(group)),
        "reference_agreement_rate": round(mean(1.0 if record.matched_rollout_reference else 0.0 for record in group), 4),
        "average_estimated_regret_vs_reference": round(mean(regrets), 4),
        "p90_estimated_regret_vs_reference": round(percentile(regrets, 0.90), 4),
    }
