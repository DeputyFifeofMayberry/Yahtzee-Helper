from yahtzee.advisor import YahtzeeAdvisor
from yahtzee.models import OptimizationObjective, Scorecard


def test_maximize_yahtzee_probability_benchmark_four_of_a_kind_opening():
    advisor = YahtzeeAdvisor()
    scorecard = Scorecard()

    rec = advisor.recommend([1, 1, 1, 1, 6], 1, scorecard, objective=OptimizationObjective.MAXIMIZE_YAHTZEE_PROBABILITY)

    assert rec.best_action.held_dice == (1, 1, 1, 1)
    assert abs(rec.recommended_line_yahtzee_probability - (11.0 / 36.0)) < 1e-12
    assert abs(rec.max_yahtzee_probability - (11.0 / 36.0)) < 1e-12


def test_semantic_separation_recommended_line_vs_max_yahtzee_probability():
    advisor = YahtzeeAdvisor()
    scorecard = Scorecard()

    rec = advisor.recommend([1, 1, 1, 1, 6], 1, scorecard, objective=OptimizationObjective.BOARD_UTILITY)

    assert rec.recommended_line_yahtzee_probability <= rec.max_yahtzee_probability
    assert rec.recommended_line_yahtzee_probability != rec.max_yahtzee_probability


def test_outcome_distribution_uses_selected_objective_consistently():
    advisor = YahtzeeAdvisor()
    scorecard = Scorecard()

    rec = advisor.recommend([1, 1, 1, 1, 6], 1, scorecard, objective=OptimizationObjective.MAXIMIZE_YAHTZEE_PROBABILITY)
    hold = rec.best_action.held_dice
    assert hold is not None

    dist = advisor.optimal_turn_outcome_probabilities(hold, 2, scorecard, objective=OptimizationObjective.MAXIMIZE_YAHTZEE_PROBABILITY)

    assert abs(sum(dist.values()) - 1.0) < 1e-12
    assert abs(dist["Yahtzee"] - rec.recommended_line_yahtzee_probability) < 1e-12
