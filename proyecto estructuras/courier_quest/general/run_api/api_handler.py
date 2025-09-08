
import requests
from pathlib import Path
import json
from typing import Optional



class APIHandler:
    def __init__(self, base_url: str = "https://tigerds-api.kindflower-ccaf48b6.eastus.azurecontainerapps.io",
                 cache_dir: str = "api_cache", data_dir: str = "data"):
        self.base_url = base_url
        self.cache_dir = Path(cache_dir)
        self.data_dir = Path(data_dir)
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        self.data_dir.mkdir(exist_ok=True, parents=True)
        self.last_source = None
        self.api_available = self.check_api_availability()

        # Mapeo de endpoints a archivos locales
        self.endpoint_to_local = {
            "city/map": "ciudad.json",
            "city/jobs": "pedidos.json",
            "city/weather": "weather.json"
        }

    def check_api_availability(self) -> bool:
        """Verifica si la API está disponible"""
        try:
            response = requests.get(f"{self.base_url}/city/map", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            print("API no disponible. Usando datos locales/caché.")
            return False

    def fetch_data(self, endpoint: str, params: dict = None, force_update: bool = False) -> Optional[dict]:
        # Limpiar el nombre del endpoint para el archivo de caché
        cache_name = endpoint.replace('/', '_')
        if params:
            # Incluir parámetros en el nombre del archivo de caché
            param_str = "_".join([f"{k}_{v}" for k, v in params.items()])
            cache_name = f"{cache_name}_{param_str}"

        cache_file = self.cache_dir / f"{cache_name}.json"
        local_file = self.data_dir / self.endpoint_to_local.get(endpoint, "")

        # Si la API no está disponible, usar caché o datos locales directamente
        if not self.api_available:
            print(f"API no disponible para {endpoint}. Usando datos almacenados.")
            if cache_file.exists():
                with open(cache_file, 'r', encoding='utf-8') as f:
                    self.last_source = "cache"
                    return json.load(f)
            elif local_file.exists():
                with open(local_file, 'r', encoding='utf-8') as f:
                    self.last_source = "local"
                    return json.load(f)
            else:
                print(f"No hay datos disponibles para {endpoint}")
                self.last_source = None
                return None

        # Si la API está disponible, intentar obtener datos frescos
        if not force_update and cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                self.last_source = "cache"
                return json.load(f)

        try:
            response = requests.get(f"{self.base_url}/{endpoint}", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Extraer el campo "data" solo para endpoints específicos
            endpoints_with_data = ["city/map", "city/jobs", "city/weather"]
            if endpoint in endpoints_with_data and isinstance(data, dict) and "data" in data:
                data = data["data"]

            # Guardar en caché
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.last_source = "api"
            print(f"Datos obtenidos exitosamente de la API para {endpoint}")
            return data
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {endpoint}: {e}")
            if cache_file.exists():
                print("Usando datos en caché como respaldo.")
                with open(cache_file, 'r', encoding='utf-8') as f:
                    self.last_source = "cache"
                    return json.load(f)
            elif local_file.exists():
                print("Usando datos locales como respaldo.")
                with open(local_file, 'r', encoding='utf-8') as f:
                    self.last_source = "local"
                    return json.load(f)
            else:
                print(f"No hay datos disponibles para {endpoint}")
                self.last_source = None
                return None

    def get_city_map(self) -> Optional[dict]:
        city_data = self.fetch_data("city/map")

        if city_data:
            # Si los datos no tienen nombre, asignar uno por defecto
            if "name" not in city_data:
                city_data["name"] = "TigerCity"

            return city_data
        return {
            "name": "TigerCity",
            "width": 30,
            "height": 30,
            "buildings": [],
            "roads": []
        }

    def get_jobs(self) -> list:
        jobs_data = self.fetch_data("city/jobs")

        if jobs_data:
            if isinstance(jobs_data, list):
                return jobs_data
            elif isinstance(jobs_data, dict) and "jobs" in jobs_data:
                return jobs_data["jobs"]

        # Devolver lista vacía si todo falla
        return []

    def get_weather(self) -> Optional[dict]:
        # Usar parámetros como en tu código original
        params = {"city": "TigerCity", "mode": "mode"}
        weather_data = self.fetch_data("city/weather", params=params)

        # Adaptarse a la estructura real de los datos
        if weather_data:
            # Extraer la condición actual del clima
            current_condition = weather_data.get('initial', {}).get('condition', 'unknown')

            # Mapear las condiciones a descripciones más amigables
            condition_translations = {
                'clear': 'Despejado',
                'clouds': 'Nublado',
                'rain_light': 'Lluvia ligera',
                'rain': 'Lluvia',
                'storm': 'Tormenta',
                'fog': 'Niebla',
                'wind': 'Viento',
                'heat': 'Calor',
                'cold': 'Frío',
                'unknown': 'Desconocido'
            }

            # Crear un summary descriptivo
            summary = condition_translations.get(current_condition, current_condition)

            # Calcular temperatura basada en la condición (esto es un ejemplo)
            temperature_base = {
                'clear': 25, 'clouds': 20, 'rain_light': 18, 'rain': 16,
                'storm': 15, 'fog': 12, 'wind': 22, 'heat': 30, 'cold': 10
            }

            temperature = temperature_base.get(current_condition, 20)

            # Devolver la estructura esperada por el juego
            return {
                "summary": summary,
                "temperature": temperature,

            }
        return {
            "summary": "Despejado",
            "temperature": 25,
        }

    def is_data_available(self):
        # Primero verifica si la API está disponible
        if self.api_available:
            return True

        # Luego verifica si hay datos en caché
        for endpoint in ["city/map", "city/jobs", "city/weather"]:
            cache_name = endpoint.replace("/", "_")
            cache_file = self.cache_dir / f"{cache_name}.json"

            if cache_file.exists():
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if data:  # Verifica que no esté vacío
                            return True
                except (json.JSONDecodeError, FileNotFoundError):
                    continue

        # Finalmente verifica datos locales
        for local_file in self.endpoint_to_local.values():
            data_file = self.data_dir / local_file
            if data_file.exists():
                try:
                    with open(data_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if data:  # Verifica que no esté vacío
                            return True
                except (json.JSONDecodeError, FileNotFoundError):
                    continue

        return False


