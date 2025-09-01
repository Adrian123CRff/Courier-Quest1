import requests
import json
from pathlib import Path
from typing import Optional


class APIManager:
    def __init__(self, base_url: str, cache_dir: str = "./api_cache", data_dir: str = "./data"):
        self.base_url = base_url
        self.cache_dir = Path(cache_dir)
        self.data_dir = Path(data_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)

        # Mapeo de endpoints a archivos locales
        self.endpoint_to_local = {
            "city/map": "ciudad.json",
            "city/jobs": "pedidos.json",
            "city/weather": "weather.json"
        }

    def fetch_data(self, endpoint: str, force_update: bool = False) -> Optional[dict]:
        cache_file = self.cache_dir / f"{endpoint.replace('/', '_')}.json"
        local_file = self.data_dir / self.endpoint_to_local.get(endpoint, "")

        # Cargar de cache si existe y no se fuerza actualización
        if not force_update and cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        try:
            response = requests.get(f"{self.base_url}/{endpoint}", timeout=10)
            response.raise_for_status()
            data = response.json()
            # Guardar en cache
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            return data
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {endpoint}: {e}")
            # Intentar cargar desde cache si existe
            if cache_file.exists():
                print("Falling back to cached data.")
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            # Si no hay cache, intentar cargar desde archivo local
            elif local_file.exists():
                print("Falling back to local data file.")
                with open(local_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                print(f"No cached or local data available for {endpoint}.")
                return None

    def load_local_data(self, endpoint: str) -> Optional[dict]:
        """Carga datos directamente desde los archivos locales sin intentar el API."""
        filename = self.endpoint_to_local.get(endpoint)
        if not filename:
            print(f"No local file mapping for endpoint: {endpoint}")
            return None
        local_file = self.data_dir / filename
        if local_file.exists():
            try:
                with open(local_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading local data from {local_file}: {e}")
                return None
        else:
            print(f"Local file {local_file} not found.")
            return None
        

