from __future__ import annotations

import json
from pathlib import Path

from yahtzee.models import GameState


def save_game(state: GameState, path: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")


def load_game(path: str) -> GameState:
    p = Path(path)
    payload = json.loads(p.read_text(encoding="utf-8"))
    return GameState.from_dict(payload)
