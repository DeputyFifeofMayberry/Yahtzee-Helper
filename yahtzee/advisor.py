from __future__ import annotations

from functools import lru_cache

from yahtzee.models import ActionType, Category, CandidateAction, Recommendation, Scorecard, UPPER_CATEGORIES
from yahtzee.probabilities import outcome_class_distribution, reroll_distribution
from yahtzee.scoring import score_roll_in_category
from yahtzee.utils import canonical_dice, distinct_holds


CATEGORY_BASELINE = {
    Category.ONES: 2.1,
    Category.TWOS: 4.2,
    Category.THREES: 6.3,
    Category.FOURS: 8.4,
    Category.FIVES: 10.5,
    Category.SIXES: 12.6,
    Category.THREE_KIND: 16.0,
    Category.FOUR_KIND: 5.6,
    Category.FULL_HOUSE: 3.9,
    Category.SMALL_STRAIGHT: 12.3,
    Category.LARGE_STRAIGHT: 3.1,
    Category.YAHTZEE: 0.8,
    Category.CHANCE: 22.0,
}


class YahtzeeAdvisor:
    def recommend(self, dice: list[int], roll_number: int, scorecard: Scorecard) -> Recommendation:
        cdice = canonical_dice(dice)
        rolls_remaining = max(0, 3 - roll_number)
        best_stop_category, best_stop_utility, best_stop_score = self.best_score_now(cdice, scorecard)

        candidates: list[CandidateAction] = []
        if rolls_remaining > 0:
            for hold in distinct_holds(cdice):
                exact_ev, total_utility = self.expected_values_for_hold(hold, rolls_remaining, scorecard)
                probs = self.optimal_turn_outcome_probabilities(hold, rolls_remaining, scorecard)
                held_str = ", ".join(map(str, hold)) if hold else "nothing"
                candidates.append(
                    CandidateAction(
                        action_type=ActionType.HOLD_AND_REROLL,
                        held_dice=hold,
                        expected_value=total_utility,
                        exact_turn_ev=exact_ev,
                        board_adjustment=total_utility - exact_ev,
                        description=f"Hold {held_str}, reroll {5 - len(hold)} dice.",
                        probabilities=probs,
                    )
                )
        candidates.append(
            CandidateAction(
                action_type=ActionType.SCORE_NOW,
                category=best_stop_category,
                expected_value=best_stop_utility,
                exact_turn_ev=float(best_stop_score),
                board_adjustment=best_stop_utility - float(best_stop_score),
                description=f"Score {best_stop_category.value} now for {best_stop_score}.",
            )
        )

        ranked = sorted(
            candidates,
            key=lambda c: (
                c.expected_value,
                c.exact_turn_ev,
                -len(c.held_dice or ()),
                c.description,
            ),
            reverse=True,
        )
        best = ranked[0]
        explanation = self._explain(best, best_stop_category, roll_number)
        return Recommendation(
            best_action=best,
            top_actions=ranked[:3],
            best_stop_category=best_stop_category,
            best_stop_score=best_stop_score,
            explanation=explanation,
        )

    def best_score_now(self, dice: tuple[int, ...], scorecard: Scorecard) -> tuple[Category, float, int]:
        legal_categories = scorecard.legal_scoring_categories(dice)
        best_cat = legal_categories[0]
        best_utility = float("-inf")
        best_score = 0
        for cat in legal_categories:
            result = score_roll_in_category(dice, cat, scorecard)
            utility = self._score_utility(scorecard, cat, result.score, result.yahtzee_bonus_awarded)
            if utility > best_utility:
                best_utility = utility
                best_cat, best_score = cat, result.score
        return best_cat, best_utility, best_score

    def expected_values_for_hold(self, held: tuple[int, ...], rolls_remaining: int, scorecard: Scorecard) -> tuple[float, float]:
        return self._expected_values_for_hold_cached(tuple(sorted(held)), rolls_remaining, scorecard.score_signature())

    @lru_cache(maxsize=500_000)
    def _expected_values_for_hold_cached(
        self,
        held: tuple[int, ...],
        rolls_remaining: int,
        score_signature: tuple[tuple[int | None, ...], int],
    ) -> tuple[float, float]:
        scorecard = Scorecard.from_signature(score_signature)
        if rolls_remaining == 0:
            _, utility, raw_score = self.best_score_now(tuple(sorted(held)), scorecard)
            return float(raw_score), utility

        to_roll = 5 - len(held)
        exact_ev = 0.0
        utility_ev = 0.0
        for outcome, p in reroll_distribution(to_roll).items():
            new_dice = tuple(sorted(held + outcome))
            if rolls_remaining == 1:
                _, utility, raw_score = self.best_score_now(new_dice, scorecard)
                next_exact, next_utility = float(raw_score), utility
            else:
                best_next = max(
                    (self._expected_values_for_hold_cached(next_hold, rolls_remaining - 1, score_signature), next_hold)
                    for next_hold in distinct_holds(new_dice)
                )
                next_exact, next_utility = best_next[0]
            exact_ev += p * next_exact
            utility_ev += p * next_utility

        return exact_ev, utility_ev

    def optimal_turn_outcome_probabilities(
        self,
        held: tuple[int, ...],
        rolls_remaining: int,
        scorecard: Scorecard,
    ) -> dict[str, float]:
        final_dist = self._optimal_turn_outcome_distribution(tuple(sorted(held)), rolls_remaining, scorecard.score_signature())
        return outcome_class_distribution(final_dist)

    @lru_cache(maxsize=300_000)
    def _optimal_turn_outcome_distribution(
        self,
        held: tuple[int, ...],
        rolls_remaining: int,
        score_signature: tuple[tuple[int | None, ...], int],
    ) -> dict[tuple[int, ...], float]:
        if rolls_remaining == 0:
            return {tuple(sorted(held)): 1.0}

        to_roll = 5 - len(held)
        merged: dict[tuple[int, ...], float] = {}

        for outcome, p in reroll_distribution(to_roll).items():
            new_dice = tuple(sorted(held + outcome))
            if rolls_remaining == 1:
                next_dist = {new_dice: 1.0}
            else:
                best_next_hold = max(
                    distinct_holds(new_dice),
                    key=lambda h: self._expected_values_for_hold_cached(h, rolls_remaining - 1, score_signature),
                )
                next_dist = self._optimal_turn_outcome_distribution(best_next_hold, rolls_remaining - 1, score_signature)

            for final_dice, branch_p in next_dist.items():
                merged[final_dice] = merged.get(final_dice, 0.0) + (p * branch_p)

        return merged

    def _score_utility(self, scorecard: Scorecard, category: Category, raw_score: int, yahtzee_bonus: int) -> float:
        utility = float(raw_score + yahtzee_bonus)

        if category in UPPER_CATEGORIES:
            pip = UPPER_CATEGORIES.index(category) + 1
            target = 3 * pip
            utility += 0.7 * min(raw_score, target)
            if raw_score < target:
                utility -= 0.3 * (target - raw_score)

        open_count = len(scorecard.open_categories())
        phase_factor = max(0.0, (open_count - 2) / 11)
        baseline_gap = max(0.0, CATEGORY_BASELINE[category] - raw_score)
        utility -= phase_factor * baseline_gap

        if category == Category.YAHTZEE and raw_score == 0:
            utility += 1.0 if open_count <= 5 else -1.0

        if category == Category.THREE_KIND and open_count >= 9 and raw_score < 24:
            utility -= 2.0

        if category == Category.FOUR_KIND and open_count >= 9 and raw_score < 24:
            utility -= 1.0

        if category == Category.CHANCE and open_count >= 8 and raw_score < 23:
            utility -= 5.0

        return utility

    def _explain(self, best: CandidateAction, stop_cat: Category, roll_number: int) -> str:
        if best.action_type == ActionType.SCORE_NOW:
            return (
                f"Roll {roll_number}: scoring now has the top board-aware utility. "
                f"Exact score-now EV is {best.exact_turn_ev:.2f}, with board adjustment {best.board_adjustment:+.2f}."
            )
        return (
            f"Roll {roll_number}: this hold maximizes exact end-of-turn continuation EV ({best.exact_turn_ev:.2f}) "
            f"under optimal remaining holds. Final ranking adds board-aware adjustment ({best.board_adjustment:+.2f}). "
            f"If you stop immediately, {stop_cat.value} is the best legal score-now category."
        )
