# Changelog

## 2026-04-09
- Fixed a Streamlit startup import crash on `pages/Benchmark_Analysis.py` by removing eager benchmark package re-exports and stabilizing module initialization order.
- Hardened the `benchmark` package by converting intra-package imports to explicit relative imports to avoid partial initialization and circular import fragility.
- Replaced eager `benchmark.__init__` exports with a minimal package marker to remove implicit import-order coupling.
- Added benchmark import smoke tests covering `benchmark.run`, `benchmark.page_helpers`, key exported run symbols, and the benchmark page import path.

