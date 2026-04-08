from __future__ import annotations

import streamlit as st

from yahtzee.advisor import YahtzeeAdvisor
from yahtzee.models import ALL_CATEGORIES, GameState, OptimizationObjective
from yahtzee.persistence import load_game, save_game
from yahtzee.state import GameManager
from yahtzee.ui_state import (
    ENTRY_MODE_COUNTS,
    ENTRY_MODE_QUICK,
    TURN_ENTRY_MODE_KEY,
    TURN_FACE_COUNT_KEYS,
    TURN_QUICK_ENTRY_KEY,
    TURN_ROLL_KEY,
    commit_turn_draft_to_manager,
    read_validated_turn_input,
    seed_turn_draft_from_manager,
    sync_turn_draft_after_authoritative_change,
)

st.set_page_config(page_title="Yahtzee Strategy Advisor", layout="wide")

if "manager" not in st.session_state:
    st.session_state.manager = GameManager(GameState())
if "advisor" not in st.session_state:
    st.session_state.advisor = YahtzeeAdvisor()
if "objective" not in st.session_state:
    st.session_state.objective = OptimizationObjective.BOARD_UTILITY

manager: GameManager = st.session_state.manager
advisor: YahtzeeAdvisor = st.session_state.advisor

seed_turn_draft_from_manager(st.session_state, manager)

st.title("🎲 Yahtzee Strategy Advisor")
st.caption("Exact reroll enumeration with selectable strategy objective and explicit Yahtzee-probability reporting.")

with st.sidebar:
    st.header("Game Controls")
    if st.button("New Game", use_container_width=True):
        st.session_state.manager = GameManager(GameState())
        sync_turn_draft_after_authoritative_change(st.session_state, st.session_state.manager)
        st.rerun()

    save_path = st.text_input("Save file", value="saved_games/yahtzee_game.json")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Save", use_container_width=True):
            save_game(st.session_state.manager.state, save_path)
            st.success("Saved")
    with c2:
        if st.button("Load", use_container_width=True):
            st.session_state.manager = GameManager(load_game(save_path))
            sync_turn_draft_after_authoritative_change(st.session_state, st.session_state.manager)
            st.success("Loaded")
            st.rerun()

    if st.button("Undo last action", use_container_width=True):
        if st.session_state.manager.undo():
            sync_turn_draft_after_authoritative_change(st.session_state, st.session_state.manager)
            st.success("Undid last action")
            st.rerun()
        else:
            st.warning("Nothing to undo")

    if st.button("Reset current turn", use_container_width=True):
        st.session_state.manager.reset_current_turn()
        sync_turn_draft_after_authoritative_change(st.session_state, st.session_state.manager)
        st.rerun()

    st.markdown("---")
    st.subheader("Strategy Mode")
    st.session_state.objective = st.selectbox(
        "Optimization objective",
        [
            OptimizationObjective.BOARD_UTILITY,
            OptimizationObjective.EXACT_TURN_EV,
            OptimizationObjective.MAXIMIZE_YAHTZEE_PROBABILITY,
        ],
        format_func=lambda o: {
            OptimizationObjective.BOARD_UTILITY: "Board-aware utility",
            OptimizationObjective.EXACT_TURN_EV: "Exact turn EV",
            OptimizationObjective.MAXIMIZE_YAHTZEE_PROBABILITY: "Maximize Yahtzee probability",
        }[o],
    )

    st.markdown("---")
    st.subheader("Rules summary")
    st.write(
        "13 turns, 3 rolls per turn, one box filled each turn, upper bonus +35 at 63+, with official extra-Yahtzee Joker placement rules."
    )

state = st.session_state.manager.state

left, right = st.columns([1.6, 1.1])

