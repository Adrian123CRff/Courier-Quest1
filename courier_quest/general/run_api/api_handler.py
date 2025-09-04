import requests
import json
from pathlib import Path
from typing import Optional


class APIHandler:
    def __init__(self, base_url: str = "https://tigerds-api.kindflower-ccaf48b6.eastus.azurecontainerapps.io",
                 cache_dir: str = "../api_cache", data_dir: str = "../data"):
        self.base_url = base_url
        self.cache_dir = Path(cache_dir)
        self.data_dir = Path(data_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)
        self.last_source = None

        self.endpoint_to_local = {
            "city/map": "ciudad.json",
            "city/jobs": "pedidos.json",
            "city/weather": "weather.json"
        }

    def fetch_data(self, endpoint: str, force_update: bool = False) -> Optional[dict]:
        cache_file = self.cache_dir / f"{endpoint.replace('/', '_')}.json"
        local_file = self.data_dir / self.endpoint_to_local.get(endpoint, "")

        if not force_update and cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                self.last_source = "cache"
                return json.load(f)

        try:
            response = requests.get(f"{self.base_url}/{endpoint}", timeout=10)
            response.raise_for_status()
            data = response.json()
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            self.last_source = "api"
            return data
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {endpoint}: {e}")
            if cache_file.exists():
                print("Falling back to cached data.")
                with open(cache_file, 'r', encoding='utf-8') as f:
                    self.last_source = "cache"
                    return json.load(f)
            elif local_file.exists():
                print("Falling back to local data file.")
                with open(local_file, 'r', encoding='utf-8') as f:
                    self.last_source = "local"
                    return json.load(f)
            else:
                print(f"No cached or local data available for {endpoint}.")
                self.last_source = None
                return None

    def get_city_map(self) -> Optional[dict]:
        return self.fetch_data("city/map")

    def get_jobs(self) -> Optional[dict]:
        return self.fetch_data("city/jobs")

    def get_weather(self) -> Optional[dict]:
        return self.fetch_data("city/weather")