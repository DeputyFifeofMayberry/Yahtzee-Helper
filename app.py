from __future__ import annotations

import streamlit as st

from yahtzee.advisor import YahtzeeAdvisor
from yahtzee.models import ALL_CATEGORIES, GameState
from yahtzee.persistence import load_game, save_game
from yahtzee.state import GameManager

st.set_page_config(page_title="Yahtzee Strategy Advisor", layout="wide")

if "manager" not in st.session_state:
    st.session_state.manager = GameManager(GameState())
if "advisor" not in st.session_state:
    st.session_state.advisor = YahtzeeAdvisor()

manager: GameManager = st.session_state.manager
advisor: YahtzeeAdvisor = st.session_state.advisor

st.title("🎲 Yahtzee Strategy Advisor")
st.caption(
    "Exact turn-level continuation EV for rerolls, plus a separate board-aware utility adjustment for final ranking."
)

with st.sidebar:
    st.header("Game Controls")
    if st.button("New Game", use_container_width=True):
        st.session_state.manager = GameManager(GameState())
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
            st.success("Loaded")
            st.rerun()

    if st.button("Undo last action", use_container_width=True):
        if st.session_state.manager.undo():
            st.success("Undid last action")
            st.rerun()
        else:
            st.warning("Nothing to undo")

    if st.button("Reset current turn", use_container_width=True):
        st.session_state.manager.reset_current_turn()
        st.rerun()

    st.markdown("---")
    st.subheader("Rules summary")
    st.write("13 categories, 3 rolls per turn, upper bonus +35 at 63, Yahtzee bonuses +100 with Joker rule.")

state = st.session_state.manager.state

left, right = st.columns([1.6, 1.1])

with left:
    st.subheader(f"Turn {state.turn_index}")
    dice_cols = st.columns(5)
    dice = []
    for i, col in enumerate(dice_cols):
        with col:
            dice.append(st.selectbox(f"Die {i + 1}", [1, 2, 3, 4, 5, 6], index=state.current_dice[i] - 1))

    roll_num = st.radio("Roll number", [1, 2, 3], index=state.roll_number - 1, horizontal=True)

    try:
        st.session_state.manager.set_current_roll(dice, roll_num)
    except ValueError as exc:
        st.error(str(exc))

    rec = advisor.recommend(
        st.session_state.manager.state.current_dice,
        st.session_state.manager.state.roll_number,
        st.session_state.manager.state.scorecard,
    )

    st.subheader("Recommendation")
    st.success(f"Best action: {rec.best_action.description}")
    st.write(rec.explanation)
    st.write(f"Best score-now fallback: **{rec.best_stop_category.value}** ({rec.best_stop_score})")

    st.markdown("#### Top 3 options")
    for i, action in enumerate(rec.top_actions, start=1):
        st.write(
            f"{i}. {action.description} | Final utility: {action.expected_value:.2f} "
            f"(exact turn EV: {action.exact_turn_ev:.2f}, board adj: {action.board_adjustment:+.2f})"
        )

    if rec.best_action.action_type.value == "HOLD_AND_REROLL" and rec.best_action.probabilities:
        st.markdown("#### Exact end-of-turn outcome classes (recommended hold)")
        st.table({"Outcome Class": list(rec.best_action.probabilities.keys()), "Probability": [f"{v:.1%}" for v in rec.best_action.probabilities.values()]})

    st.markdown("#### Apply score")
    legal_categories = st.session_state.manager.state.scorecard.legal_scoring_categories(state.current_dice)
    selected = st.selectbox("Category", legal_categories, format_func=lambda c: c.value)
    if st.button("Apply category", type="primary"):
        try:
            gained = st.session_state.manager.apply_score(selected)
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