with left:
    st.subheader(f"Turn {state.turn_index}")

    with st.form("turn_entry_form"):
        st.radio("Roll number", [1, 2, 3], horizontal=True, key=TURN_ROLL_KEY)
        st.radio("Entry mode", [ENTRY_MODE_QUICK, ENTRY_MODE_COUNTS], horizontal=True, key=TURN_ENTRY_MODE_KEY)

        if st.session_state[TURN_ENTRY_MODE_KEY] == ENTRY_MODE_QUICK:
            st.text_input(
                "Dice",
                key=TURN_QUICK_ENTRY_KEY,
                help="Examples: 11116, 1 1 1 1 6, 1,1,1,1,6",
            )
        else:
            face_cols = st.columns(6)
            for idx, col in enumerate(face_cols):
                with col:
                    st.number_input(
                        f"{idx + 1}",
                        min_value=0,
                        max_value=5,
                        step=1,
                        key=TURN_FACE_COUNT_KEYS[idx],
                    )
            selected_total = sum(int(st.session_state.get(key, 0)) for key in TURN_FACE_COUNT_KEYS)
            st.caption(f"Dice selected: {selected_total} / 5")

        try:
            preview_dice, preview_roll = read_validated_turn_input(st.session_state)
            st.caption(f"Resolved dice: {preview_dice} (roll {preview_roll})")
        except ValueError as exc:
            st.warning(f"Preview: {exc}")

        apply_dice = st.form_submit_button("Apply Dice")

    if apply_dice:
        try:
            commit_turn_draft_to_manager(st.session_state, st.session_state.manager)
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    objective: OptimizationObjective = st.session_state.objective
    rec = advisor.recommend(
        st.session_state.manager.state.current_dice,
        st.session_state.manager.state.roll_number,
        st.session_state.manager.state.scorecard,
        objective=objective,
    )

    st.subheader("Recommendation")
    st.success(f"Best action: {rec.best_action.description}")
    st.write(f"Objective optimized: **{objective.value}**")
    st.write(rec.explanation)
    st.write(f"Best score-now fallback: **{rec.best_stop_category.value}** ({rec.best_stop_score})")
    st.write(f"Yahtzee probability (recommended line): **{rec.recommended_line_yahtzee_probability:.1%}**")
    st.write(f"Maximum possible Yahtzee probability from this state: **{rec.max_yahtzee_probability:.1%}**")

    st.markdown("#### Top 3 options")
    for i, action in enumerate(rec.top_actions, start=1):
        st.write(
            f"{i}. {action.description} | Objective value: {advisor.objective_value(action.exact_turn_ev, action.expected_value, action.yahtzee_probability, objective):.4f} "
            f"| Yahtzee: {action.yahtzee_probability:.1%} "
            f"| Utility: {action.expected_value:.2f} (exact turn EV: {action.exact_turn_ev:.2f}, board adj: {action.board_adjustment:+.2f})"
        )

    if rec.best_action.action_type.value == "HOLD_AND_REROLL" and rec.best_action.probabilities:
        st.markdown("#### Exact end-of-turn outcome classes (for this recommended policy line)")
        st.table(
            {
                "Outcome Class": list(rec.best_action.probabilities.keys()),
                "Probability": [f"{v:.1%}" for v in rec.best_action.probabilities.values()],
            }
        )

    st.markdown("#### Apply score")
    legal_categories = st.session_state.manager.state.scorecard.legal_scoring_categories(state.current_dice)
    selected = st.selectbox("Category", legal_categories, format_func=lambda c: c.value)
    if st.button("Apply category", type="primary"):
        try:
            gained = st.session_state.manager.apply_score(selected)
            sync_turn_draft_after_authoritative_change(st.session_state, st.session_state.manager)
            st.success(f"Scored {gained} in {selected.value}")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

with right:
    st.subheader("Scorecard")
    rows = []
    sc = state.scorecard
    for c in ALL_CATEGORIES:
        rows.append({"Category": c.value, "Score": sc.scores[c] if sc.scores[c] is not None else "-", "Filled": sc.scores[c] is not None})
    st.table(rows)
    st.write(f"Upper subtotal: {sc.upper_subtotal}")
    st.write(f"Upper bonus: {sc.upper_bonus}")
    st.write(f"Lower subtotal (+Yahtzee bonus): {sc.lower_subtotal}")
    st.write(f"Grand total: **{sc.grand_total}**")
