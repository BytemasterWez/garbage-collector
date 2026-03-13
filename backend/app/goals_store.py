from __future__ import annotations

import json
from pathlib import Path


GOALS_FILE_PATH = Path(__file__).with_name("goals.json")


def load_goals() -> list[dict[str, str]]:
    """Read the local goal list for the first Phase 8 engine."""
    with GOALS_FILE_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    goals: list[dict[str, str]] = []
    for goal in payload:
        normalized = {
            "id": str(goal["id"]).strip(),
            "name": str(goal["name"]).strip(),
            "description": str(goal["description"]).strip(),
        }
        if normalized["id"] and normalized["name"] and normalized["description"]:
            goals.append(normalized)

    return goals
