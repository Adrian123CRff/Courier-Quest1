#save_manager.py
import os
import json
import pickle
import time
from pathlib import Path
from typing import Optional, Any, Dict
from dataclasses import is_dataclass, asdict



BASE_DIR = Path(__file__).resolve().parent
SAVE_DIR = BASE_DIR / "saves"
DEBUG_DIR = SAVE_DIR / "debug"
SAVE_DIR.mkdir(exist_ok=True, parents=True)
DEBUG_DIR.mkdir(exist_ok=True, parents=True)



def save_game(state: Any, slot_name: str = "slot1.sav") -> str:
    """Guarda un GameState en formato binario (.sav) y en JSON para debug."""
    path = SAVE_DIR / slot_name

    # Normalizar el estado a dict
    if isinstance(state, dict):
        state_dict: Dict[str, Any] = state
    elif hasattr(state, "to_dict") and callable(getattr(state, "to_dict")):
        state_dict = state.to_dict()
    elif is_dataclass(state):
        state_dict = asdict(state)
    else:
        raise TypeError(
            f"save_game() espera un dict, un objeto con to_dict() o una dataclass; recibido {type(state)._name_}"
        )

    payload = {
        "meta": {
            "format": "courierquest-save",
            "version": "1.0",
            "timestamp": time.time(),
        },
        "state": state.to_dict()
    }

    # Guardar binario
    with open(path, "wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)

    # Guardar JSON legible en carpeta debug
    debug_path = DEBUG_DIR / f"{slot_name}.json"
    with open(debug_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"[SAVE] Partida guardada en {path}")
    return str(path)

def load_game(slot_name: str = "slot1.sav") -> Optional[Dict[str, Any]]:
    """Carga un GameState desde un archivo .sav binario."""
    path = SAVE_DIR / slot_name
    if not path.exists():
        print(f"[LOAD] No existe el archivo {slot_name}")
        return None

    try:
        with open(path, "rb") as f:
            payload = pickle.load(f)
        state_dict = payload.get("state", {})
        if not isinstance(state_dict, dict):
            raise ValueError("El contenido de 'state' no es un dict válido")
        return state_dict
    except Exception as e:
        print(f"[ERROR] Falló la carga de {slot_name}: {e}")
        return None


def list_saves() -> list[str]:
    """Lista los archivos de guardado disponibles ordenados por fecha."""
    saves = [f for f in SAVE_DIR.iterdir() if f.suffix == ".sav"]
    saves.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.name for p in saves]