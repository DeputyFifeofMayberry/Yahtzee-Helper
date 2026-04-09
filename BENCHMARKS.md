# Yahtzee strategy comparison benchmark harness

This repository includes a headless benchmark engine for comparing four strategy styles:

1. `board_utility`
2. `exact_turn_ev`
3. `human_heuristic`
4. `rollout_oracle`

## Run depth modes (fast vs deep)

The benchmark engine supports three depth profiles for browser and CLI use:

- **Fast Check (`mode=fast`)**
  - Small full-game sample.
  - Very small best-known-choice comparison sample.
  - Designed for quick browser feedback.
- **Standard Comparison (`mode=standard`)**
  - Moderate full-game sample.
  - Moderate best-known-choice comparison.
  - Good default for day-to-day comparisons.
- **Deep Analysis (`mode=deep`)**
  - Large full-game sample.
  - Larger best-known-choice comparison and rollout depth.
  - Use when you need higher-confidence benchmarking.

The rollout oracle remains intentionally expensive and should be used as a benchmark reference, not a default gameplay policy.

## What it measures

### How each strategy scored (full-game metrics)
- Average Final Score
- Median Final Score
- Low-end / High-end Score Range (P10/P90)
- Upper Bonus Hit Rate
- Average Upper Subtotal
- Yahtzee Rate
- Extra Yahtzee Bonus Rate
- Average Zeros per Game
- How Often This Box Ended Up as 0
- Average Score by Category

### How often each strategy matched the best known choice
For sampled in-game decision states, each strategy is compared to the rollout oracle reference.

- Matched Best-Known Choice (oracle agreement rate)
- Average Points Lost vs Best-Known Choice (regret)
- Median / high-end regret
- Severe misses (>3 and >5 points)
- Breakdowns by roll number and state type tags

## In-app page

Run Streamlit and open **Strategy Test Lab** from the sidebar:

```bash
streamlit run app.py
```

The page is optimized for normal browser users first:
- plain-English labels and help text
- Fast / Standard / Deep presets that autofill but stay editable
- advanced settings hidden behind an expander
- run-cost estimate and heavy-run warnings
- detailed data and downloads still available

## CLI workflow

Run with mode defaults:

```bash
python scripts/run_benchmarks.py --mode standard
```

Run deep analysis:

```bash
python scripts/run_benchmarks.py --mode deep
```

Override specific values while keeping mode defaults:

```bash
python scripts/run_benchmarks.py --mode standard --full-games 120 --state-sample-size 70
```

Use fully custom settings:

```bash
python scripts/run_benchmarks.py --mode custom --full-games 250 --oracle-games 40 --state-sample-games 80 --state-sample-size 120 --state-sample-rate 0.35 --oracle-rollouts 40
```

Outputs are written to `benchmark_results/` by default:
- `full_game_results.csv`
- `oracle_comparisons.csv`
- `full_game_summary.json`
- `oracle_summary.json`
