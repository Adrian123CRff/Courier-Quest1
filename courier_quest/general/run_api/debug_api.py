import requests
import json


def debug_api_responses():
    """Depura la estructura real de las respuestas API"""

    # Endpoints a probar
    endpoints = [
        ("city/map", "Mapa de la ciudad", {}),
        ("city/jobs", "Pedidos/trabajos", {}),
        ("city/weather", "Información del clima", {"city": "TigerCity", "mode": "mode"})
    ]

    base_url = "https://tigerds-api.kindflower-ccaf48b6.eastus.azurecontainerapps.io"

    for endpoint, description, params in endpoints:
        print("=" * 60)
        print(f"DEPURANDO: {description}")
        print(f"Endpoint: {endpoint}")
        print("=" * 60)

        try:
            # Hacer la solicitud directamente a la API
            url = f"{base_url}/{endpoint}"
            response = requests.get(url, params=params, timeout=10)

            print(f"Status Code: {response.status_code}")
            print(f"URL completa: {response.url}")

            if response.status_code == 200:
                data = response.json()
                print("Estructura de la respuesta:")
                print(json.dumps(data, indent=2, ensure_ascii=False))

                # Análisis de la estructura
                if isinstance(data, dict):
                    if "data" in data:
                        print("\n✓ La respuesta contiene un campo 'data'")
                        print(f"Tipo de 'data': {type(data['data'])}")
                    else:
                        print("\n✗ La respuesta NO contiene un campo 'data'")

                    # Buscar campos comunes
                    for field in ["name", "summary", "temperature", "jobs"]:
                        if field in data:
                            print(f"Campo '{field}' encontrado en respuesta principal")
                        elif "data" in data and isinstance(data["data"], dict) and field in data["data"]:
                            print(f"Campo '{field}' encontrado dentro de 'data'")
            else:
                print(f"Error: {response.text}")

        except Exception as e:
            print(f"Excepción al llamar {endpoint}: {e}")

        print("\n\n")


if __name__ == "__main__":
    debug_api_responses()