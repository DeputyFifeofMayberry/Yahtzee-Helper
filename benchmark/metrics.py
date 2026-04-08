from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean, median

from benchmark.models import GameSimulationResult, OracleComparisonRecord


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
        "zero_rate_by_category": {
            category: round(count / len(results), 4)
            for category, count in sorted(zero_counter.items())
        },
        "average_score_by_category": {
            category: round(mean(scores), 3)
            for category, scores in sorted(category_score_totals.items())
        },
    }


def summarize_oracle_results(records: list[OracleComparisonRecord]) -> dict[str, object]:
    if not records:
        return {"comparisons": 0}

    regrets = [record.regret for record in records]
    overall = {
        "comparisons": len(records),
        "oracle_agreement_rate": round(mean(1.0 if record.matched_oracle else 0.0 for record in records), 4),
        "average_regret": round(mean(regrets), 4),
        "median_regret": round(median(regrets), 4),
        "p90_regret": round(percentile(regrets, 0.90), 4),
        "severe_miss_rate_gt_3": round(mean(1.0 if record.regret > 3.0 else 0.0 for record in records), 4),
        "severe_miss_rate_gt_5": round(mean(1.0 if record.regret > 5.0 else 0.0 for record in records), 4),
    }

    by_tag: dict[str, list[OracleComparisonRecord]] = defaultdict(list)
    by_roll: dict[int, list[OracleComparisonRecord]] = defaultdict(list)
    for record in records:
        by_roll[record.roll_number].append(record)
        for tag in record.tags:
            by_tag[tag].append(record)

    overall["by_roll_number"] = {
        f"roll_{roll}": _summarize_record_group(group) for roll, group in sorted(by_roll.items())
    }
    overall["by_tag"] = {
        tag: _summarize_record_group(group) for tag, group in sorted(by_tag.items())
    }
    return overall


def _summarize_record_group(group: list[OracleComparisonRecord]) -> dict[str, float]:
    regrets = [record.regret for record in group]
    return {
        "count": float(len(group)),
        "oracle_agreement_rate": round(mean(1.0 if record.matched_oracle else 0.0 for record in group), 4),
        "average_regret": round(mean(regrets), 4),
        "p90_regret": round(percentile(regrets, 0.90), 4),
    }
