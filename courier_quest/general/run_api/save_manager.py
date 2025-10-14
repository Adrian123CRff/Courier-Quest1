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
        for key, value in state.__dict__.items():
            # Incluir atributos no privados y no callable, pero también algunos privados importantes
            if not callable(value) and (not key.startswith('_') or key in ['_idle_recover_accum']):
                if key == 'deque' and hasattr(value, '__iter__'):
                    result[key] = list(value)
                elif key == 'inventory' and hasattr(value, 'to_dict'):
                    result[key] = value.to_dict()
                elif key == 'player' and hasattr(value, 'to_dict'):
                    result[key] = value.to_dict()
                else:
                    result[key] = value
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
