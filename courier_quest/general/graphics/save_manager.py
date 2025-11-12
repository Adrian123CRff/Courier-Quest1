#save_manager.py
from __future__ import annotations

import os
import pickle
import time
from typing import Any, Dict


SAVES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "saves")
DEFAULT_SLOT = os.path.join(SAVES_DIR, "slot1.sav")


class SaveManager:
    def __init__(self, view: Any) -> None:
        self.view = view
        os.makedirs(SAVES_DIR, exist_ok=True)

    def _serialize_state(self) -> Dict[str, Any]:
        v = self.view
        try:
            state = {}
            # copy dictionary-like state if possible
            if isinstance(v.state, dict):
                state.update(v.state)
            else:
                # fallback: pick selected attributes
                for name in ["map_data", "city_map", "orders", "jobs_data", "weather_state", "weather_data", "money", "player_x", "player_y", "elapsed_seconds", "inventory"]:
                    state[name] = getattr(v.state, name, None)

            # ensure player pos and elapsed time
            try:
                state["player_x"] = int(v.player.cell_x)
                state["player_y"] = int(v.player.cell_y)
            except Exception:
                pass
            try:
                if v.game_manager and hasattr(v.game_manager, "get_game_time"):
                    state["elapsed_seconds"] = float(v.game_manager.get_game_time())
            except Exception:
                pass

            # ensure weather snapshot
            try:
                if hasattr(v.weather_markov, "get_state"):
                    state["weather_state"] = dict(v.weather_markov.get_state())
            except Exception:
                pass

            # Guardar estadísticas del jugador
            try:
                if hasattr(v, "player_stats") and v.player_stats:
                    state["player_stats"] = {
                        "stamina": getattr(v.player_stats, "stamina", 100.0),
                        "reputation": getattr(v.player_stats, "reputation", 70),
                        "consecutive_on_time_deliveries": getattr(v.player_stats, "consecutive_on_time_deliveries", 0),
                        "first_late_delivery_of_day": getattr(v.player_stats, "first_late_delivery_of_day", True),
                        "is_resting": getattr(v.player_stats, "is_resting", False),
                        "is_at_rest_point": getattr(v.player_stats, "is_at_rest_point", False),
                        "last_rest_time": getattr(v.player_stats, "last_rest_time", time.time()),
                        "_idle_recover_accum": getattr(v.player_stats, "_idle_recover_accum", 0.0)
                    }
            except Exception as e:
                print(f"[SAVE] Error serializando player_stats: {e}")

            # Guardar score system si existe
            try:
                if hasattr(v, "score_system") and v.score_system:
                    state["score_system"] = {
                        "total_money": getattr(v.score_system, "total_money", 0.0),
                        "deliveries_completed": getattr(v.score_system, "deliveries_completed", 0),
                        "on_time_deliveries": getattr(v.score_system, "on_time_deliveries", 0),
                        "cancellations": getattr(v.score_system, "cancellations", 0),
                        "lost_packages": getattr(v.score_system, "lost_packages", 0),
                        "game_start_time": getattr(v.score_system, "game_start_time", time.time()),
                        "game_duration": getattr(v.score_system, "game_duration", 900)
                    }
            except Exception as e:
                print(f"[SAVE] Error serializando score_system: {e}")

            # Guardar inventario completo
            try:
                if hasattr(v, "inventory") and v.inventory:
                    state["inventory"] = {
                        "items": getattr(v.inventory, "items", []),
                        "current_weight": getattr(v.inventory, "current_weight", 0.0),
                        "max_weight": getattr(v.inventory, "max_weight", 50.0)
                    }
            except Exception as e:
                print(f"[SAVE] Error serializando inventory: {e}")

            # Guardar jobs manager state
            try:
                if hasattr(v, "job_manager") and v.job_manager:
                    state["job_manager"] = {
                        "active_jobs": getattr(v.job_manager, "active_jobs", []),
                        "completed_jobs": getattr(v.job_manager, "completed_jobs", []),
                        "cancelled_jobs": getattr(v.job_manager, "cancelled_jobs", [])
                    }
            except Exception as e:
                print(f"[SAVE] Error serializando job_manager: {e}")

            return state
        except Exception as e:
            print(f"[SAVE] Error serializando estado: {e}")
            return {}

    def _apply_deserialized_state(self, state: Dict[str, Any]) -> None:
        v = self.view
        try:
            if isinstance(v.state, dict):
                v.state.update(state)
            else:
                for k, val in state.items():
                    try:
                        setattr(v.state, k, val)
                    except Exception:
                        pass
            
            # Restaurar estadísticas del jugador
            try:
                if "player_stats" in state and hasattr(v, "player_stats") and v.player_stats:
                    player_stats_data = state["player_stats"]
                    v.player_stats.stamina = player_stats_data.get("stamina", 100.0)
                    v.player_stats.reputation = player_stats_data.get("reputation", 70)
                    v.player_stats.consecutive_on_time_deliveries = player_stats_data.get("consecutive_on_time_deliveries", 0)
                    v.player_stats.first_late_delivery_of_day = player_stats_data.get("first_late_delivery_of_day", True)
                    v.player_stats.is_resting = player_stats_data.get("is_resting", False)
                    v.player_stats.is_at_rest_point = player_stats_data.get("is_at_rest_point", False)
                    v.player_stats.last_rest_time = player_stats_data.get("last_rest_time", time.time())
                    v.player_stats._idle_recover_accum = player_stats_data.get("_idle_recover_accum", 0.0)
                    print(f"[LOAD] Player stats restauradas: stamina={v.player_stats.stamina}, reputation={v.player_stats.reputation}")
            except Exception as e:
                print(f"[SAVE] Error restaurando player_stats: {e}")

            # Restaurar score system
            try:
                if "score_system" in state and hasattr(v, "score_system") and v.score_system:
                    score_data = state["score_system"]
                    v.score_system.total_money = score_data.get("total_money", 0.0)
                    v.score_system.deliveries_completed = score_data.get("deliveries_completed", 0)
                    v.score_system.on_time_deliveries = score_data.get("on_time_deliveries", 0)
                    v.score_system.cancellations = score_data.get("cancellations", 0)
                    v.score_system.lost_packages = score_data.get("lost_packages", 0)
                    v.score_system.game_start_time = score_data.get("game_start_time", time.time())
                    v.score_system.game_duration = score_data.get("game_duration", 900)
                    print(f"[LOAD] Score system restaurado: money={v.score_system.total_money}, deliveries={v.score_system.deliveries_completed}")
            except Exception as e:
                print(f"[SAVE] Error restaurando score_system: {e}")

            # Restaurar inventario
            try:
                if "inventory" in state and hasattr(v, "inventory") and v.inventory:
                    inventory_data = state["inventory"]
                    v.inventory.items = inventory_data.get("items", [])
                    v.inventory.current_weight = inventory_data.get("current_weight", 0.0)
                    v.inventory.max_weight = inventory_data.get("max_weight", 50.0)
                    print(f"[LOAD] Inventario restaurado: {len(v.inventory.items)} items, weight={v.inventory.current_weight}")
            except Exception as e:
                print(f"[SAVE] Error restaurando inventory: {e}")

            # Restaurar job manager
            try:
                if "job_manager" in state and hasattr(v, "job_manager") and v.job_manager:
                    job_data = state["job_manager"]
                    v.job_manager.active_jobs = job_data.get("active_jobs", [])
                    v.job_manager.completed_jobs = job_data.get("completed_jobs", [])
                    v.job_manager.cancelled_jobs = job_data.get("cancelled_jobs", [])
                    print(f"[LOAD] Job manager restaurado: {len(v.job_manager.active_jobs)} active jobs")
            except Exception as e:
                print(f"[SAVE] Error restaurando job_manager: {e}")

            # Restaurar posición del jugador
            try:
                if "player_x" in state and "player_y" in state and hasattr(v, "player"):
                    v.player.cell_x = state["player_x"]
                    v.player.cell_y = state["player_y"]
                    print(f"[LOAD] Posición del jugador restaurada: ({state['player_x']}, {state['player_y']})")
            except Exception as e:
                print(f"[SAVE] Error restaurando posición del jugador: {e}")

            # signal resume for weather/time
            try:
                v.state["__resume_from_save__"] = True
            except Exception:
                pass
        except Exception as e:
            print(f"[SAVE] Error aplicando estado: {e}")

    def save(self, path: str = DEFAULT_SLOT) -> bool:
        try:
            data = self._serialize_state()
            with open(path, "wb") as f:
                pickle.dump(data, f)
            print(f"[SAVE] Guardado en {path}")
            return True
        except Exception as e:
            print(f"[SAVE] Error guardando: {e}")
            return False

    def load(self, path: str = DEFAULT_SLOT) -> bool:
        try:
            if not os.path.exists(path):
                print(f"[SAVE] No existe {path}")
                return False
            with open(path, "rb") as f:
                data = pickle.load(f)
            if not isinstance(data, dict):
                print("[SAVE] Formato inválido")
                return False
            self._apply_deserialized_state(data)
            print(f"[SAVE] Cargado desde {path}")
            return True
        except Exception as e:
            print(f"[SAVE] Error cargando: {e}")
            return False


