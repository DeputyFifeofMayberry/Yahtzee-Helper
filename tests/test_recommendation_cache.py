from yahtzee.models import Category, OptimizationObjective, Scorecard
from yahtzee.recommendation_service import (
    build_turn_analysis_fingerprint,
    clear_turn_analysis_state,
    compute_recommendation_payload,
    mark_turn_analysis_stale,
    recommendation_from_payload,
)


def test_fingerprint_changes_for_all_material_inputs():
    sc = Scorecard()
    base_sig = sc.score_signature()

    base = build_turn_analysis_fingerprint(
        dice=[1, 2, 3, 4, 5],
        roll_number=1,
        score_signature=base_sig,
        objective=OptimizationObjective.BOARD_UTILITY,
    )
    assert base != build_turn_analysis_fingerprint(
        dice=[1, 2, 3, 4, 6],
        roll_number=1,
        score_signature=base_sig,
        objective=OptimizationObjective.BOARD_UTILITY,
    )
    assert base != build_turn_analysis_fingerprint(
        dice=[1, 2, 3, 4, 5],
        roll_number=2,
        score_signature=base_sig,
        objective=OptimizationObjective.BOARD_UTILITY,
    )

    sc.scores[Category.ONES] = 3
    assert base != build_turn_analysis_fingerprint(
        dice=[1, 2, 3, 4, 5],
        roll_number=1,
        score_signature=sc.score_signature(),
        objective=OptimizationObjective.BOARD_UTILITY,
    )
    assert base != build_turn_analysis_fingerprint(
        dice=[1, 2, 3, 4, 5],
        roll_number=1,
        score_signature=base_sig,
        objective=OptimizationObjective.EXACT_TURN_EV,
    )


def test_clear_and_stale_analysis_state_flow():
    session_state: dict[str, object] = {
        "turn_analysis_result": {"foo": "bar"},
        "turn_analysis_fingerprint": (1,),
        "turn_analysis_requested": True,
        "turn_analysis_stale": False,
    }
    mark_turn_analysis_stale(session_state)
    assert session_state["turn_analysis_stale"] is True

    clear_turn_analysis_state(session_state)
    assert session_state["turn_analysis_result"] is None
    assert session_state["turn_analysis_fingerprint"] is None
    assert session_state["turn_analysis_requested"] is False
    assert session_state["turn_analysis_stale"] is False


def test_recommendation_payload_round_trip_and_default_has_no_probabilities():
    scorecard = Scorecard()
    payload = compute_recommendation_payload(
        dice=(6, 6, 6, 2, 1),
        roll_number=1,
        score_signature=scorecard.score_signature(),
        objective_value=OptimizationObjective.BOARD_UTILITY.value,
        include_probabilities=False,
        top_n=3,
    )
    rec = recommendation_from_payload(payload)
    assert rec.best_action.probabilities == {}
