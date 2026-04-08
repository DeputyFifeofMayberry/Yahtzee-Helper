from __future__ import annotations

from functools import lru_cache

from yahtzee.models import (
    ActionType,
    Category,
    CandidateAction,
    OptimizationObjective,
    Recommendation,
    Scorecard,
    UPPER_CATEGORIES,
)
from yahtzee.probabilities import is_yahtzee_dice, outcome_class_distribution, reroll_distribution
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
    def recommend(
        self,
        dice: list[int],
        roll_number: int,
        scorecard: Scorecard,
        objective: OptimizationObjective = OptimizationObjective.BOARD_UTILITY,
    ) -> Recommendation:
        cdice = canonical_dice(dice)
        rolls_remaining = max(0, 3 - roll_number)
        best_stop_category, best_stop_utility, best_stop_score = self.best_score_now(cdice, scorecard)

        candidates: list[CandidateAction] = []
        if rolls_remaining > 0:
            for hold in distinct_holds(cdice):
                exact_ev, total_utility, yahtzee_probability = self.hold_metrics(hold, rolls_remaining, scorecard, objective)
                probs = self.optimal_turn_outcome_probabilities(hold, rolls_remaining, scorecard, objective)
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
                        yahtzee_probability=yahtzee_probability,
                    )
                )

        score_now_yahtzee_probability = 1.0 if is_yahtzee_dice(cdice) else 0.0
        candidates.append(
            CandidateAction(
                action_type=ActionType.SCORE_NOW,
                category=best_stop_category,
                expected_value=best_stop_utility,
                exact_turn_ev=float(best_stop_score),
                board_adjustment=best_stop_utility - float(best_stop_score),
                description=f"Score {best_stop_category.value} now for {best_stop_score}.",
                yahtzee_probability=score_now_yahtzee_probability,
            )
        )

        ranked = sorted(candidates, key=lambda c: self._candidate_sort_key(c, objective), reverse=True)
        best = ranked[0]
        explanation = self._explain(best, best_stop_category, roll_number, objective)
        return Recommendation(
            best_action=best,
            top_actions=ranked[:3],
            best_stop_category=best_stop_category,
            best_stop_score=best_stop_score,
            explanation=explanation,
            objective=objective,
            recommended_line_yahtzee_probability=best.yahtzee_probability,
            max_yahtzee_probability=self.probability_of_max_yahtzee_from_state(cdice, roll_number, scorecard),
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

    def hold_metrics(
        self,
        held: tuple[int, ...],
        rolls_remaining: int,
        scorecard: Scorecard,
        objective: OptimizationObjective,
    ) -> tuple[float, float, float]:
        return self._hold_metrics_cached(tuple(sorted(held)), rolls_remaining, scorecard.score_signature(), objective.value)

    @lru_cache(maxsize=700_000)
    def _hold_metrics_cached(
        self,
        held: tuple[int, ...],
        rolls_remaining: int,
        score_signature: tuple[tuple[int | None, ...], int],
        objective_value: str,
    ) -> tuple[float, float, float]:
        objective = OptimizationObjective(objective_value)
        scorecard = Scorecard.from_signature(score_signature)

        if rolls_remaining == 0:
            _, utility, raw_score = self.best_score_now(tuple(sorted(held)), scorecard)
            yahtzee_probability = 1.0 if is_yahtzee_dice(held) else 0.0
            return float(raw_score), utility, yahtzee_probability

        to_roll = 5 - len(held)
        exact_ev = 0.0
        utility_ev = 0.0
        yahtzee_probability_ev = 0.0

        for outcome, probability in reroll_distribution(to_roll).items():
            new_dice = tuple(sorted(held + outcome))
            if rolls_remaining == 1:
                _, utility, raw_score = self.best_score_now(new_dice, scorecard)
                next_exact = float(raw_score)
                next_utility = utility
                next_yahtzee_probability = 1.0 if is_yahtzee_dice(new_dice) else 0.0
            else:
                best_next_hold = self.choose_best_hold(new_dice, rolls_remaining - 1, score_signature, objective)
                next_exact, next_utility, next_yahtzee_probability = self._hold_metrics_cached(
                    best_next_hold,
                    rolls_remaining - 1,
                    score_signature,
                    objective.value,
                )
            exact_ev += probability * next_exact
            utility_ev += probability * next_utility
            yahtzee_probability_ev += probability * next_yahtzee_probability

        return exact_ev, utility_ev, yahtzee_probability_ev

    def choose_best_hold(
        self,
        dice: tuple[int, ...],
        rolls_remaining: int,
        score_signature: tuple[tuple[int | None, ...], int],
        objective: OptimizationObjective,
    ) -> tuple[int, ...]:
        best_hold: tuple[int, ...] | None = None
        best_key: tuple[float, float, float, int, tuple[int, ...]] | None = None
        for hold in distinct_holds(dice):
            exact_ev, utility_ev, yahtzee_probability = self._hold_metrics_cached(
                hold,
                rolls_remaining,
                score_signature,
                objective.value,
            )
            key = self._hold_sort_key(hold, exact_ev, utility_ev, yahtzee_probability, objective)
            if best_key is None or key > best_key:
                best_key = key
                best_hold = hold
        if best_hold is None:
            raise ValueError("No legal holds available")
        return best_hold

    def probability_of_yahtzee_under_policy(
        self,
        held: tuple[int, ...],
        rolls_remaining: int,
        scorecard: Scorecard,
        objective: OptimizationObjective,
    ) -> float:
        return self.hold_metrics(held, rolls_remaining, scorecard, objective)[2]

    def probability_of_max_yahtzee_from_state(self, dice: list[int] | tuple[int, ...], roll_number: int, scorecard: Scorecard) -> float:
        cdice = canonical_dice(dice)
        rolls_remaining = max(0, 3 - roll_number)
        if rolls_remaining == 0:
            return 1.0 if is_yahtzee_dice(cdice) else 0.0
        best_hold = self.choose_best_hold(cdice, rolls_remaining, scorecard.score_signature(), OptimizationObjective.MAXIMIZE_YAHTZEE_PROBABILITY)
        return self.hold_metrics(best_hold, rolls_remaining, scorecard, OptimizationObjective.MAXIMIZE_YAHTZEE_PROBABILITY)[2]

    def optimal_turn_outcome_probabilities(
        self,
        held: tuple[int, ...],
        rolls_remaining: int,
        scorecard: Scorecard,
        objective: OptimizationObjective = OptimizationObjective.BOARD_UTILITY,
    ) -> dict[str, float]:
        final_dist = self._optimal_turn_outcome_distribution(
            tuple(sorted(held)),
            rolls_remaining,
            scorecard.score_signature(),
            objective.value,
        )
        return outcome_class_distribution(final_dist)

    @lru_cache(maxsize=500_000)
    def _optimal_turn_outcome_distribution(
        self,
        held: tuple[int, ...],
        rolls_remaining: int,
        score_signature: tuple[tuple[int | None, ...], int],
        objective_value: str,
    ) -> dict[tuple[int, ...], float]:
        objective = OptimizationObjective(objective_value)
        if rolls_remaining == 0:
            return {tuple(sorted(held)): 1.0}

        to_roll = 5 - len(held)
        merged: dict[tuple[int, ...], float] = {}

        for outcome, probability in reroll_distribution(to_roll).items():
            new_dice = tuple(sorted(held + outcome))
            if rolls_remaining == 1:
                next_dist = {new_dice: 1.0}
            else:
                best_next_hold = self.choose_best_hold(new_dice, rolls_remaining - 1, score_signature, objective)
                next_dist = self._optimal_turn_outcome_distribution(
                    best_next_hold,
                    rolls_remaining - 1,
                    score_signature,
                    objective.value,
                )

            for final_dice, branch_probability in next_dist.items():
                merged[final_dice] = merged.get(final_dice, 0.0) + (probability * branch_probability)

        return merged

    def objective_value(self, exact_ev: float, utility_ev: float, yahtzee_probability: float, objective: OptimizationObjective) -> float:
        return self._objective_primary_value(exact_ev, utility_ev, yahtzee_probability, objective)

    def _candidate_sort_key(self, candidate: CandidateAction, objective: OptimizationObjective) -> tuple[float, float, float, int, str]:
        primary = self.objective_value(
            candidate.exact_turn_ev,
            candidate.expected_value,
            candidate.yahtzee_probability,
            objective,
        )
        return (
            primary,
            candidate.expected_value,
            candidate.exact_turn_ev,
            -(len(candidate.held_dice) if candidate.held_dice else 6),
            candidate.description,
        )

    def _hold_sort_key(
        self,
        hold: tuple[int, ...],
        exact_ev: float,
        utility_ev: float,
        yahtzee_probability: float,
        objective: OptimizationObjective,
    ) -> tuple[float, float, float, int, tuple[int, ...]]:
        primary = self.objective_value(exact_ev, utility_ev, yahtzee_probability, objective)
        return (primary, utility_ev, exact_ev, -len(hold), hold)

    def _objective_primary_value(
        self,
        exact_ev: float,
        utility_ev: float,
        yahtzee_probability: float,
        objective: OptimizationObjective,
    ) -> float:
        if objective == OptimizationObjective.BOARD_UTILITY:
            return utility_ev
        if objective == OptimizationObjective.EXACT_TURN_EV:
            return exact_ev
        return yahtzee_probability

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

    def _explain(self, best: CandidateAction, stop_cat: Category, roll_number: int, objective: OptimizationObjective) -> str:
        objective_label = {
            OptimizationObjective.BOARD_UTILITY: "board-aware utility",
            OptimizationObjective.EXACT_TURN_EV: "exact turn EV",
            OptimizationObjective.MAXIMIZE_YAHTZEE_PROBABILITY: "Yahtzee probability",
        }[objective]

        if best.action_type == ActionType.SCORE_NOW:
            return (
                f"Roll {roll_number}: scoring now is best for objective '{objective_label}'. "
                f"Score-now EV is {best.exact_turn_ev:.2f}, board adjustment {best.board_adjustment:+.2f}, "
                f"and Yahtzee chance on this line is {best.yahtzee_probability:.1%}."
            )
        return (
            f"Roll {roll_number}: this hold is best for objective '{objective_label}'. "
            f"Projected exact turn EV is {best.exact_turn_ev:.2f}, board-adjusted utility is {best.expected_value:.2f}, "
            f"and Yahtzee chance on this line is {best.yahtzee_probability:.1%}. "
            f"If you stop immediately, {stop_cat.value} is the best legal score-now category."
        )
