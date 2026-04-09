# Changelog

## 2026-04-09
- Fixed a Streamlit startup import crash on `pages/Benchmark_Analysis.py` by removing eager benchmark package re-exports and stabilizing module initialization order.
- Hardened the `benchmark` package by converting intra-package imports to explicit relative imports to avoid partial initialization and circular import fragility.
- Replaced eager `benchmark.__init__` exports with a minimal package marker to remove implicit import-order coupling.
- Added benchmark import smoke tests covering `benchmark.run`, `benchmark.page_helpers`, key exported run symbols, and the benchmark page import path.

- Overhauled Strategy Test Lab into a browser-safe decision tool with explicit run modes (Quick Winner, Balanced Benchmark, Deep Dive, Advanced Custom), clearer methodology, and pre-run strategy/stage summaries.
- Added benchmark planning + execution separation (`plan_benchmark_run` and `execute_benchmark_plan`) with workload estimates, browser caps, auto-downgrade metadata, and partial-result-safe stage toggles.
- Removed `exact_turn_ev` from browser-safe default runs; it is now advanced/opt-in only and gated behind Advanced Custom selection.
- Improved progress reliability with stage-aware incremental updates for full-game simulation, sampled-state collection, and reference move-quality checks.
- Expanded benchmark tests to cover strategy safety defaults, plan downgrade behavior, progress callback coverage, runtime smoke execution, and page helper/display mapping stability.
