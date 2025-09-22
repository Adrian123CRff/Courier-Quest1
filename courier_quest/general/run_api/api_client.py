import requests
import time
from pathlib import Path
import json
from typing import Optional, Any, Dict, Union

class ApiClient:
    def __init__(
            self,
            base_url: str = "https://tigerds-api.kindflower-ccaf48b6.eastus.azurecontainerapps.io",
            cache_dir: str = "api_cache",
            data_dir: str = "data",
            ttl: int = 60
    ):
        self.base_url = base_url
        self.cache_dir = Path(cache_dir)
        self.data_dir = Path(data_dir)
        self.ttl = ttl

        self.cache_dir.mkdir(exist_ok=True, parents=True)
        self.data_dir.mkdir(exist_ok=True, parents=True)

        # Mapeo de endpoints a archivos locales
        self.endpoint_to_local = {
            "city/map": "ciudad.json",
            "city/jobs": "pedidos.json",
            "city/weather": "weather.json"
        }

    # -------------------------------
    # Funciones internas de soporte
    # -------------------------------

    def _cache_path(self, endpoint: str, params: Optional[dict] = None) -> Path:
        cache_name=endpoint.replace("/","_")
        if params:
            param_str="_".join([f"{k}_{v}" for k, v in sorted(params.items())])
            cache_name=f"{cache_name}_{param_str}"
        return self.cache_dir / f"{cache_name}.json"

    def _load_json_file(self, path: Path) -> Optional[Union[dict, list]]:
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return None

    def _save_json_file(self, path: Path, data: Any):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _is_cache_valid(self, path: Path) -> bool:
        """Determina si el cache es válido según TTL."""
        if not path.exists():
            return False
        age = time.time() - path.stat().st_mtime
        return age <= self.ttl

    # -------------------------------
    # Fetch principal
    # -------------------------------

    def fetch_data(self, endpoint: str, params: dict = None) -> Optional[Union[dict, list]]:
        """
        Intenta obtener datos del API, si falla usa cache válido,
        y si tampoco hay cache, usa fallback local en /data.
        """
        cache_file = self._cache_path(endpoint, params)
        local_file = self.data_dir / self.endpoint_to_local.get(endpoint, "")

        # 1. Intentar API
        url = f"{self.base_url}/{endpoint}"
        try:
            resp = requests.get(url, params=params, timeout=5)
            resp.raise_for_status()
            data = resp.json()

            # Normalizar: si viene {"data": {...}}, usar el contenido
            if isinstance(data, dict) and "data" in data:
                data = data["data"]

            # Guardar en cache
            self._save_json_file(cache_file, data)
            print(f"[API] {endpoint} OK → datos guardados en cache")
            return data

        except requests.exceptions.RequestException:
            print(f"[WARN] No se pudo conectar a {endpoint}, usando respaldo")

        # 2. Intentar cache válido
        if self._is_cache_valid(cache_file):
            data = self._load_json_file(cache_file)
            if data is not None:
                print(f"[CACHE] {endpoint} cargado desde cache válido")
                return data

        # 3. Intentar local
        if local_file.exists():
            data = self._load_json_file(local_file)
            if data is not None:
                print(f"[LOCAL] {endpoint} cargado desde /data")
                return data

        # 4. Nada disponible
        print(f"[ERROR] No hay datos disponibles para {endpoint}")
        return None

        # -------------------------------
        # Wrappers específicos
        # -------------------------------

    def get_city_map(self) -> Dict[str, Any]:
        data = self.fetch_data("city/map") or {}
        return {
            "name": data.get("name", "TigerCity"),
            "width": data.get("width", 30),
            "height": data.get("height", 30),
            "buildings": data.get("buildings", []),
            "roads": data.get("roads", []),
        }

    def get_jobs(self) -> list:
        data = self.fetch_data("city/jobs") or []
        if isinstance(data, dict) and "jobs" in data:
            return data["jobs"]
        if isinstance(data, list):
            return data
        return []

    def get_weather(self) -> Dict[str, Any]:
        data = self.fetch_data("city/weather", params={"city": "TigerCity"}) or {}
        initial = data.get("initial", {})
        condition = initial.get("condition", "unknown")

        translations = {
            "clear": "Despejado",
            "clouds": "Nublado",
            "rain_light": "Lluvia ligera",
            "rain": "Lluvia",
            "storm": "Tormenta",
            "fog": "Niebla",
            "wind": "Viento",
            "heat": "Calor",
            "cold": "Frío",
            "unknown": "Desconocido",
        }

        summary = translations.get(condition, condition)
        temp_defaults = {
            "clear": 25, "clouds": 20, "rain_light": 18, "rain": 16,
            "storm": 15, "fog": 12, "wind": 22, "heat": 30, "cold": 10
        }
        temperature = temp_defaults.get(condition, 20)

        return {
            "condition": condition,
            "summary": summary,
            "temperature": temperature,
        }



