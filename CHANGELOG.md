# Changelog

## 2026-04-09
- Refactored the main Streamlit app analysis flow so initial page render no longer auto-runs turn recommendations for placeholder `[1, 1, 1, 1, 1]` dice.
- Added turn-analysis fingerprints + session-state invalidation to reuse recommendations across reruns and only refresh when dice, roll, scorecard, or objective actually changes.
- Added an app-level cached recommendation service and lazy exact-outcome breakdown computation for the selected best hold only.
- Updated objective UX labels/help to clarify that exact turn EV is slower and now marks recommendations stale until users explicitly refresh.
- Refactored advisor recommendation generation to avoid computing exact outcome probabilities for every hold candidate by default.
- Added tests covering fingerprint invalidation, analysis state reset/stale behavior, and advisor lazy probability computation path.

- Fixed a Streamlit startup import crash on `pages/Benchmark_Analysis.py` by removing eager benchmark package re-exports and stabilizing module initialization order.
- Hardened the `benchmark` package by converting intra-package imports to explicit relative imports to avoid partial initialization and circular import fragility.
- Replaced eager `benchmark.__init__` exports with a minimal package marker to remove implicit import-order coupling.
- Added benchmark import smoke tests covering `benchmark.run`, `benchmark.page_helpers`, key exported run symbols, and the benchmark page import path.

- Overhauled Strategy Test Lab into a browser-safe decision tool with explicit run modes (Quick Winner, Balanced Benchmark, Deep Dive, Advanced Custom), clearer methodology, and pre-run strategy/stage summaries.
- Added benchmark planning + execution separation (`plan_benchmark_run` and `execute_benchmark_plan`) with workload estimates, browser caps, auto-downgrade metadata, and partial-result-safe stage toggles.
- Removed `exact_turn_ev` from browser-safe default runs; it is now advanced/opt-in only and gated behind Advanced Custom selection.
- Improved progress reliability with stage-aware incremental updates for full-game simulation, sampled-state collection, and reference move-quality checks.
- Expanded benchmark tests to cover strategy safety defaults, plan downgrade behavior, progress callback coverage, runtime smoke execution, and page helper/display mapping stability.
