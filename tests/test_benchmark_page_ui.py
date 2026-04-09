import importlib

from benchmark.page_helpers import STRATEGY_METADATA, strategy_summary_rows


def test_page_imports_successfully():
    importlib.import_module("pages.Benchmark_Analysis")


def test_strategy_mapping_complete_and_user_facing():
    expected = {"board_utility", "exact_turn_ev", "human_heuristic", "rollout_oracle"}
    assert expected.issubset(set(STRATEGY_METADATA.keys()))
    rows = strategy_summary_rows(["board_utility", "human_heuristic"])
    assert rows[0]["Strategy"] != "board_utility"
