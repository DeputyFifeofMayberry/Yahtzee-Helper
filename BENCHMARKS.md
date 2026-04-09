# Benchmark Analysis (Yahtzee-Helper)

This project ships a **Benchmark Analysis** system for strategy comparison. It is designed for fairer, reproducible comparisons and auditable outputs.

## What it compares

1. **Full-game score comparison** (paired)
   - Uses **common random numbers**: every strategy is run on the same per-game seed list.
   - Outputs keep `game_id` and `shared_seed_id` so pairwise deltas are auditable.
2. **Move-quality vs rollout reference**
   - Uses sampled decision snapshots.
   - Default corpus mode is `neutral_canonical` (strategy-neutral generation path).
   - Compares each strategy action to a Monte Carlo **rollout reference** (not ground truth).

## Canonical modes

- `quick`
- `balanced` (default)
- `deep`
- `advanced_custom`

Backward-compatible aliases:
- `fast` -> `quick`
- `standard` -> `balanced`
- `custom` -> `advanced_custom`

## Reference terminology (honest naming)

Use these terms in UI/CLI/docs/outputs:
- `rollout_reference`
- `reference agreement rate`
- `estimated regret vs reference`

The rollout reference is an approximate Monte Carlo evaluator. It is not an exact oracle.

## Reproducibility

- Full-game stage: deterministic shared seed bank from `seed`.
- Move-quality stage: deterministic snapshot sampling from fixed RNG seeded by `seed`.
- Rollout reference seed derivation from game state uses stable canonical JSON + SHA-256.
- No Python `hash()` is used for benchmark determinism.

## CLI examples

Balanced run:

```bash
python scripts/run_benchmarks.py --mode balanced
```

Deep run with explicit move-quality stage:

```bash
python scripts/run_benchmarks.py --mode deep --include-move-quality
```

Advanced custom run:

```bash
python scripts/run_benchmarks.py --mode advanced_custom --full-games 120 --state-sample-games 20 --state-sample-size 80 --rollout-reference-rollouts 24 --corpus-mode neutral_canonical
```

## Output files

- `full_game_results.csv`
- `rollout_reference_comparisons.csv`
- `full_game_summary.json`
- `rollout_reference_summary.json`
- `run_manifest.json`
- `run_result.json`

### Audit fields in rollout rows

Each row includes: snapshot id, provenance, dice, roll number, turn index, score signature, policy action, reference action, match flag, estimated policy/reference values, estimated regret, rollout count, and tags.

## Browser-safe behavior

Non-advanced modes apply browser-safe caps. If caps are applied:
- the run records auto-adjustments
- `run_manifest.json` records requested vs effective settings
- UI displays explicit downgrade notices

## Serious-comparison guidance

For more stable comparison:
- use `balanced` or `deep`
- keep `corpus_mode=neutral_canonical`
- use enough full games and sampled states
- interpret move-quality metrics with caution text and sample counts
