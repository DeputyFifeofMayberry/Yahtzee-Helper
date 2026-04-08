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

## Official rule interpretation implemented

This app implements standard Hasbro Yahtzee scoring and legality behavior:

- 5 dice, up to 3 rolls per turn
- 13-turn game, one score box must be filled each turn
- Filled score boxes cannot be reused
- Upper section categories score matching pips
- Upper bonus is +35 when upper subtotal is 63 or higher
- Lower section scoring:
  - Three of a Kind: total of all 5 dice if legal, else 0
  - Four of a Kind: total of all 5 dice if legal, else 0
  - Full House: 25
  - Small Straight: 30
  - Large Straight: 40
  - Yahtzee: 50
  - Chance: total of all 5 dice

### Extra Yahtzee and Joker handling

When a Yahtzee is rolled and the Yahtzee box is already filled, this app applies official Joker placement order:

1. **If Yahtzee box is 50**
   - Award +100 Yahtzee bonus.
   - Then apply Joker placement constraints below.
2. **If Yahtzee box is 0**
   - Do **not** award +100 bonus.
   - Still apply Joker placement constraints below.

Joker placement constraints:

- If the matching upper category is open, it is the **only legal category**.
- If matching upper is filled and any lower category is open, legal choices are **exactly open lower categories**, scored with Joker semantics:
  - Three/Four of a Kind: total of all 5 dice
  - Full House: 25
  - Small Straight: 30
  - Large Straight: 40
  - Chance: total of all 5 dice
- If matching upper is filled and all lower categories are filled, legal choices are **exactly open upper categories**.
  - Matching upper scores normal pip total.
  - Non-matching open upper categories score 0.

If the Yahtzee box is still unfilled and you roll a Yahtzee, no extra-Yahtzee bonus/Joker override is used yet; normal category selection applies.

## What is exact vs heuristic

### Exact

- Exact reroll outcome enumeration (no Monte Carlo) for 0..5 rerolled dice.
- Exact turn-level continuation search over remaining rerolls.
- Exact recommended-hold end-of-turn probability classes under optimal continuation.
- Exact scorecard-state cache signature using every category score/unfilled state + Yahtzee bonus.
- Exact legality gating for score-now choices under ordinary and Joker contexts.

### Heuristic (board-aware)

- Final action ranking uses a board-aware utility layer in addition to exact turn EV.
- Utility adjustments are grounded in category baselines and upper-section progress, but this is not a full 13-turn optimal dynamic program.

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
