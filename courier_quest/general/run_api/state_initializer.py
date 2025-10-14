# state_initializer.py - CORREGIDO
import json
from pathlib import Path
from typing import Optional
from datetime import datetime  # ✅ AÑADIR IMPORT

from .models import GameState
from .api_client import ApiClient

BASE_DIR = Path(__file__).resolve().parent
CACHE_PATH = BASE_DIR / "api_cache" / "city_map.json"

def _fallback_tiles_from_cache(city_map: dict) -> dict:
    """
    Si city_map no contiene 'tiles', intenta leer api_cache/city_map.json
    y devolver una versión con 'tiles' si existe.
    """
    # Si ya trae tiles, devolver tal cual
    if city_map and isinstance(city_map, dict) and city_map.get("tiles"):
        return city_map

    # Intentar leer cache
    try:
        if CACHE_PATH.exists():
            with CACHE_PATH.open(encoding="utf-8") as f:
                cached = json.load(f)
            if isinstance(cached, dict) and cached.get("tiles"):
                print(f"[FALLBACK] API no trae 'tiles' -> usando 'tiles' desde cache: {CACHE_PATH}")
                # Merge sensible: preferir keys del cached, pero mantener campos principales de city_map si vienen
                merged = dict(cached)
                if isinstance(city_map, dict):
                    # Sobre-escribir con city_map valores 'name','width','height' si el API los prové
                    if city_map.get("name"):
                        merged["name"] = city_map.get("name")
                    if city_map.get("city_name"):
                        merged["city_name"] = city_map.get("city_name")
                    if city_map.get("width"):
                        merged["width"] = city_map.get("width")
                    if city_map.get("height"):
                        merged["height"] = city_map.get("height")
                    # conservar otras keys existentes en city_map (no borrar cached)
                    for k, v in city_map.items():
                        if k not in merged:
                            merged[k] = v
                return merged
    except Exception as e:
        print("[FALLBACK] Error leyendo cache:", e)

    return city_map or {}

def init_game_state(api: Optional[ApiClient] = None, force_update: bool = False) -> GameState:
    """
    Inicializa GameState usando EXCLUSIVAMENTE datos del API
    """
    if api is None:
        api = ApiClient()

    state = GameState()

    try:
        # Obtener datos DINÁMICOS del API
        city_map = api.get_city_map()
        jobs = api.get_jobs()
        weather = api.get_weather()

        # Si el mapa no tiene tiles, intentar fallback con cache
        if not city_map.get("tiles"):
            city_map = _fallback_tiles_from_cache(city_map)

        # Validar datos críticos
        if not city_map.get("start_time"):
            print("❌ ERROR: El mapa no tiene start_time")
            # Podemos generar uno basado en tiempo actual si es necesario
            city_map["start_time"] = datetime.now().isoformat() + "Z"

        if not city_map.get("max_time"):
            print("❌ ERROR: El mapa no tiene max_time")
            city_map["max_time"] = 900  # Valor por defecto genérico

        # Rellenar el estado con datos DINÁMICOS
        state.city_map = city_map
        state.orders = jobs or []
        state.weather_state = weather or {}

        # Configurar jugador con datos dinámicos
        state.player = {
            "name": "Courier",
            "stamina": 100,
            "money": 0,
        }

        state.reputation = 70

        print(f"[INIT] Estado inicializado con datos del API:")
        print(f"  - Ciudad: {city_map.get('name')}")
        print(f"  - Meta: ${city_map.get('goal')}")
        print(f"  - Duración: {city_map.get('max_time')}s")
        print(f"  - Trabajos: {len(state.orders)}")

    except Exception as e:
        print(f"❌ ERROR CRÍTICO inicializando estado: {e}")
        # En caso de error total, usar valores genéricos
        state = _create_minimal_state()

    return state

def _create_minimal_state() -> GameState:
    """Crea estado mínimo genérico en caso de fallo total"""
    return GameState(
        player={"name": "Courier", "stamina": 100, "money": 0},
        city_map={
            "name": "FallbackCity",
            "width": 20,
            "height": 15,
            "goal": 1000,
            "start_time": datetime.now().isoformat() + "Z",
            "max_time": 900
        },
        orders=[],
        weather_state={},
        reputation=70
    )
