from api_handler import APIHandler
import json
import time

import json
import time

def test_api_connection():
    """Prueba la conexión con la API"""
    handler = APIHandler()

    print("Probando conexión con la API...")
    print(f"URL base: {handler.base_url}")

    # Forzar actualización desde la API (ignorar caché)
    print("\n1. Obteniendo mapa de la ciudad (forzando actualización)...")
    city_map = handler.get_city_map()  # Usar el método adaptado
    print(f"Resultado: {'Éxito' if city_map else 'Fallo'}")
    print(f"Ciudad: {city_map.get('name', 'No disponible') if city_map else 'N/A'}")
    if city_map and 'width' in city_map and 'height' in city_map:
        print(f"Tamaño del mapa: {city_map['width']}x{city_map['height']}")

    print("\n2. Obteniendo pedidos (forzando actualización)...")
    jobs = handler.get_jobs()  # Usar el método estándar
    print(f"Resultado: {'Éxito' if jobs else 'Fallo'}")
    if jobs:
        if isinstance(jobs, list):
            print(f"Número de trabajos: {len(jobs)}")
            # Mostrar algunos trabajos de ejemplo
            for i, job in enumerate(jobs[:3]):  # Mostrar solo los primeros 3
                print(f"  Trabajo {i+1}: {job.get('id', 'N/A')}")
        elif isinstance(jobs, dict) and 'jobs' in jobs:
            print(f"Número de trabajos: {len(jobs['jobs'])}")
        else:
            print(f"Formato de datos: {type(jobs)}")

    print("\n3. Obteniendo clima (forzando actualización)...")
    weather = handler.get_weather()  # Usar el método adaptado
    print(f"Resultado: {'Éxito' if weather else 'Fallo'}")
    if weather:
        print(f"Clima: {weather.get('summary', 'No disponible')}")
        print(f"Temperatura: {weather.get('temperature', 'N/D')}°C")
        # Opcional: mostrar la condición raw para depuración
        if 'raw_data' in weather:
            print(f"Condición original: {weather['raw_data'].get('initial', {}).get('condition', 'N/A')}")

    print(f"\nFuente de datos: {handler.last_source}")
if __name__ == "__main__":
    test_api_connection()