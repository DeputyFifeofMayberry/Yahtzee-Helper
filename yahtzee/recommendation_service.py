from __future__ import annotations

from typing import Any

from yahtzee.advisor import YahtzeeAdvisor
from yahtzee.models import ActionType, CandidateAction, Category, OptimizationObjective, Recommendation, Scorecard
from yahtzee.state import GameManager


def build_turn_analysis_fingerprint(
    *,
    dice: list[int],
    roll_number: int,
    score_signature: tuple[tuple[int | None, ...], int],
    objective: OptimizationObjective,
) -> tuple[tuple[int, ...], int, tuple[tuple[int | None, ...], int], str]:
    """Stable fingerprint for recommendation validity across reruns."""
    return (tuple(dice), int(roll_number), score_signature, objective.value)


def clear_turn_analysis_state(session_state: dict[str, Any]) -> None:
    session_state["turn_analysis_result"] = None
    session_state["turn_analysis_fingerprint"] = None
    session_state["turn_analysis_requested"] = False
    session_state["turn_analysis_stale"] = False
    session_state["turn_analysis_breakdown"] = None
    session_state["turn_analysis_breakdown_fingerprint"] = None


def mark_turn_analysis_stale(session_state: dict[str, Any]) -> None:
    if session_state.get("turn_analysis_result") is None:
        session_state["turn_analysis_stale"] = False
        return
    session_state["turn_analysis_stale"] = True


def recommendation_to_payload(rec: Recommendation) -> dict[str, Any]:
    return {
        "best_action": _candidate_to_payload(rec.best_action),
        "top_actions": [_candidate_to_payload(action) for action in rec.top_actions],
        "best_stop_category": rec.best_stop_category.value,
        "best_stop_score": rec.best_stop_score,
        "explanation": rec.explanation,
        "objective": rec.objective.value,
        "recommended_line_yahtzee_probability": rec.recommended_line_yahtzee_probability,
        "max_yahtzee_probability": rec.max_yahtzee_probability,
    }


def recommendation_from_payload(payload: dict[str, Any]) -> Recommendation:
    return Recommendation(
        best_action=_candidate_from_payload(payload["best_action"]),
        top_actions=[_candidate_from_payload(action_payload) for action_payload in payload["top_actions"]],
        best_stop_category=Category(payload["best_stop_category"]),
        best_stop_score=int(payload["best_stop_score"]),
        explanation=str(payload["explanation"]),
        objective=OptimizationObjective(payload["objective"]),
        recommended_line_yahtzee_probability=float(payload["recommended_line_yahtzee_probability"]),
        max_yahtzee_probability=float(payload["max_yahtzee_probability"]),
    )


def compute_recommendation_payload(
    *,
    dice: tuple[int, ...],
    roll_number: int,
    score_signature: tuple[tuple[int | None, ...], int],
    objective_value: str,
    include_probabilities: bool,
    top_n: int,
) -> dict[str, Any]:
    advisor = YahtzeeAdvisor()
    scorecard = Scorecard.from_signature(score_signature)
    objective = OptimizationObjective(objective_value)
    recommendation = advisor.recommend(
        list(dice),
        int(roll_number),
        scorecard,
        objective=objective,
        include_probabilities=bool(include_probabilities),
        top_n=int(top_n),
    )
    return recommendation_to_payload(recommendation)


def compute_exact_breakdown_payload(
    *,
    held_dice: tuple[int, ...],
    roll_number: int,
    score_signature: tuple[tuple[int | None, ...], int],
    objective_value: str,
) -> dict[str, float]:
    advisor = YahtzeeAdvisor()
    scorecard = Scorecard.from_signature(score_signature)
    objective = OptimizationObjective(objective_value)
    rolls_remaining = max(0, 3 - int(roll_number))
    return advisor.optimal_turn_outcome_probabilities(tuple(sorted(held_dice)), rolls_remaining, scorecard, objective)


def build_score_signature_for_manager(manager: GameManager) -> tuple[tuple[int | None, ...], int]:
    return manager.state.scorecard.score_signature()


def _candidate_to_payload(candidate: CandidateAction) -> dict[str, Any]:
    return {
        "action_type": candidate.action_type.value,
        "held_dice": list(candidate.held_dice) if candidate.held_dice is not None else None,
        "category": candidate.category.value if candidate.category is not None else None,
        "expected_value": candidate.expected_value,
        "exact_turn_ev": candidate.exact_turn_ev,
        "board_adjustment": candidate.board_adjustment,
        "description": candidate.description,
        "probabilities": dict(candidate.probabilities),
        "yahtzee_probability": candidate.yahtzee_probability,
    }


def _candidate_from_payload(payload: dict[str, Any]) -> CandidateAction:
    held_dice = payload.get("held_dice")
    return CandidateAction(
        action_type=ActionType(payload["action_type"]),
        held_dice=tuple(held_dice) if isinstance(held_dice, list) else None,
        category=Category(payload["category"]) if payload.get("category") else None,
        expected_value=float(payload["expected_value"]),
        exact_turn_ev=float(payload["exact_turn_ev"]),
        board_adjustment=float(payload["board_adjustment"]),
        description=str(payload["description"]),
        probabilities=dict(payload.get("probabilities", {})),
        yahtzee_probability=float(payload["yahtzee_probability"]),
    )
