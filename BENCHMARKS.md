# Yahtzee policy benchmark harness

This repository now includes a headless benchmark harness for comparing four policy styles:

1. `board_utility`
2. `exact_turn_ev`
3. `human_heuristic`
4. `rollout_oracle`

## What it measures

### Full-game metrics
- average final score
- median final score
- p10 / p90 final score
- upper bonus hit rate
- average upper subtotal
- Yahtzee rate
- extra Yahtzee bonus rate
- average zeros per game
- zero rate by category
- average score by category

### Oracle-comparison metrics
The rollout oracle is used as the stronger reference policy.

For sampled in-game states, each policy is compared against the rollout oracle on:
- oracle agreement rate
- average regret
- median regret
- p90 regret
- severe miss rate > 3 points
- severe miss rate > 5 points

The comparison is also sliced by:
- roll number
- game phase
- made full house
- made straight
- opening four of a kind
- upper bonus pressure
- bailout states

## How to run

```bash
python scripts/run_benchmarks.py
```

Useful options:

```bash
python scripts/run_benchmarks.py --full-games 1000 --oracle-games 100 --state-sample-size 250 --oracle-rollouts 80
```

Outputs are written to `benchmark_results/` by default:
- `full_game_results.csv`
- `oracle_comparisons.csv`
- `full_game_summary.json`
- `oracle_summary.json`

## Notes

- `BOARD_UTILITY` remains a heuristic policy.
- `EXACT_TURN_EV` remains an exact single-turn EV objective.
- `rollout_oracle` is intentionally expensive and should be treated as the benchmark reference, not the default gameplay policy.
- The human heuristic policy is intentionally simpler than the board-aware advisor so you can tell whether the current strategy is actually outperforming common practical rules.
