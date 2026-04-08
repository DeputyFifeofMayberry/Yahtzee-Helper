from __future__ import annotations

from functools import lru_cache

from yahtzee.models import ActionType, Category, CandidateAction, Recommendation, Scorecard, UPPER_CATEGORIES
from yahtzee.probabilities import category_probability, final_outcome_distribution, reroll_distribution
from yahtzee.scoring import category_score, score_with_scorecard
from yahtzee.utils import canonical_dice, distinct_holds


HARD_CATEGORY_WEIGHT = {
    Category.YAHTZEE: 6.0,
    Category.LARGE_STRAIGHT: 4.0,
    Category.SMALL_STRAIGHT: 2.5,
    Category.FULL_HOUSE: 2.0,
    Category.FOUR_KIND: 1.5,
    Category.THREE_KIND: 1.0,
    Category.CHANCE: 3.0,
}


class YahtzeeAdvisor:
    def recommend(self, dice: list[int], roll_number: int, scorecard: Scorecard) -> Recommendation:
        cdice = canonical_dice(dice)
        rolls_remaining = max(0, 3 - roll_number)
        best_stop_category, best_stop_utility, best_stop_score = self.best_score_now(cdice, scorecard)

        candidates: list[CandidateAction] = []
        if rolls_remaining > 0:
            for hold in distinct_holds(cdice):
                ev = self.expected_utility_for_hold(hold, rolls_remaining, scorecard)
                probs = self._key_probabilities_for_hold(hold, rolls_remaining)
                held_str = ", ".join(map(str, hold)) if hold else "nothing"
                candidates.append(
                    CandidateAction(
                        action_type=ActionType.HOLD_AND_REROLL,
                        held_dice=hold,
                        expected_value=ev,
                        description=f"Hold {held_str}, reroll {5 - len(hold)} dice.",
                        probabilities=probs,
                    )
                )
        candidates.append(
            CandidateAction(
                action_type=ActionType.SCORE_NOW,
                category=best_stop_category,
                expected_value=best_stop_utility,
                description=f"Score {best_stop_category.value} now for {best_stop_score}.",
            )
        )

        ranked = sorted(candidates, key=lambda c: c.expected_value, reverse=True)
        best = ranked[0]
        explanation = self._explain(best, best_stop_category, roll_number, scorecard)
        return Recommendation(
            best_action=best,
            top_actions=ranked[:3],
            best_stop_category=best_stop_category,
            best_stop_score=best_stop_score,
            explanation=explanation,
        )

    def best_score_now(self, dice: tuple[int, ...], scorecard: Scorecard) -> tuple[Category, float, int]:
        best_cat = scorecard.open_categories()[0]
        best_utility = float("-inf")
        best_score = 0
        for cat in scorecard.open_categories():
            try:
                score, yb = score_with_scorecard(dice, cat, scorecard)
            except ValueError:
                continue
            utility = self._score_utility(scorecard, cat, score, yb)
            if utility > best_utility:
                best_utility = utility
                best_cat, best_score = cat, score
        return best_cat, best_utility, best_score

    @lru_cache(maxsize=250_000)
    def _expected_utility_cached(
        self,
        held: tuple[int, ...],
        rolls_remaining: int,
        open_categories_sig: tuple[str, ...],
        upper_subtotal: int,
        yahtzee_box: int,
    ) -> float:
        scorecard = Scorecard()
        for c in scorecard.scores:
            scorecard.scores[c] = 0 if c.value not in open_categories_sig else None
        scorecard.scores[Category.YAHTZEE] = yahtzee_box if Category.YAHTZEE.value not in open_categories_sig else None
        for c in UPPER_CATEGORIES:
            if scorecard.scores[c] == 0 and upper_subtotal > 0:
                # lightweight encoding for bonus pressure in utility calculation
                scorecard.scores[c] = 1
                upper_subtotal -= 1

        if rolls_remaining == 0:
            _, utility, _ = self.best_score_now(tuple(sorted(held)), scorecard)
            return utility

        to_roll = 5 - len(held)
        dist = reroll_distribution(to_roll)
        ev = 0.0
        for outcome, p in dist.items():
            new_dice = tuple(sorted(held + outcome))
            if rolls_remaining == 1:
                _, u, _ = self.best_score_now(new_dice, scorecard)
            else:
                holds = distinct_holds(new_dice)
                u = max(self.expected_utility_for_hold(h, rolls_remaining - 1, scorecard) for h in holds)
            ev += p * u
        return ev

    def expected_utility_for_hold(self, held: tuple[int, ...], rolls_remaining: int, scorecard: Scorecard) -> float:
        sig = tuple(sorted(c.value for c in scorecard.open_categories()))
        yahtzee_box = scorecard.scores[Category.YAHTZEE] if scorecard.scores[Category.YAHTZEE] is not None else -1
        return self._expected_utility_cached(tuple(sorted(held)), rolls_remaining, sig, scorecard.upper_subtotal, yahtzee_box)

    def _score_utility(self, scorecard: Scorecard, category: Category, raw_score: int, yahtzee_bonus: int) -> float:
        utility = float(raw_score + yahtzee_bonus)

        if category in UPPER_CATEGORIES:
            remaining_to_bonus = max(0, 63 - scorecard.upper_subtotal)
            progress = min(raw_score, remaining_to_bonus)
            utility += progress * 0.6
            if remaining_to_bonus > 0 and raw_score == 0:
                utility -= 3.0

        if category in HARD_CATEGORY_WEIGHT:
            open_count = len(scorecard.open_categories())
            scarcity_factor = (13 - open_count + 1) / 13
            utility -= HARD_CATEGORY_WEIGHT[category] * (1 - scarcity_factor)

        if category == Category.CHANCE and len(scorecard.open_categories()) > 6:
            utility -= 4.0

        if category == Category.YAHTZEE and raw_score == 0 and len(scorecard.open_categories()) < 5:
            utility += 2.5

        return utility

    def _key_probabilities_for_hold(self, hold: tuple[int, ...], rolls_remaining: int) -> dict[str, float]:
        dist = final_outcome_distribution(hold, 1 if rolls_remaining > 0 else 0)
        return {
            "Yahtzee": category_probability(dist, Category.YAHTZEE),
            "Full House": category_probability(dist, Category.FULL_HOUSE),
            "Small Straight": category_probability(dist, Category.SMALL_STRAIGHT),
            "Large Straight": category_probability(dist, Category.LARGE_STRAIGHT),
            "Three of a Kind": category_probability(dist, Category.THREE_KIND),
            "Four of a Kind": category_probability(dist, Category.FOUR_KIND),
        }

    def _explain(self, best: CandidateAction, stop_cat: Category, roll_number: int, scorecard: Scorecard) -> str:
        if best.action_type == ActionType.SCORE_NOW:
            return (
                f"Scoring now is strongest on roll {roll_number}; {best.category.value} has the best board-aware utility "
                f"given open categories and bonus pressure."
            )
        return (
            f"Holding this pattern maximizes expected end-of-turn utility via exact roll-out over remaining rerolls. "
            f"If you stop now, {stop_cat.value} is currently the best score-now fallback."
        )
