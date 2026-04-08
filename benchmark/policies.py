from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from benchmark.models import PolicyDecision
from yahtzee.advisor import YahtzeeAdvisor
from yahtzee.models import ActionType, Category, GameState, OptimizationObjective, Scorecard
from yahtzee.rules import is_full_house, is_large_straight, is_small_straight


class Policy(Protocol):
    name: str

    def decide(self, state: GameState, advisor: YahtzeeAdvisor) -> PolicyDecision:
        ...


@dataclass
class ObjectivePolicy:
    name: str
    objective: OptimizationObjective

    def decide(self, state: GameState, advisor: YahtzeeAdvisor) -> PolicyDecision:
        rec = advisor.recommend(
            list(state.current_dice),
            state.roll_number,
            state.scorecard,
            objective=self.objective,
        )
        best = rec.best_action
        return PolicyDecision(
            action_type=best.action_type,
            held_dice=tuple(best.held_dice) if best.held_dice is not None else None,
            category=best.category,
            description=best.description,
        )


@dataclass
class HumanHeuristicPolicy:
    name: str = "human_heuristic"

    def decide(self, state: GameState, advisor: YahtzeeAdvisor) -> PolicyDecision:
        dice = tuple(sorted(state.current_dice))
        scorecard = state.scorecard

        if state.roll_number == 3:
            return self._score_now_decision(dice, scorecard, advisor)

        if Category.LARGE_STRAIGHT in scorecard.open_categories() and is_large_straight(dice):
            if state.roll_number == 1:
                return PolicyDecision(ActionType.HOLD_AND_REROLL, held_dice=dice, description="Preserve made large straight.")
            return PolicyDecision(ActionType.SCORE_NOW, category=Category.LARGE_STRAIGHT, description="Bank large straight.")

        if Category.FULL_HOUSE in scorecard.open_categories() and is_full_house(dice):
            counts = Counter(dice)
            trip_value = max(value for value, count in counts.items() if count == 3)
            if trip_value <= 4 or state.roll_number == 2:
                return PolicyDecision(ActionType.SCORE_NOW, category=Category.FULL_HOUSE, description="Bank full house.")

        four_kind = self._highest_n_of_a_kind_value(dice, 4)
        if (
            four_kind is not None
            and state.roll_number == 1
            and scorecard.scores[Category.YAHTZEE] is None
        ):
            return PolicyDecision(
                ActionType.HOLD_AND_REROLL,
                held_dice=(four_kind, four_kind, four_kind, four_kind),
                description="Chase Yahtzee from opening four of a kind.",
            )

        large_draw = self._best_large_straight_draw(dice, scorecard)
        if large_draw is not None:
            return PolicyDecision(ActionType.HOLD_AND_REROLL, held_dice=large_draw, description="Preserve four-card straight draw.")

        small_draw = self._best_small_straight_core(dice, scorecard)
        if small_draw is not None:
            return PolicyDecision(ActionType.HOLD_AND_REROLL, held_dice=small_draw, description="Preserve small-straight core.")

        trip_value = self._highest_n_of_a_kind_value(dice, 3)
        if trip_value is not None:
            return PolicyDecision(
                ActionType.HOLD_AND_REROLL,
                held_dice=(trip_value, trip_value, trip_value),
                description="Keep made triple.",
            )

        high_pair = self._best_upper_pair_to_keep(dice, scorecard)
        if high_pair is not None:
            return PolicyDecision(
                ActionType.HOLD_AND_REROLL,
                held_dice=(high_pair, high_pair),
                description="Keep high pair for upper section.",
            )

        return self._score_or_best_hold_fallback(state, advisor)

    def _score_now_decision(self, dice: tuple[int, ...], scorecard: Scorecard, advisor: YahtzeeAdvisor) -> PolicyDecision:
        legal = scorecard.legal_scoring_categories(dice)
        if Category.LARGE_STRAIGHT in legal and is_large_straight(dice):
            return PolicyDecision(ActionType.SCORE_NOW, category=Category.LARGE_STRAIGHT, description="Score large straight.")
        if Category.FULL_HOUSE in legal and is_full_house(dice):
            return PolicyDecision(ActionType.SCORE_NOW, category=Category.FULL_HOUSE, description="Score full house.")
        if Category.SMALL_STRAIGHT in legal and is_small_straight(dice):
            return PolicyDecision(ActionType.SCORE_NOW, category=Category.SMALL_STRAIGHT, description="Score small straight.")
        if Category.SIXES in legal:
            sixes_score = sum(d for d in dice if d == 6)
            if sixes_score >= 18:
                return PolicyDecision(ActionType.SCORE_NOW, category=Category.SIXES, description="Take strong sixes.")
        best_cat, _, _ = advisor.best_score_now(dice, scorecard)
        return PolicyDecision(ActionType.SCORE_NOW, category=best_cat, description=f"Fallback to best score-now: {best_cat.value}.")

    def _score_or_best_hold_fallback(self, state: GameState, advisor: YahtzeeAdvisor) -> PolicyDecision:
        exact_policy = ObjectivePolicy("exact_turn_ev_fallback", OptimizationObjective.EXACT_TURN_EV)
        return exact_policy.decide(state, advisor)

    @staticmethod
    def _highest_n_of_a_kind_value(dice: tuple[int, ...], n: int) -> int | None:
        counts = Counter(dice)
        candidates = [value for value, count in counts.items() if count >= n]
        return max(candidates) if candidates else None

    @staticmethod
    def _best_large_straight_draw(dice: tuple[int, ...], scorecard: Scorecard) -> tuple[int, ...] | None:
        if Category.LARGE_STRAIGHT not in scorecard.open_categories():
            return None
        unique = set(dice)
        for run in ((1, 2, 3, 4), (2, 3, 4, 5), (3, 4, 5, 6)):
            if set(run).issubset(unique):
                return run
        return None

    @staticmethod
    def _best_small_straight_core(dice: tuple[int, ...], scorecard: Scorecard) -> tuple[int, ...] | None:
        if Category.SMALL_STRAIGHT not in scorecard.open_categories():
            return None
        unique = set(dice)
        for run in ((2, 3, 4), (3, 4, 5), (1, 2, 3), (4, 5, 6)):
            if set(run).issubset(unique):
                return run
        return None

    @staticmethod
    def _best_upper_pair_to_keep(dice: tuple[int, ...], scorecard: Scorecard) -> int | None:
        counts = Counter(dice)
        categories = [
            Category.ONES,
            Category.TWOS,
            Category.THREES,
            Category.FOURS,
            Category.FIVES,
            Category.SIXES,
        ]
        for value in (6, 5, 4, 3, 2, 1):
            category = categories[value - 1]
            if counts.get(value, 0) >= 2 and category in scorecard.open_categories():
                return value
        return None
