# Undo manager for game state
from __future__ import annotations

import copy
from typing import Any, List, Dict


class UndoManager:
    def __init__(self, view: Any, max_depth: int = 50) -> None:
        self.view = view
        self.max_depth = max_depth
        self._stack: List[Dict[str, Any]] = []

    def snapshot(self) -> None:
        v = self.view
        snap: Dict[str, Any] = {}
        try:
            if isinstance(v.state, dict):
                snap["state"] = copy.deepcopy(v.state)
            else:
                # minimal snapshot for non-dict states
                minimal = {}
                for name in ["map_data", "city_map", "orders", "jobs_data", "weather_state", "money", "player_x", "player_y", "elapsed_seconds", "inventory"]:
                    minimal[name] = copy.deepcopy(getattr(v.state, name, None))
                snap["state_min"] = minimal
            # player pos
            try:
                snap["player_pos"] = (int(v.player.cell_x), int(v.player.cell_y))
            except Exception:
                pass
        except Exception:
            return
        self._stack.append(snap)
        if len(self._stack) > self.max_depth:
            self._stack.pop(0)

    def restore(self) -> bool:
        if not self._stack:
            return False
        v = self.view
        snap = self._stack.pop()
        try:
            if "state" in snap and isinstance(v.state, dict):
                v.state.clear()
                v.state.update(snap["state"])
            elif "state_min" in snap:
                for k, val in snap["state_min"].items():
                    try:
                        setattr(v.state, k, val)
                    except Exception:
                        pass
            if "player_pos" in snap:
                x, y = snap["player_pos"]
                try:
                    v.player.cell_x = int(x)
                    v.player.cell_y = int(y)
                    v.player.pixel_x, v.player.pixel_y = v.player.cell_to_pixel(v.player.cell_x, v.player.cell_y)
                    v.player.target_pixel_x, v.player.target_pixel_y = v.player.pixel_x, v.player.pixel_y
                    v.player.moving = False
                    try:
                        v.player.sprite.center_x = v.player.pixel_x
                        v.player.sprite.center_y = v.player.pixel_y
                    except Exception:
                        pass
                except Exception:
                    pass
            return True
        except Exception:
            return False


