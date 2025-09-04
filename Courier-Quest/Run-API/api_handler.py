import requests
import json
import os
from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class APIHandler:
    def __init__(self, base_url="https://tigerds-api.kindflower-ccaf48b6.eastus.azurecontainerapps.io"):
        self.base_url = base_url
        self.cache_dir = "api_cache"
        self.data_dir = "data"
        self.last_source = None  # Para rastrear la última fuente de datos

        # Crear directorios si no existen
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)

    def _make_request(self, endpoint):
        """Realiza una petición a la API y maneja errores"""
        url = f"{self.base_url}{endpoint}"
        try:
            logger.info(f"Intentando conectar con: {url}")
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()
            self._save_to_cache(endpoint, data)
            self.last_source = "api"
            logger.info("Conexión exitosa con la API")

            return data
        except requests.exceptions.Timeout:
            logger.warning("Timeout al conectar con la API")
            data = self._load_from_cache(endpoint)
            self.last_source = "cache" if data else "error"
            return data
        except requests.exceptions.ConnectionError:
            logger.warning("Error de conexión con la API")
            data = self._load_from_cache(endpoint)
            self.last_source = "cache" if data else "error"
            return data
        except requests.exceptions.HTTPError as e:
            logger.warning(f"Error HTTP: {e}")
            data = self._load_from_cache(endpoint)
            self.last_source = "cache" if data else "error"
            return data
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error de solicitud: {e}")
            data = self._load_from_cache(endpoint)
            self.last_source = "cache" if data else "error"
            return data
        except Exception as e:
            logger.error(f"Error inesperado: {e}")
            self.last_source = "error"
            return None

    def _save_to_cache(self, endpoint, data):
        """Guarda la respuesta de la API en caché"""
        try:
            # Crear nombre de archivo seguro a partir del endpoint
            filename = endpoint.replace("/", "_")[1:] + ".json"
            cache_path = os.path.join(self.cache_dir, filename)

            # Añadir timestamp a los datos
            cached_data = {
                "timestamp": datetime.now().isoformat(),
                "data": data
            }

            with open(cache_path, 'w') as f:
                json.dump(cached_data, f, indent=2)

            logger.info(f"Datos guardados en caché: {cache_path}")
        except Exception as e:
            logger.error(f"Error al guardar en caché: {e}")

    def _load_from_cache(self, endpoint):
        """Carga datos desde el caché si están disponibles"""
        try:
            filename = endpoint.replace("/", "_")[1:] + ".json"
            cache_path = os.path.join(self.cache_dir, filename)

            if os.path.exists(cache_path):
                with open(cache_path, 'r') as f:
                    cached_data = json.load(f)

                logger.info(f"Datos cargados desde caché: {cache_path}")
                self.last_source = "cache"
                return cached_data["data"]
            else:
                # Si no hay caché, intentar cargar desde archivos locales
                data = self._load_local_data(endpoint)
                self.last_source = "local" if data else "error"
                return data
        except Exception as e:
            logger.error(f"Error al cargar desde caché: {e}")
            data = self._load_local_data(endpoint)
            self.last_source = "local" if data else "error"
            return data

    def _load_local_data(self, endpoint):
        """Carga datos desde archivos locales de respaldo"""
        try:
            # Mapear endpoints a archivos locales
            endpoint_to_file = {
                "/city/map": "ciudad.json",
                "/city/jobs": "pedidos.json",
                "/city/weather": "weather.json"
            }

            filename = endpoint_to_file.get(endpoint)
            if not filename:
                return None

            local_path = os.path.join(self.data_dir, filename)

            if os.path.exists(local_path):
                with open(local_path, 'r') as f:
                    data = json.load(f)

                logger.info(f"Datos cargados desde archivo local: {local_path}")
                return data
            else:
                logger.error(f"Archivo local no encontrado: {local_path}")
                return None
        except Exception as e:
            logger.error(f"Error al cargar datos locales: {e}")
            return None

    def get_city_map(self):
        """Obtiene el mapa de la ciudad"""
        return self._make_request("/city/map")

    def get_jobs(self):
        """Obtiene los pedidos disponibles"""
        return self._make_request("/city/jobs")

    def get_weather(self):
        """Obtiene la información del clima"""
        return self._make_request("/city/weather")