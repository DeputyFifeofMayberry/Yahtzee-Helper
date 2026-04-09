from yahtzee.advisor import YahtzeeAdvisor
from yahtzee.models import ActionType, OptimizationObjective, Scorecard


def test_recommend_default_does_not_compute_exact_probabilities(monkeypatch):
    advisor = YahtzeeAdvisor()
    calls = {"count": 0}

    def spy(*args, **kwargs):
        calls["count"] += 1
        return {"Yahtzee": 1.0}

    monkeypatch.setattr(advisor, "optimal_turn_outcome_probabilities", spy)

    rec = advisor.recommend([6, 6, 6, 2, 1], 1, Scorecard(), objective=OptimizationObjective.BOARD_UTILITY)
    assert calls["count"] == 0
    assert rec.best_action.probabilities == {}


def test_recommend_can_compute_best_action_probabilities_only(monkeypatch):
    advisor = YahtzeeAdvisor()
    calls = {"count": 0}

    def spy(*args, **kwargs):
        calls["count"] += 1
        return {"Yahtzee": 0.25, "Any": 0.75}

    monkeypatch.setattr(advisor, "optimal_turn_outcome_probabilities", spy)

    rec = advisor.recommend(
        [6, 6, 6, 2, 1],
        1,
        Scorecard(),
        objective=OptimizationObjective.BOARD_UTILITY,
        include_probabilities=True,
    )

    assert rec.best_action.action_type == ActionType.HOLD_AND_REROLL
    assert calls["count"] == 1
    assert rec.best_action.probabilities["Yahtzee"] == 0.25
    assert all(action.probabilities == {} for action in rec.top_actions[1:])
