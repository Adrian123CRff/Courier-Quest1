# state_initializer.py
import json
from pathlib import Path
from typing import Optional

from models import GameState
from api_client import ApiClient

CACHE_PATH = Path("api_cache") / "city_map.json"

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
    Inicializa y retorna un GameState usando ApiClient (o creando uno).
    - Si force_update=True intentará forzar la obtención de datos frescos desde la API.
    - Si la API no trae 'tiles', usará la cache de api_cache/city_map.json si existe.
    """
    if api is None:
        api = ApiClient()

    state = GameState()

    # ------------- Obtener city_map (con intento de force_update si se pide) -------------
    city_map = {}
    try:
        if force_update:
            # Intentar llamar con parámetro force_update si el cliente lo permite
            try:
                city_map = api.get_city_map(force_update=True)
            except TypeError:
                # la firma no acepta force_update -> llamar normal
                city_map = api.get_city_map()
        else:
            city_map = api.get_city_map()
    except Exception as e:
        print("[INIT] Error al obtener city_map desde API:", e)
        city_map = {}

    # Aplicar fallback a cache si no hay tiles en la respuesta
    city_map = _fallback_tiles_from_cache(city_map)

    # ------------- Obtener jobs y weather (con try/except) -------------
    try:
        # intentar force en jobs si está disponible
        if force_update and hasattr(api, "get_jobs"):
            try:
                jobs = api.get_jobs(force_update=True)
            except TypeError:
                jobs = api.get_jobs()
        else:
            jobs = api.get_jobs()
    except Exception as e:
        print("[INIT] Error al obtener jobs:", e)
        jobs = []

    try:
        if force_update and hasattr(api, "get_weather"):
            try:
                weather = api.get_weather(force_update=True)
            except TypeError:
                weather = api.get_weather()
        else:
            weather = api.get_weather()
    except Exception as e:
        print("[INIT] Error al obtener weather:", e)
        weather = {}

    # ------------- Rellenar el estado -------------
    # guardar el dict del mapa en el estado para que GameMap lo consuma
    state.city_map = city_map or {}

    # pedidos / orders
    state.orders = jobs or []

    # clima
    state.weather_state = weather or {}

    # jugador básico
    state.player = {
        "name": "Courier",
        "hp": 100,
        "stamina": 100,
        "money": 0,
    }

    # reputación inicial (puedes adaptar)
    state.reputation = 70

    # debug summary
    try:
        cm_keys = list(state.city_map.keys()) if isinstance(state.city_map, dict) else []
        print(f"[INIT] state.city_map keys: {cm_keys}")
    except Exception:
        pass

    return state
