# Yahtzee Strategy Advisor

A local Streamlit app that helps you play a full game of standard 5-dice Yahtzee with mathematically explicit turn analysis and a live scorecard.

## What the app does

- Tracks a full 13-category Yahtzee scorecard
- Lets you enter current 5 dice and roll number (1/2/3)
- Recommends the best immediate action:
  - hold dice and reroll, or
  - score now in a legal category
- Shows top 3 options with:
  - exact turn-level continuation EV (for rerolls)
  - board-aware utility adjustment
  - final ranking utility
- Shows exact end-of-turn outcome-class probabilities for the recommended hold
- Applies selected scores with legality checks, updates totals, supports undo
- Saves/loads game state as local JSON

## Rules interpretation (explicit)

This app implements standard Yahtzee:

- 5d6, up to 3 rolls per turn
- 13 standard categories
- Upper bonus +35 at upper subtotal >= 63

### Yahtzee + Joker handling

- First Yahtzee can be scored in Yahtzee for 50.
- If Yahtzee category is **50**, each additional Yahtzee gives **+100** Yahtzee bonus.
- On additional Yahtzee with Yahtzee category = 50:
  - If matching upper category is open, you are forced to score there.
  - If matching upper category is closed, legal choices are open lower categories with Joker semantics.
  - If all lower categories are filled, any open upper category is legal.
- If Yahtzee category is **0** (or still unfilled), extra Yahtzee/Joker override is not active.

## What is exact vs heuristic

### Exact

- Exact reroll outcome enumeration (no Monte Carlo) for 0..5 rerolled dice.
- Exact turn-level continuation search over remaining rerolls.
- Exact recommended-hold end-of-turn probability classes under optimal continuation.
- Exact scorecard-state cache signature using every category score/unfilled state + Yahtzee bonus.

### Heuristic (board-aware)

- Final action ranking uses a board-aware utility layer in addition to exact turn EV.
- Utility adjustments are grounded in category baselines and upper-section progress, but this is not a full 13-turn optimal dynamic program.

## How to interpret the recommendation panel

- **Best action**: highest board-aware utility.
- **Exact turn EV**: exact expected raw turn score for that action under continuation model.
- **Board adjustment**: utility delta from board context.
- **Best score-now fallback**: best legal immediate scoring category if you stop now.
- **Outcome classes table**: exact probability of finishing the turn in each mutually exclusive class for the recommended hold.

## Limitations

- Not a proven full-game optimal solver across all 13 future turns.
- Utility calibration is principled but still model-based.
- Outcome classes summarize hand types, not full category score distributions.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

## Test

```bash
pytest -q
```
