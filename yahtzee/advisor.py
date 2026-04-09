from __future__ import annotations

from dataclasses import dataclass
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
from yahtzee.rules import is_full_house, is_large_straight, is_n_of_a_kind, is_small_straight
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

UPPER_PIP = {
    Category.ONES: 1,
    Category.TWOS: 2,
    Category.THREES: 3,
    Category.FOURS: 4,
    Category.FIVES: 5,
    Category.SIXES: 6,
}


@dataclass
class UtilityBreakdown:
    upper_bonus_progress: float = 0.0
    category_scarcity: float = 0.0
    sacrifice_slot: float = 0.0

    @property
    def total(self) -> float:
        return self.upper_bonus_progress + self.category_scarcity + self.sacrifice_slot


class YahtzeeAdvisor:
    def recommend(
        self,
        dice: list[int],
        roll_number: int,
        scorecard: Scorecard,
        objective: OptimizationObjective = OptimizationObjective.BOARD_UTILITY,
        *,
        include_probabilities: bool = False,
        top_n: int = 3,
    ) -> Recommendation:
        if scorecard.is_complete:
            raise ValueError("No legal scoring categories remain; the game is complete.")
        cdice = canonical_dice(dice)
        rolls_remaining = max(0, 3 - roll_number)
        best_stop_category, best_stop_utility, best_stop_score = self.best_score_now(cdice, scorecard)

        candidates: list[CandidateAction] = []
        if rolls_remaining > 0:
            for hold in distinct_holds(cdice):
                exact_ev, total_utility, yahtzee_probability = self.hold_metrics(hold, rolls_remaining, scorecard, objective)
                held_str = ", ".join(map(str, hold)) if hold else "nothing"
                candidates.append(
                    CandidateAction(
                        action_type=ActionType.HOLD_AND_REROLL,
                        held_dice=hold,
                        expected_value=total_utility,
                        exact_turn_ev=exact_ev,
                        board_adjustment=total_utility - exact_ev,
                        description=f"Hold {held_str}, reroll {5 - len(hold)} dice.",
                        yahtzee_probability=yahtzee_probability,
                    )
                )

        score_now_yahtzee_probability = 1.0 if is_yahtzee_dice(cdice) else 0.0
        score_now_adjustment = (
            self.full_house_take_break_adjustment(cdice, roll_number, scorecard, best_stop_category)
            if objective == OptimizationObjective.BOARD_UTILITY
            else 0.0
        )
        candidates.append(
            CandidateAction(
                action_type=ActionType.SCORE_NOW,
                category=best_stop_category,
                expected_value=best_stop_utility + score_now_adjustment,
                exact_turn_ev=float(best_stop_score),
                board_adjustment=(best_stop_utility - float(best_stop_score)) + score_now_adjustment,
                description=f"Score {best_stop_category.value} now for {best_stop_score}.",
                yahtzee_probability=score_now_yahtzee_probability,
            )
        )

        ranked = sorted(candidates, key=lambda c: self._candidate_sort_key(c, objective), reverse=True)
        best = ranked[0]
        if include_probabilities and best.action_type == ActionType.HOLD_AND_REROLL and best.held_dice is not None:
            best.probabilities = self.optimal_turn_outcome_probabilities(best.held_dice, rolls_remaining, scorecard, objective)
        explanation = self._explain(best, best_stop_category, roll_number, objective, cdice, scorecard)
        return Recommendation(
            best_action=best,
            top_actions=ranked[: max(1, int(top_n))],
            best_stop_category=best_stop_category,
            best_stop_score=best_stop_score,
            explanation=explanation,
            objective=objective,
            recommended_line_yahtzee_probability=best.yahtzee_probability,
            max_yahtzee_probability=self.probability_of_max_yahtzee_from_state(cdice, roll_number, scorecard),
        )

    def best_score_now(self, dice: tuple[int, ...], scorecard: Scorecard) -> tuple[Category, float, int]:
        legal_categories = scorecard.legal_scoring_categories(dice)
        if not legal_categories:
            raise ValueError("No legal scoring categories remain; the game is complete.")
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

        if objective == OptimizationObjective.BOARD_UTILITY:
            utility_ev += self._board_hold_adjustment(held, rolls_remaining, scorecard)

        return exact_ev, utility_ev, yahtzee_probability_ev

    def _board_hold_adjustment(self, held: tuple[int, ...], rolls_remaining: int, scorecard: Scorecard) -> float:
        if not held:
            return 0.0
        return (
            self.straight_draw_adjustment(held, rolls_remaining, scorecard)
            + self.yahtzee_chase_adjustment(held, rolls_remaining, scorecard)
        )

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
        breakdown = UtilityBreakdown(
            upper_bonus_progress=self.upper_bonus_progress_adjustment(scorecard, category, raw_score),
            category_scarcity=self.category_scarcity_adjustment(scorecard, category, raw_score),
            sacrifice_slot=self.sacrifice_slot_adjustment(scorecard, category, raw_score),
        )
        utility += breakdown.total
        return utility

    def upper_bonus_progress_adjustment(self, scorecard: Scorecard, category: Category, raw_score: int) -> float:
        if category not in UPPER_CATEGORIES:
            return 0.0

        current_upper = scorecard.upper_subtotal
        needed_now = max(0, 63 - current_upper)
        if needed_now == 0:
            return 0.4

        open_upper = scorecard.open_upper_categories()
        if not open_upper:
            return 0.0

        pip = UPPER_PIP[category]
        open_upper_capacity = sum(5 * UPPER_PIP[c] for c in open_upper)
        remaining_capacity_after = max(0, open_upper_capacity - (5 * pip))
        needed_after = max(0, needed_now - raw_score)

        # bonus race pressure: large when there is little slack left.
        pressure = needed_now / max(1.0, open_upper_capacity)
        pressure_factor = 1.0 + (1.8 * min(1.0, pressure))

        progress_ratio = min(1.0, raw_score / max(1.0, needed_now))
        pip_weight = 0.5 + (pip / 6.0)
        progress_value = 5.2 * progress_ratio * pip_weight * pressure_factor

        if needed_after == 0:
            progress_value += 7.0
        elif needed_after > remaining_capacity_after:
            progress_value += 3.0

        if needed_now > open_upper_capacity * 0.92:
            progress_value *= 0.3

        target = 3 * pip
        if raw_score >= target:
            progress_value += 1.2
        else:
            progress_value -= 0.25 * (target - raw_score)

        return progress_value

    def category_scarcity_adjustment(self, scorecard: Scorecard, category: Category, raw_score: int) -> float:
        open_count = len(scorecard.open_categories())
        scarcity = {
            Category.LARGE_STRAIGHT: 7.5,
            Category.SMALL_STRAIGHT: 3.2,
            Category.FULL_HOUSE: 2.8,
            Category.YAHTZEE: 2.0,
            Category.FOUR_KIND: 1.2,
        }.get(category, 0.0)
        if scarcity == 0.0:
            return 0.0

        phase = 0.7 + 0.6 * (open_count / 13.0)
        score_factor = 1.0
        if category == Category.LARGE_STRAIGHT and raw_score == 40:
            score_factor = 1.25
        elif category == Category.SMALL_STRAIGHT and raw_score == 30:
            score_factor = 1.1

        return scarcity * phase * score_factor

    def sacrifice_slot_adjustment(self, scorecard: Scorecard, category: Category, raw_score: int) -> float:
        open_count = len(scorecard.open_categories())
        early = open_count >= 8

        if raw_score > 0:
            if category == Category.CHANCE and early and raw_score < 20:
                return -2.8
            return 0.0

        if category == Category.CHANCE:
            return -9.0 if early else -4.0
        if category in (Category.ONES, Category.TWOS):
            return -0.8 if early else -0.3
        if category == Category.FOUR_KIND:
            return -1.2 if early else -0.5
        if category == Category.YAHTZEE:
            return -3.5 if early else 0.5
        return -1.8 if early else -0.8

    def straight_draw_adjustment(self, held: tuple[int, ...], rolls_remaining: int, scorecard: Scorecard) -> float:
        unique = set(held)
        score = 0.0

        large_open = not scorecard.is_filled(Category.LARGE_STRAIGHT)
        small_open = not scorecard.is_filled(Category.SMALL_STRAIGHT)

        four_card_runs = ({1, 2, 3, 4}, {2, 3, 4, 5}, {3, 4, 5, 6})
        core_runs = ({2, 3, 4}, {3, 4, 5})

        if large_open and any(run.issubset(unique) for run in four_card_runs):
            score += 6.0 if rolls_remaining >= 2 else 3.5
        if small_open and any(run.issubset(unique) for run in core_runs):
            score += 4.8 if rolls_remaining >= 2 else 2.4

        if large_open and len(held) == 5 and is_large_straight(held):
            score += 9.0
        if small_open and len(held) == 5 and is_small_straight(held):
            score += 4.0

        if (not large_open) and (not small_open):
            score *= 0.1

        return score

    def full_house_take_break_adjustment(
        self,
        dice: tuple[int, ...],
        roll_number: int,
        scorecard: Scorecard,
        chosen_category: Category,
    ) -> float:
        if roll_number >= 3 or not is_full_house(dice) or scorecard.is_filled(Category.FULL_HOUSE):
            return 0.0

        counts = sorted({d: dice.count(d) for d in set(dice)}.values())
        if counts != [2, 3]:
            return 0.0

        triple_pip = max(set(dice), key=lambda p: dice.count(p))
        open_count = len(scorecard.open_categories())
        stability_need = 1.0 if open_count <= 4 else 0.0
        upside_open = sum(
            int(not scorecard.is_filled(cat))
            for cat in (Category.THREE_KIND, Category.FOUR_KIND, Category.YAHTZEE)
        )
        upper_cat = UPPER_CATEGORIES[triple_pip - 1]
        upper_open = not scorecard.is_filled(upper_cat)

        if chosen_category == Category.FULL_HOUSE:
            if triple_pip <= 3:
                return 4.2 + stability_need
            return -0.8 * upside_open - (1.0 if upper_open else 0.0)

        # If not taking full house now, still lightly reward breaking high triple houses.
        if triple_pip >= 5 and upside_open >= 2:
            return 1.8
        return 0.0

    def yahtzee_chase_adjustment(self, held: tuple[int, ...], rolls_remaining: int, scorecard: Scorecard) -> float:
        if rolls_remaining < 2 or len(held) != 4:
            return 0.0

        pip = held[0]
        if any(d != pip for d in held):
            return 0.0

        yahtzee_score = scorecard.scores[Category.YAHTZEE]
        if yahtzee_score is None:
            base = 4.8
        elif yahtzee_score == 50:
            base = 6.0
        elif yahtzee_score == 0:
            base = 1.0
        else:
            base = 2.0

        upper_category = UPPER_CATEGORIES[pip - 1]
        if not scorecard.is_filled(upper_category):
            needed = max(0, 63 - scorecard.upper_subtotal)
            if needed > 0:
                base += 1.2 * (pip / 6.0)

        return base

    def _explain(self, best: CandidateAction, stop_cat: Category, roll_number: int, objective: OptimizationObjective, dice: tuple[int, ...], scorecard: Scorecard) -> str:
        objective_label = {
            OptimizationObjective.BOARD_UTILITY: "board-aware utility",
            OptimizationObjective.EXACT_TURN_EV: "exact turn EV",
            OptimizationObjective.MAXIMIZE_YAHTZEE_PROBABILITY: "Yahtzee probability",
        }[objective]

        strategic_reasons: list[str] = []
        if objective == OptimizationObjective.BOARD_UTILITY:
            if best.action_type == ActionType.HOLD_AND_REROLL and best.held_dice is not None:
                if self.straight_draw_adjustment(best.held_dice, max(0, 3 - roll_number), scorecard) >= 4.5:
                    strategic_reasons.append("preserving straight potential")
                if self.yahtzee_chase_adjustment(best.held_dice, max(0, 3 - roll_number), scorecard) > 3.5:
                    strategic_reasons.append("chasing Yahtzee from an opening four-of-a-kind")
            if best.action_type == ActionType.SCORE_NOW and best.category in UPPER_CATEGORIES:
                if self.upper_bonus_progress_adjustment(scorecard, best.category, int(best.exact_turn_ev)) > 4.0:
                    strategic_reasons.append("chasing upper-bonus progress")
            if best.action_type == ActionType.SCORE_NOW and best.category == Category.FULL_HOUSE:
                if self.full_house_take_break_adjustment(dice, roll_number, scorecard, best.category) > 0:
                    strategic_reasons.append("taking a secure Full House now")
            if best.action_type == ActionType.SCORE_NOW and best.category == Category.CHANCE:
                if self.sacrifice_slot_adjustment(scorecard, Category.CHANCE, int(best.exact_turn_ev)) >= 0:
                    strategic_reasons.append("using Chance only because bailout flexibility is less valuable now")

        reason_text = ""
        if strategic_reasons:
            reason_text = " Strategic factors: " + ", ".join(strategic_reasons) + "."

        if best.action_type == ActionType.SCORE_NOW:
            return (
                f"Roll {roll_number}: scoring now is best for objective '{objective_label}'. "
                f"Score-now EV is {best.exact_turn_ev:.2f}, board adjustment {best.board_adjustment:+.2f}, "
                f"and Yahtzee chance on this line is {best.yahtzee_probability:.1%}."
                f"{reason_text}"
            )
        return (
            f"Roll {roll_number}: this hold is best for objective '{objective_label}'. "
            f"Projected exact turn EV is {best.exact_turn_ev:.2f}, board-adjusted utility is {best.expected_value:.2f}, "
            f"and Yahtzee chance on this line is {best.yahtzee_probability:.1%}. "
            f"If you stop immediately, {stop_cat.value} is the best legal score-now category."
            f"{reason_text}"
        )
