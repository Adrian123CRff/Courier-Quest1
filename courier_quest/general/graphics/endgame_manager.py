#engame_manager.py
from __future__ import annotations

from typing import Any, Optional
import datetime

from .scoreboard import Scoreboard


class EndgameManager:
    def __init__(self, view: Any) -> None:
        self.view = view
        self._scoreboard = Scoreboard()

    def _compute_goal(self) -> float:
        v = self.view
        if isinstance(v.state, dict):
            _m = v.state.get("map_data") or v.state.get("city_map") or {}
        else:
            _m = getattr(v.state, "map_data", None) or getattr(v.state, "city_map", {})
        try:
            return float((_m or {}).get("goal", 3000))
        except Exception:
            return 3000.0

    def _compute_total_duration(self) -> Optional[float]:
        v = self.view
        gm = v.game_manager
        if not gm:
            return None
        # Prefer declared duration, else infer from elapsed + remaining
        for attr in ("max_duration", "duration"):
            if hasattr(gm, attr):
                try:
                    return float(getattr(gm, attr))
                except Exception:
                    pass
        try:
            elapsed = float(gm.get_game_time())
            remaining = float(gm.get_time_remaining())
            return elapsed + remaining
        except Exception:
            return None

    def _compute_score(self, finished: str, time_remaining: float) -> float:
        v = self.view
        money = v._get_state_money()
        rep = getattr(v.player_stats, "reputation", 70)
        pay_mult = 1.05 if rep >= 90 else 1.0
        score_base = money * pay_mult

        # Bonus tiempo si victoria y queda >=20% del tiempo total
        bonus = 0.0
        total = self._compute_total_duration() or 0.0
        try:
            if finished == "win" and total > 0 and time_remaining >= 0.2 * total:
                bonus = 0.1 * score_base
        except Exception:
            pass

        # Penalizaciones (placeholder mínima)
        penalty = 0.0

        return max(0.0, score_base + bonus - penalty)

    def _record_score(self, finished: str, time_remaining: float) -> None:
        v = self.view
        entry = {
            "score": self._compute_score(finished, time_remaining),
            "finished": finished,
            "money": v._get_state_money(),
            "reputation": getattr(v.player_stats, "reputation", 70),
            "time_remaining": float(time_remaining),
            "date": datetime.datetime.utcnow().isoformat() + "Z",
        }
        self._scoreboard.add_score(entry)

    def check_and_maybe_end(self) -> None:
        v = self.view
        if getattr(v, "_game_over", False):
            return
        gm = v.game_manager
        if not gm:
            return
        try:
            time_remaining = float(gm.get_time_remaining())
        except Exception:
            time_remaining = 0.0

        money = v._get_state_money()
        goal = self._compute_goal()
        rep = getattr(v.player_stats, "reputation", 70)

        finished: Optional[str] = None
        if money >= goal and time_remaining > 0:
            finished = "win"
        elif rep < 20:
            finished = "lose"
        elif time_remaining <= 0 and money < goal:
            finished = "lose"

        if finished:
            try:
                self._record_score(finished, time_remaining)
            except Exception:
                pass

            try:
                v._game_over = True
            except Exception:
                pass

            # Notificación simple; transición de vista opcional a implementar en UI
            if finished == "win":
                v.show_notification("🏆 ¡Victoria! Meta alcanzada. Puntaje guardado.")
            else:
                v.show_notification("❌ Fin del juego. Puntaje guardado.")


