import requests
import json
import os
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional

class APIDataManager:
    """
    Módulo especializado exclusivamente en obtener y verificar datos del API
    """

    def __init__(self):
        self.base_url = "https://tigerds-api.kindflower-ccaf48b6.eastus.azurecontainerapps.io"
        self.cache_dir = "api_cache"
        self.data_dir = "data"

        # Crear directorios necesarios
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)

        print("✅ Módulo API Data Fetcher inicializado")

    def _get_data_hash(self, data: Any) -> str:
        """Calcular hash MD5 para detectar cambios"""
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def _fetch_from_api(self, endpoint: str) -> Optional[Any]:
        """Obtener datos directamente del API"""
        try:
            url = f"{self.base_url}{endpoint}"
            print(f"🌐 Conectando a: {url}")

            response = requests.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()
            print(f"✅ Datos obtenidos (Status: {response.status_code})")
            return data

        except requests.exceptions.RequestException as e:
            print(f"❌ Error de conexión: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"❌ Error decodificando JSON: {e}")
            return None

    def _save_data(self, data_type: str, data: Any):
        """Guardar datos en cache y como última versión"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Guardar en cache con timestamp
        cache_file = os.path.join(self.cache_dir, f"{timestamp}_{data_type}.json")
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Guardar última versión
        data_file = os.path.join(self.data_dir, f"{data_type}.json")
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"💾 {data_type} guardado")

    def _load_previous_data(self, data_type: str) -> Optional[Any]:
        """Cargar datos anteriores"""
        data_file = os.path.join(self.data_dir, f"{data_type}.json")
        if os.path.exists(data_file):
            try:
                with open(data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"❌ Error cargando {data_type}: {e}")
        return None

    def check_and_update_data(self, endpoint: str, data_type: str) -> Dict[str, Any]:
        """
        Verificar si hay cambios en el API y actualizar si es necesario

        Returns:
            Dict con:
            - data: los datos actuales
            - source: fuente de los datos ('api', 'cache', 'default')
            - changed: si hubo cambios
            - previous_hash: hash anterior (si existía)
            - current_hash: hash actual
        """
        print(f"\n🔍 Verificando {data_type}...")

        # 1. Obtener datos del API
        api_data = self._fetch_from_api(endpoint)

        if api_data is not None:
            current_hash = self._get_data_hash(api_data)

            # 2. Cargar datos anteriores para comparar
            previous_data = self._load_previous_data(data_type)

            if previous_data is not None:
                previous_hash = self._get_data_hash(previous_data)
                has_changed = current_hash != previous_hash

                if has_changed:
                    print(f"🔄 Cambios detectados en {data_type}")
                    print(f"   Hash anterior: {previous_hash}")
                    print(f"   Hash nuevo:    {current_hash}")

                    # Guardar nuevos datos
                    self._save_data(data_type, api_data)

                    return {
                        "data": api_data,
                        "source": "api",
                        "changed": True,
                        "previous_hash": previous_hash,
                        "current_hash": current_hash
                    }
                else:
                    print(f"✅ {data_type} sin cambios")
                    return {
                        "data": previous_data,
                        "source": "cache",
                        "changed": False,
                        "previous_hash": previous_hash,
                        "current_hash": current_hash
                    }
            else:
                # No hay datos anteriores, guardar estos
                print(f"📝 Primera vez obteniendo {data_type}")
                self._save_data(data_type, api_data)

                return {
                    "data": api_data,
                    "source": "api",
                    "changed": True,
                    "previous_hash": None,
                    "current_hash": current_hash
                }
        else:
            # 3. Fallback a datos locales
            print(f"📡 Usando datos locales para {data_type}")
            local_data = self._load_previous_data(data_type)

            if local_data is not None:
                current_hash = self._get_data_hash(local_data)
                return {
                    "data": local_data,
                    "source": "cache",
                    "changed": False,
                    "previous_hash": current_hash,
                    "current_hash": current_hash
                }
            else:
                # 4. Datos por defecto
                print(f"⚠️ Usando datos por defecto para {data_type}")
                default_data = self._get_default_data(data_type)
                current_hash = self._get_data_hash(default_data)

                return {
                    "data": default_data,
                    "source": "default",
                    "changed": False,
                    "previous_hash": None,
                    "current_hash": current_hash
                }

    def get_city_map(self) -> Dict[str, Any]:
        """Obtener y verificar mapa de la ciudad"""
        return self.check_and_update_data("/city/map", "city_map")

    def get_jobs(self) -> Dict[str, Any]:
        """Obtener y verificar pedidos"""
        return self.check_and_update_data("/city/jobs", "jobs")

    def get_weather(self) -> Dict[str, Any]:
        """Obtener y verificar clima"""
        return self.check_and_update_data("/city/weather", "weather")

    def _get_default_data(self, data_type: str) -> Any:
        """Datos por defecto para cada tipo"""
        defaults = {
            "city_map": {
                "version": "1.0",
                "width": 20,
                "height": 15,
                "tiles": [],
                "legend": {},
                "goal": 3000
            },
            "jobs": [],
            "weather": {
                "city": "TigerCity",
                "date": "2025-09-01",
                "bursts": [],
                "meta": {"units": {"intensity": "0-1"}}
            }
        }
        return defaults.get(data_type, {})

    def get_all_data(self) -> Dict[str, Any]:
        """Obtener y verificar todos los datos"""
        print("🚀 Obteniendo todos los datos del API...")

        results = {
            "city_map": self.get_city_map(),
            "jobs": self.get_jobs(),
            "weather": self.get_weather(),
            "timestamp": datetime.now().isoformat()
        }

        # Resumen
        print("\n📊 RESUMEN:")
        for key, result in results.items():
            if key != "timestamp":
                print(f"   {key}: {result['source']} - Cambios: {result['changed']}")

        return results

    def force_update(self) -> Dict[str, Any]:
        """Forzar actualización desde el API ignorando cambios"""
        print("🔄 Forzando actualización completa...")

        # Obtener datos frescos del API
        city_data = self._fetch_from_api("/city/map")
        jobs_data = self._fetch_from_api("/city/jobs")
        weather_data = self._fetch_from_api("/city/weather")

        # Guardar regardless of changes
        if city_data:
            self._save_data("city_map", city_data)
        if jobs_data:
            self._save_data("jobs", jobs_data)
        if weather_data:
            self._save_data("weather", weather_data)

        return {
            "city_map": city_data or self._load_previous_data("city_map") or self._get_default_data("city_map"),
            "jobs": jobs_data or self._load_previous_data("jobs") or self._get_default_data("jobs"),
            "weather": weather_data or self._load_previous_data("weather") or self._get_default_data("weather")
        }


# Función de prueba específica
def test_api_endpoints():
    """Probar específicamente cada endpoint del API"""
    fetcher = APIDataManager()

    print("=== PRUEBA DE ENDPOINTS DEL API ===")

    # Probar cada endpoint individualmente
    print("\n1. Probando /city/map:")
    city_result = fetcher.get_city_map()
    print(f"   Fuente: {city_result['source']}")
    print(f"   Cambios: {city_result['changed']}")
    print(f"   Tipo de datos: {type(city_result['data'])}")
    if isinstance(city_result['data'], dict):
        print(f"   Keys: {list(city_result['data'].keys())}")

    print("\n2. Probando /city/jobs:")
    jobs_result = fetcher.get_jobs()
    print(f"   Fuente: {jobs_result['source']}")
    print(f"   Cambios: {jobs_result['changed']}")
    print(f"   Tipo de datos: {type(jobs_result['data'])}")
    if isinstance(jobs_result['data'], list):
        print(f"   Cantidad de jobs: {len(jobs_result['data'])}")
        if jobs_result['data']:
            print(f"   Ejemplo del primer job: {jobs_result['data'][0]}")

    print("\n3. Probando /city/weather:")
    weather_result = fetcher.get_weather()
    print(f"   Fuente: {weather_result['source']}")
    print(f"   Cambios: {weather_result['changed']}")
    print(f"   Tipo de datos: {type(weather_result['data'])}")
    if isinstance(weather_result['data'], dict):
        print(f"   Keys: {list(weather_result['data'].keys())}")
        if 'bursts' in weather_result['data']:
            print(f"   Cantidad de bursts: {len(weather_result['data']['bursts'])}")

if __name__ == "__main__":
    test_api_endpoints()