# Yahtzee Strategy Advisor

A local Streamlit app that helps you play a full game of standard 5-dice Yahtzee with mathematically explicit turn analysis and a live scorecard.

## What the app does

- Tracks a full 13-category Yahtzee scorecard.
- Lets you enter current 5 dice and roll number (1/2/3).
- Recommends the best immediate action (hold+reraoll or score now) under a selected optimization objective.
- Shows top 3 options with:
  - objective value,
  - exact turn EV,
  - board-aware utility,
  - Yahtzee probability for that option.
- Shows exact end-of-turn outcome-class probabilities for the recommended policy line.
- Shows both:
  - Yahtzee probability under the currently recommended line, and
  - maximum possible Yahtzee probability from the current state.
- Applies selected scores with legality checks, updates totals, supports undo.
- Saves/loads game state as local JSON.

## Strategy modes (what is optimized)

The app supports three explicit optimization objectives:

1. **Board-aware utility** (`BOARD_UTILITY`)
   - Primary objective: board-adjusted utility.
   - Uses exact turn EV plus scorecard-aware adjustments.

2. **Exact turn EV** (`EXACT_TURN_EV`)
   - Primary objective: expected points scored this turn (exact enumeration).
   - No board-adjusted objective priority.

3. **Maximize Yahtzee probability** (`MAXIMIZE_YAHTZEE_PROBABILITY`)
   - Primary objective: highest probability of ending the turn with a Yahtzee.
   - Still uses exact reroll enumeration (no Monte Carlo).

The same objective is used consistently at top-level recommendation, recursive continuation choice, and final outcome distribution reporting.

## What is exact vs heuristic

### Exact

- Exact reroll outcome enumeration for 0..5 rerolled dice (no Monte Carlo).
- Exact continuation recursion over remaining rerolls.
- Exact policy-consistent continuation selection for each objective.
- Exact scorecard-state cache signature with all category values + Yahtzee bonus.
- Exact legality checks, including Joker placement constraints.
- Exact Yahtzee-chase probabilities:
  - under the selected recommendation line,
  - and maximum possible from the current state.

### Heuristic / model-based

- **Only** the board-aware utility objective applies heuristic shaping.
- `BOARD_UTILITY` is now an interpretable blend of exact turn EV plus board-state adjustments for:
  - upper-bonus race progress (dynamic by subtotal, need-to-63, and open upper boxes),
  - scarce-category value (especially made straights),
  - straight-core and straight-draw preservation on early rolls,
  - full-house take-vs-break context (low FHs are more often banked; high FHs can be broken),
  - opening four-of-a-kind Yahtzee chase pressure,
  - dynamic sacrifice-slot pressure (e.g., Chance preserved as a bailout box early more often).
- `EXACT_TURN_EV` remains mathematically aligned to pure expected points this turn.
- `MAXIMIZE_YAHTZEE_PROBABILITY` remains mathematically aligned to pure Yahtzee probability.
- The board-aware objective is intentionally practical, but it is not a full-game optimal dynamic program over all 13 future turns.

## Yahtzee probability semantics

The displayed Yahtzee percentages have two different meanings:

- **Yahtzee probability (recommended line):**
  Probability of ending this turn with Yahtzee if you follow the currently selected recommendation policy.

- **Maximum possible Yahtzee probability from this state:**
  Best achievable Yahtzee chance from this same state if you optimize specifically for Yahtzee probability.

These can differ intentionally. For example, board-aware utility may prefer a hold with slightly lower Yahtzee chance but better expected scoring utility.

Additional board-aware examples now modeled:
- Preserve **2-3-4** or **3-4-5** cores early when Small Straight is still open.
- Preserve **1-2-3-4 / 2-3-4-5 / 3-4-5-6** on early rolls when Large Straight is still open.
- Treat made Large Straights as premium scarce outcomes when the category is open.
- Take low full houses (e.g., 2-2-3-3-3) more readily than high full houses (e.g., 5-5-6-6-6), which are sometimes broken for upside.
- Preserve Chance as a flexible bailout box more often early game instead of dumping it by default.

### Concrete example

State:
- roll = `[1, 1, 1, 1, 6]`
- roll number = `1` (two rerolls remaining)
- empty scorecard

In **Maximize Yahtzee probability** mode, the optimal line is to hold four 1s and reroll the sixth die on both remaining rolls if needed.

Resulting Yahtzee probability is:

- `11/36 = 0.3055555555555556`

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
- If matching upper is filled and any lower category is open, legal choices are **exactly open lower categories**, scored with Joker semantics.
- If matching upper is filled and all lower categories are filled, legal choices are **exactly open upper categories**.

## UI state integrity fix

Turn-entry widgets now use explicit, stable session-state keys:

- `turn_die_1` .. `turn_die_5`
- `turn_roll_number`

State ownership is explicit:

- Widget state owns in-progress turn input during normal interaction.
- Backend manager state syncs into widget state **only** at authoritative sync points:
  - initial load,
  - New Game,
  - Load,
  - Undo,
  - Reset current turn,
  - Apply category.

This prevents the previous first-click bounce-back/false-input issue caused by reruns repeatedly rebuilding widget defaults from backend state.

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
