# Yahtzee Strategy Advisor

A local Streamlit app that helps you play a full game of standard 5-dice Yahtzee with **odds-based recommendations** and a live scorecard.

## What the app does

- Tracks a full 13-category Yahtzee scorecard
- Lets you enter current 5 dice and roll number (1/2/3)
- Recommends the best immediate action:
  - hold dice and reroll, or
  - score now in a category
- Shows top 3 options with expected utility
- Shows key probabilities (Yahtzee, Full House, straights, kinds)
- Applies selected scores, updates totals, supports undo
- Saves/loads game state as local JSON

## Tech stack

- Python 3.11+
- Streamlit UI
- Pure-Python game logic and advisor engine
- pytest test suite

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

## Rules interpretation

This app implements standard Yahtzee:

- 5d6, up to 3 rolls per turn
- 13 standard categories
- Upper bonus +35 at upper subtotal >= 63
- Additional Yahtzees after first scored Yahtzee (50) grant +100 each
- Joker handling:
  - If extra Yahtzee occurs and the corresponding upper box is open, you must score there.
  - Otherwise, you can score in lower categories using Joker semantics
    (Full House = 25, Small Straight = 30, Large Straight = 40,
    3/4-kind count as sum)

## How the advisor works

The advisor is intentionally a **decision aid**, not a full perfect-game solver.

It combines:

1. **Exact current-turn odds / EV engine**
   - Generates all distinct legal holds from current roll
   - Enumerates exact reroll outcome distributions
   - Computes expected utility across remaining rerolls
   - Uses caching and canonical dice representation for responsiveness

2. **Board-aware utility layer**
   - Evaluates final score choices with context:
     - immediate score
     - upper bonus pressure
     - preserving flexible categories (e.g., Chance)
     - scarcity/difficulty weighting for hard categories
     - late-game tradeoffs

This yields advice that behaves more like a strong human player with math support.

## Limitations

- Not a full-horizon dynamic program over all 13 future turns
- Board-aware utility is tunable heuristic weighting (documented in code)
- Probability panel focuses on key outcomes and recommended hold

## Example usage

1. Start new game
2. Enter dice and current roll number
3. Review best action and top alternatives
4. Apply chosen category score
5. Save game as JSON and resume later

## Project tree

```text
.
├── app.py
├── requirements.txt
├── README.md
├── yahtzee
│   ├── __init__.py
│   ├── advisor.py
│   ├── models.py
│   ├── persistence.py
│   ├── probabilities.py
│   ├── rules.py
│   ├── scoring.py
│   ├── state.py
│   └── utils.py
└── tests
    ├── test_advisor.py
    ├── test_rules.py
    ├── test_scoring.py
    └── test_state.py
```
