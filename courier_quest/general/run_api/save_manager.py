import json
import pickle
import time
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import is_dataclass, asdict

BASE_DIR = Path(__file__).resolve().parent
SAVE_DIR = BASE_DIR / "saves"
DEBUG_DIR = SAVE_DIR / "debug"
SAVE_DIR.mkdir(parents=True, exist_ok=True)
DEBUG_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_state(state: Any) -> Dict[str, Any]:
    if isinstance(state, dict):
        return dict(state)
    if hasattr(state, "to_dict") and callable(state.to_dict):
        return state.to_dict()
    if is_dataclass(state):
        return asdict(state)
    
    # Si es un objeto con atributos, intentar extraer los datos importantes
    if hasattr(state, "__dict__"):
        result = {}
        # Extraer atributos básicos
        for attr in ["map_data", "city_map", "jobs_data", "orders", "weather_data", "weather_state", 
                     "money", "player_x", "player_y", "elapsed_seconds", "current_time", "game_duration"]:
            if hasattr(state, attr):
                result[attr] = getattr(state, attr)
        
        # Extraer player_stats si existe
        if hasattr(state, "player_stats") and state.player_stats:
            result["player_stats"] = {
                "stamina": getattr(state.player_stats, "stamina", 100.0),
                "reputation": getattr(state.player_stats, "reputation", 70),
                "consecutive_on_time_deliveries": getattr(state.player_stats, "consecutive_on_time_deliveries", 0),
                "first_late_delivery_of_day": getattr(state.player_stats, "first_late_delivery_of_day", True),
                "is_resting": getattr(state.player_stats, "is_resting", False),
                "is_at_rest_point": getattr(state.player_stats, "is_at_rest_point", False),
                "last_rest_time": getattr(state.player_stats, "last_rest_time", time.time()),
                "_idle_recover_accum": getattr(state.player_stats, "_idle_recover_accum", 0.0)
            }
        
        # Extraer score_system si existe
        if hasattr(state, "score_system") and state.score_system:
            result["score_system"] = {
                "total_money": getattr(state.score_system, "total_money", 0.0),
                "deliveries_completed": getattr(state.score_system, "deliveries_completed", 0),
                "on_time_deliveries": getattr(state.score_system, "on_time_deliveries", 0),
                "cancellations": getattr(state.score_system, "cancellations", 0),
                "lost_packages": getattr(state.score_system, "lost_packages", 0),
                "game_start_time": getattr(state.score_system, "game_start_time", time.time()),
                "game_duration": getattr(state.score_system, "game_duration", 900)
            }
        
        # Extraer inventory si existe
        if hasattr(state, "inventory") and state.inventory:
            result["inventory"] = {
                "items": getattr(state.inventory, "items", []),
                "current_weight": getattr(state.inventory, "current_weight", 0.0),
                "max_weight": getattr(state.inventory, "max_weight", 50.0)
            }
        
        return result
    
    raise TypeError(
        f"save_game() espera dict, dataclass o objeto con to_dict(); recibido {type(state).__name__}"
    )


def save_game(state: Any, slot_name: str = "slot1.sav") -> str:
    """Guarda el estado en binario (.sav) y un JSON de debug legible."""
    path = SAVE_DIR / slot_name
    state_dict = _normalize_state(state)

    payload = {
        "meta": {
            "format": "courierquest-save",
            "version": "1.0",
            "timestamp": time.time(),
        },
        "state": state_dict,  # <-- guardamos el dict tal cual (snapshot)
    }

    with open(path, "wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)

    # JSON de apoyo (opcional)
    debug_path = DEBUG_DIR / f"{slot_name}.json"
    with open(debug_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"[SAVE] Partida guardada en {path}")
    return str(path)


def load_game(slot_name: str = "slot1.sav") -> Optional[Dict[str, Any]]:
    """Carga el .sav y devuelve el dict del estado."""
    path = SAVE_DIR / slot_name
    if not path.exists():
        print(f"[LOAD] No existe {slot_name}")
        return None

    try:
        with open(path, "rb") as f:
            payload = pickle.load(f)
        state = payload.get("state", {})
        if not isinstance(state, dict):
            raise ValueError("Campo 'state' no es un dict")
        return state
    except Exception as e:
        print(f"[ERROR] Falló la carga de {slot_name}: {e}")
        return None


def list_saves() -> list[str]:
    saves = [p.name for p in SAVE_DIR.glob("*.sav")]
    saves.sort(key=lambda n: int(n.replace("slot", "").replace(".sav", "")) if n.startswith("slot") else 9999)
    return saves
