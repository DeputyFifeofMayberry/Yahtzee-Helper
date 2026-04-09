import ast
import importlib
from pathlib import Path


def test_import_benchmark_run_module_smoke():
    run_module = importlib.import_module("benchmark.run")
    assert run_module is not None


def test_import_benchmark_page_helpers_module_smoke():
    page_helpers_module = importlib.import_module("benchmark.page_helpers")
    assert page_helpers_module is not None


def test_benchmark_run_exposes_expected_symbols():
    run_module = importlib.import_module("benchmark.run")
    assert hasattr(run_module, "BenchmarkSettings")
    assert hasattr(run_module, "estimate_run_cost")


def test_benchmark_analysis_page_import_chain_references_benchmark_modules():
    # We avoid importing the Streamlit page module directly in pytest because top-level
    # UI execution depends on a Streamlit ScriptRunContext. This AST-level assertion
    # still protects the benchmark import chain used by the page.
    page_source = Path("pages/Benchmark_Analysis.py").read_text(encoding="utf-8")
    tree = ast.parse(page_source)

    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    assert "benchmark.page_helpers" in imported_modules
    assert "benchmark.run" in imported_modules
