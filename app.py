from __future__ import annotations

import streamlit as st

from yahtzee.advisor import YahtzeeAdvisor
from yahtzee.models import ALL_CATEGORIES, ActionType, GameState, OptimizationObjective
from yahtzee.persistence import load_game, save_game
from yahtzee.state import GameManager
from yahtzee.ui_state import (
    ENTRY_MODE_COUNTS,
    ENTRY_MODE_QUICK,
    STAGED_RECOMMENDED_ACTION_KEY,
    TURN_ENTRY_MODE_KEY,
    TURN_FACE_COUNT_KEYS,
    TURN_QUICK_ENTRY_KEY,
    TURN_ROLL_KEY,
    clear_staged_recommended_action,
    commit_turn_draft_to_manager,
    consume_pending_turn_draft_sync,
    get_staged_recommended_action,
    read_validated_turn_input,
    request_turn_draft_sync_from_manager,
    seed_turn_draft_from_manager,
    stage_recommended_hold,
    build_hold_mask_for_current_dice,
)

st.set_page_config(page_title="Yahtzee Strategy Advisor", layout="wide")

if "manager" not in st.session_state:
    st.session_state.manager = GameManager(GameState())
if "advisor" not in st.session_state:
    st.session_state.advisor = YahtzeeAdvisor()
if "objective" not in st.session_state:
    st.session_state.objective = OptimizationObjective.BOARD_UTILITY
if STAGED_RECOMMENDED_ACTION_KEY not in st.session_state:
    st.session_state[STAGED_RECOMMENDED_ACTION_KEY] = None

manager: GameManager = st.session_state.manager
advisor: YahtzeeAdvisor = st.session_state.advisor

seed_turn_draft_from_manager(st.session_state, manager)
consume_pending_turn_draft_sync(st.session_state)


def refresh_turn_draft_and_rerun(*, clear_staged: bool = False) -> None:
    if clear_staged:
        clear_staged_recommended_action(st.session_state)
    request_turn_draft_sync_from_manager(st.session_state, st.session_state.manager)
    st.rerun()


def render_die_marker(position: int, die_value: int, keep: bool) -> str:
    marker = "✅ KEEP" if keep else "🔁 REROLL"
    return f"<div style='border:1px solid #d9d9d9;border-radius:8px;padding:0.5rem;text-align:center;'><strong>Die {position}</strong><br/><span style='font-size:1.2rem;'>🎲 {die_value}</span><br/>{marker}</div>"


def staged_action_matches_current_turn(staged: dict | None) -> bool:
    if not staged:
        return False
    state = st.session_state.manager.state
    return (
        staged.get("turn_index") == state.turn_index
        and staged.get("source_roll") == state.roll_number
        and staged.get("source_dice") == state.current_dice
    )


if not staged_action_matches_current_turn(get_staged_recommended_action(st.session_state)):
    clear_staged_recommended_action(st.session_state)

st.title("🎲 Yahtzee Strategy Advisor")
st.caption("Exact reroll enumeration with selectable strategy objective and explicit Yahtzee-probability reporting.")

with st.sidebar:
    st.header("Game Controls")
    if st.button("New Game", use_container_width=True):
        st.session_state.manager = GameManager(GameState())
        refresh_turn_draft_and_rerun(clear_staged=True)

    save_path = st.text_input("Save file", value="saved_games/yahtzee_game.json")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Save", use_container_width=True):
            save_game(st.session_state.manager.state, save_path)
            st.success("Saved")
    with c2:
        if st.button("Load", use_container_width=True):
            st.session_state.manager = GameManager(load_game(save_path))
            st.success("Loaded")
            refresh_turn_draft_and_rerun(clear_staged=True)

    if st.button("Undo last action", use_container_width=True):
        if st.session_state.manager.undo():
            st.success("Undid last action")
            refresh_turn_draft_and_rerun(clear_staged=True)
        else:
            st.warning("Nothing to undo")

    if st.button("Reset current turn", use_container_width=True):
        st.session_state.manager.reset_current_turn()
        refresh_turn_draft_and_rerun(clear_staged=True)

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
            clear_staged_recommended_action(st.session_state)
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

    st.markdown("#### Apply recommended action")
    if rec.best_action.action_type == ActionType.SCORE_NOW and rec.best_action.category is not None:
        recommended_score = state.scorecard.legal_score_previews(state.current_dice).get(rec.best_action.category)
        score_label = (
            f"Score {rec.best_action.category.value} now for {recommended_score}"
            if recommended_score is not None
            else f"Score {rec.best_action.category.value} now"
        )
        if st.button(score_label, key="apply_recommended_score", type="primary", use_container_width=True):
            try:
                gained = st.session_state.manager.apply_score(rec.best_action.category)
                st.success(f"Scored {gained} in {rec.best_action.category.value}")
                refresh_turn_draft_and_rerun(clear_staged=True)
            except ValueError as exc:
                st.error(str(exc))

    if rec.best_action.action_type == ActionType.HOLD_AND_REROLL and rec.best_action.held_dice is not None:
        with st.container(border=True):
            held = list(rec.best_action.held_dice)
            reroll_count = 5 - len(held)
            st.write(f"Keep **{held if held else 'no dice'}** and reroll **{reroll_count}** dice.")

            staged = get_staged_recommended_action(st.session_state)
            keep_mask = staged.get("keep_mask") if staged_action_matches_current_turn(staged) else None
            if not keep_mask:
                try:
                    keep_mask = build_hold_mask_for_current_dice(list(state.current_dice), rec.best_action.held_dice)
                except ValueError as exc:
                    st.error(str(exc))
                    keep_mask = [False] * 5

            cols = st.columns(5)
            for idx, col in enumerate(cols):
                with col:
                    st.markdown(render_die_marker(idx + 1, state.current_dice[idx], bool(keep_mask[idx])), unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                if st.button("Use recommended hold", key="use_recommended_hold", type="primary", use_container_width=True):
                    try:
                        staged_payload = stage_recommended_hold(
                            st.session_state,
                            turn_index=state.turn_index,
                            current_dice=list(state.current_dice),
                            current_roll=state.roll_number,
                            held_dice=rec.best_action.held_dice,
                        )
                        next_roll = int(staged_payload["next_roll"])
                        st.session_state.manager.set_current_roll(list(state.current_dice), next_roll)
                        request_turn_draft_sync_from_manager(st.session_state, st.session_state.manager)
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
            with c2:
                if st.button("Clear staged hold", key="clear_recommended_hold", use_container_width=True):
                    clear_staged_recommended_action(st.session_state)
                    st.rerun()

            if staged_action_matches_current_turn(get_staged_recommended_action(st.session_state)):
                st.success("Recommended hold staged. Keep marked dice and reroll the others in real life.")
                st.info("Keep the marked dice, reroll the others in real life, then enter the new 5-die result above and click Apply Dice.")

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
            st.success(f"Scored {gained} in {selected.value}")
            refresh_turn_draft_and_rerun(clear_staged=True)
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
