# scoreboard.py
from __future__ import annotations

import json
import os
from typing import Any, List, Dict


SCORES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "puntajes.json")


class Scoreboard:
    def __init__(self) -> None:
        os.makedirs(os.path.dirname(SCORES_PATH), exist_ok=True)

    def load_scores(self) -> List[Dict[str, Any]]:
        try:
            if os.path.exists(SCORES_PATH):
                with open(SCORES_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
        except Exception:
            pass
        return []

    def save_scores(self, scores: List[Dict[str, Any]]) -> None:
        try:
            with open(SCORES_PATH, "w", encoding="utf-8") as f:
                json.dump(scores, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SCOREBOARD] Error guardando puntajes: {e}")

    def add_score(self, entry: Dict[str, Any]) -> None:
        scores = self.load_scores()
        scores.append(entry)
        # ordenar de mayor a menor por 'score'
        try:
            scores.sort(key=lambda s: float(s.get("score", 0.0)), reverse=True)
        except Exception:
            pass
        self.save_scores(scores)


