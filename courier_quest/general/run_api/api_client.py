import requests
import time
from datetime import datetime
from pathlib import Path
import json
import os
import logging
from typing import Optional, Any, Dict, Union, List, Tuple
import tempfile
import shutil

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ApiClient')


class ApiClient:
    """Cliente HTTP con caché en disco, fallback a /data y escritura atómica.

    Características principales:
    - requests.Session() para reutilizar conexiones
    - caché principal (endpoint_base.json) y archivos timestamped (endpoint_base_YYYYmmdd_HHMMSS.json)
    - escritura atómica de caché
    - fallback a archivos locales en /data según mapping
    - TTL y logging de caché "stale"
    - manejo de params en nombres de caché
    """

    def __init__(
        self,
        base_url: str = "https://tigerds-api.kindflower-ccaf48b6.eastus.azurecontainerapps.io",
        cache_dir: str = "api_cache",
        data_dir: str = "data",
        ttl: int = 3600,
        connection_retry_interval: int = 60,
        health_endpoint: str = "city/map",
    ):
        self.base_url = base_url.rstrip("/")
        self.cache_dir = Path(cache_dir)
        self.data_dir = Path(data_dir)
        self.ttl = ttl
        self.offline_mode = False
        self.last_connection_attempt = 0
        self.connection_retry_interval = connection_retry_interval
        self.health_endpoint = health_endpoint

        # Session para reaprovechar conexiones
        self.session = requests.Session()

        # Asegurar directorios
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        self.data_dir.mkdir(exist_ok=True, parents=True)

        # Mapeo endpoint -> archivo local en /data
        self.endpoint_to_local = {
            "city/map": "ciudad.json",
            "city/jobs": "pedidos.json",
            "city/weather": "weather.json",
        }

        # Intento inicial no bloqueante
        try:
            self._check_connection()
        except Exception as e:
            logger.debug(f"Inicialización: chequeo de conexión falló: {e}")

    # ----------------------------
    # Helpers
    # ----------------------------
    def _check_connection(self) -> bool:
        """Comprueba si el endpoint de health responde. Evita reintentos frecuentes.

        Retorna True si hay conexión y False si no.
        """
        current_time = time.time()
        if (
            current_time - self.last_connection_attempt < self.connection_retry_interval
            and self.offline_mode
        ):
            logger.debug("Chequeo de conexión: salto por retry interval (estamos offline).")
            return False

        self.last_connection_attempt = current_time
        try:
            url = f"{self.base_url}/{self.health_endpoint.lstrip('/')}"
            resp = self.session.get(url, timeout=3)
            self.offline_mode = not resp.ok
            if not self.offline_mode:
                logger.info("Conexión al API establecida. Modo online activado.")
            else:
                logger.warning("API respondió con status != 200. Modo offline activado.")
            return not self.offline_mode
        except (requests.ConnectionError, requests.Timeout, requests.RequestException) as e:
            self.offline_mode = True
            logger.warning(f"No se pudo conectar al API ({e}). Modo offline activado.")
            return False

    @staticmethod
    def _params_to_str(params: Optional[dict]) -> str:
        if not params:
            return ""
        # Normalizar a string ordenado para consistencia
        return "_".join([f"{k}_{v}" for k, v in sorted(params.items())])

    def _cache_path(self, endpoint: str, params: Optional[dict] = None) -> Path:
        cache_name = endpoint.replace("/", "_")
        param_str = self._params_to_str(params)
        if param_str:
            cache_name = f"{cache_name}_{param_str}"
        return self.cache_dir / f"{cache_name}.json"

    def _get_latest_cache(self, endpoint: str, params: Optional[dict] = None) -> Tuple[Optional[Path], Optional[float]]:
        base_name = endpoint.replace("/", "_")
        param_str = self._params_to_str(params)
        if param_str:
            base_name = f"{base_name}_{param_str}"

        pattern = f"{base_name}_*.json"
        cache_files = list(self.cache_dir.glob(pattern))

        if not cache_files:
            main_cache = self._cache_path(endpoint, params)
            if main_cache.exists():
                return main_cache, main_cache.stat().st_mtime
            return None, None

        latest_file = max(cache_files, key=lambda p: p.stat().st_mtime)
        return latest_file, latest_file.stat().st_mtime

    @staticmethod
    def _load_json_file(path: Path) -> Optional[Union[dict, list]]:
        if not path.exists():
            logger.debug(f"Archivo no encontrado: {path}")
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Error al decodificar JSON en {path}: {e}")
            return None
        except OSError as e:
            logger.error(f"Error al leer archivo {path}: {e}")
            return None

    @staticmethod
    def _atomic_save_json(path: Path, data: Any) -> bool:
        """Escritura atómica del JSON en disco (escribe archivo temporal y lo mueve)."""
        tmp_name = None
        try:
            path.parent.mkdir(exist_ok=True, parents=True)
            with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(path.parent)) as tmp:
                json.dump(data, tmp, indent=2, ensure_ascii=False)
                tmp_name = tmp.name
            shutil.move(tmp_name, str(path))
            logger.info(f"Datos guardados en {path}")
            return True
        except (OSError, IOError, json.JSONDecodeError) as e:
            logger.error(f"Error al guardar en {path}: {e}")
            if tmp_name and os.path.exists(tmp_name):
                try:
                    os.remove(tmp_name)
                except OSError:
                    pass
            return False

    def _is_cache_valid(self, path: Path) -> bool:
        if not path.exists():
            return False
        age = time.time() - path.stat().st_mtime
        return age <= self.ttl

    def _get_default_data(self, endpoint: str) -> Optional[Union[dict, list]]:
        """Devuelve datos por defecto para endpoints específicos cuando todo falla."""
        defaults = {
            "city/map": self._get_fallback_map(),
            "city/jobs": [],
            "city/weather": {
                "condition": "clear",
                "summary": "Despejado",
                "temperature": 25,
                "intensity": 0.5,
                "speed_multiplier": 1.0,
                "bursts": [],
                "city": "UnknownCity",
                "date": datetime.now().strftime("%Y-%m-%d")
            }
        }
        return defaults.get(endpoint)

    # ----------------------------
    # Fetch principal
    # ----------------------------
    def fetch_data(self, endpoint: str, params: dict = None) -> Optional[Union[dict, list]]:
        """Estrategia de fetch:

        1. Intentar API si hay conexión
        2. Si API falla o no devuelve datos, usar el cache más reciente (incluir archivos timestamped)
        3. Si no hay cache, usar /data local según mapping
        4. Si nada disponible, devolver default
        """
        has_connection = self._check_connection()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cache_file = self._cache_path(endpoint, params)

        base_name = endpoint.replace("/", "_")
        param_str = self._params_to_str(params)
        if param_str:
            base_name = f"{base_name}_{param_str}"
        timestamped_cache_file = self.cache_dir / f"{base_name}_{timestamp}.json"

        local_name = self.endpoint_to_local.get(endpoint)
        local_file = (self.data_dir / local_name) if local_name else None

        api_data = None
        if has_connection:
            try:
                url = f"{self.base_url}/{endpoint.lstrip('/')}"
                logger.info(f"Intentando actualizar datos desde API: {url}")
                resp = self.session.get(url, params=params, timeout=6)
                resp.raise_for_status()
                api_data = resp.json()
                if isinstance(api_data, dict) and "data" in api_data:
                    api_data = api_data["data"]

                # Guardar en caché timestamped y principal (escritura atómica)
                self._atomic_save_json(timestamped_cache_file, api_data)
                self._atomic_save_json(cache_file, api_data)
                logger.info("Datos actualizados desde API y guardados en caché.")
                return api_data
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError, requests.RequestException) as e:
                logger.warning(f"API no disponible al intentar fetch: {e}")
                self.offline_mode = True
                # Continuar con estrategias de fallback

        # Usar cache más reciente
        latest_cache, cache_time = self._get_latest_cache(endpoint, params)
        if latest_cache:
            cached_data = self._load_json_file(latest_cache)
            if cached_data is not None:
                age = time.time() - cache_time
                valid = self._is_cache_valid(latest_cache)
                status = "CACHÉ" if valid else "CACHÉ_STALE"
                logger.info(f"[{status}] {endpoint} cargado desde caché (edad: {int(age)}s)")
                return cached_data

        # Fallback local
        if local_file and local_file.exists():
            local_data = self._load_json_file(local_file)
            if local_data is not None:
                logger.info(f"[LOCAL] {endpoint} cargado desde /data")
                # actualizar cache principal
                self._atomic_save_json(cache_file, local_data)
                return local_data

        logger.error(f"[ERROR] No hay datos disponibles para {endpoint}")
        return self._get_default_data(endpoint)

    # ----------------------------
    # Wrappers específicos
    # ----------------------------
    def get_city_map(self) -> Dict[str, Any]:
        try:
            data = self.fetch_data("city/map")
            if not data or not isinstance(data, dict):
                data = self._get_fallback_map()

            # Validar campos REQUERIDOS dinámicamente
            required_fields = ["start_time", "max_time", "goal"]
            missing_fields = [field for field in required_fields if field not in data]

            if missing_fields:
                print(f"⚠️  ADVERTENCIA: Mapa falta campos: {missing_fields}")
                data = self._complete_missing_fields(data)

            # Asegurar que tenemos tiles y legend
            if not data.get("tiles") or not data.get("legend"):
                # Intentar fallback con cache
                data = _fallback_tiles_from_cache(data)  # Nota: Esta función está en state_initializer, podríamos moverla a api_client o viceversa

            return {
                "name": data.get("name", data.get("city_name", "UnknownCity")),
                "width": data.get("width", 20),
                "height": data.get("height", 15),
                "tiles": data.get("tiles", []),
                "legend": data.get("legend", {}),
                "goal": data.get("goal", 1000),
                "start_time": data.get("start_time"),
                "max_time": data.get("max_time"),
                "version": data.get("version", "1.0"),
            }

        except Exception as e:
            logger.error(f"Error al procesar el mapa: {e}")
            return self._get_fallback_map()

    @staticmethod
    def _complete_missing_fields(data: Dict[str, Any]) -> Dict[str, Any]:
        """Completa campos faltantes con valores por defecto GENÉRICOS"""
        defaults = {
            "start_time": "2025-01-01T00:00:00Z",
            "max_time": 900,
            "goal": 1000,
        }

        for field, default in defaults.items():
            if field not in data:
                data[field] = default
                print(f"⚠️  Campo {field} completado con valor por defecto: {default}")

        return data

    @staticmethod
    def _fallback_tiles_from_cache(city_map: dict) -> dict:
        """
        Si city_map no contiene 'tiles', intenta leer api_cache/city_map.json
        y devolver una versión con 'tiles' si existe.
        """
        # Si ya trae tiles, devolver tal cual
        if city_map and isinstance(city_map, dict) and city_map.get("tiles"):
            return city_map

        # Intentar leer cache
        cache_path = Path("api_cache") / "city_map.json"
        try:
            if cache_path.exists():
                with cache_path.open(encoding="utf-8") as f:
                    cached = json.load(f)
                if isinstance(cached, dict) and cached.get("tiles"):
                    print(f"[FALLBACK] API no trae 'tiles' -> usando 'tiles' desde cache: {cache_path}")
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

    @staticmethod
    def _get_fallback_map() -> Dict[str, Any]:
        """Fallback GENÉRICO (no específico de TigerCity)"""
        return {
            "name": "GenericCity",
            "width": 20,
            "height": 15,
            "tiles": [["C" for _ in range(20)] for _ in range(15)],
            "legend": {
                "C": {"name": "calle", "surface_weight": 1.00},
                "B": {"name": "edificio", "blocked": True},
                "P": {"name": "parque", "surface_weight": 0.95},
            },
            "goal": 1000,
            "start_time": "2025-01-01T00:00:00Z",
            "max_time": 900,
            "version": "1.0",
        }

    @staticmethod
    def _get_default_map() -> Dict[str, Any]:
        """Mapa por defecto (para compatibilidad)"""
        return ApiClient._get_fallback_map()

    def get_jobs(self) -> list:
        try:
            data = self.fetch_data("city/jobs")
            if not data:
                return []

            if isinstance(data, dict) and "jobs" in data:
                jobs = data["jobs"]
            elif isinstance(data, list):
                jobs = data
            else:
                logger.warning("Formato de pedidos inesperado")
                return []

            valid_jobs = []
            for job in jobs:
                if self._validate_job(job):
                    valid_jobs.append(job)

            if len(valid_jobs) < len(jobs):
                logger.warning(f"Se descartaron {len(jobs) - len(valid_jobs)} pedidos inválidos")

            return valid_jobs
        except Exception as e:
            logger.error(f"Error al procesar pedidos: {e}")
            return []

    def _validate_job(self, job: Dict) -> bool:
        required_fields = ["id", "pickup", "dropoff", "payout", "deadline", "weight"]
        return all(field in job for field in required_fields)

    def get_weather(self) -> Dict[str, Any]:
        try:
            data = self.fetch_data("city/weather")
            if not data:
                data = {}

            bursts = data.get("bursts", []) if isinstance(data, dict) else []
            current_burst = bursts[0] if bursts else {}
            condition = current_burst.get("condition", "clear")
            intensity = current_burst.get("intensity", 0.5)

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
            }

            speed_multipliers = {
                "clear": 1.00,
                "clouds": 0.98,
                "rain_light": 0.90,
                "rain": 0.85,
                "storm": 0.75,
                "fog": 0.88,
                "wind": 0.92,
                "heat": 0.90,
                "cold": 0.92,
            }

            summary = translations.get(condition, condition)
            temp_defaults = {
                "clear": 25,
                "clouds": 20,
                "rain_light": 18,
                "rain": 16,
                "storm": 15,
                "fog": 12,
                "wind": 22,
                "heat": 30,
                "cold": 10,
            }
            temperature = temp_defaults.get(condition, 20)

            return {
                "condition": condition,
                "summary": summary,
                "temperature": temperature,
                "intensity": intensity,
                "speed_multiplier": speed_multipliers.get(condition, 1.0),
                "bursts": bursts,
                "city": data.get("city", "UnknownCity") if isinstance(data, dict) else "UnknownCity",
                "date": data.get("date", datetime.now().strftime("%Y-%m-%d")) if isinstance(data, dict) else datetime.now().strftime("%Y-%m-%d")
            }
        except Exception as e:
            logger.error(f"Error al procesar clima: {e}")
            return {
                "condition": "clear",
                "summary": "Despejado",
                "temperature": 25,
                "intensity": 0.5,
                "speed_multiplier": 1.0,
                "bursts": [],
                "city": "UnknownCity",
                "date": datetime.now().strftime("%Y-%m-%d")
            }

    def get_connection_status(self) -> Dict[str, Any]:
        return {
            "online": not self.offline_mode,
            "last_attempt": self.last_connection_attempt,
            "cache_dir": str(self.cache_dir),
            "data_dir": str(self.data_dir),
        }

    def clear_cache(self, endpoint: str = None) -> bool:
        try:
            if endpoint:
                pattern = f"{endpoint.replace('/', '_')}*.json"
                files = list(self.cache_dir.glob(pattern))
            else:
                files = list(self.cache_dir.glob("*.json"))

            for file in files:
                file.unlink()

            logger.info(f"Cache limpiado: {len(files)} archivos eliminados")
            return True
        except OSError as e:
            logger.error(f"Error al limpiar cache: {e}")
            return False