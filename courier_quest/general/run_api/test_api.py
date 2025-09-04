from api_handler import APIHandler


def test_api_connection():
    """Prueba la conexión con la API"""
    handler = APIHandler()

    print("Probando conexión con la API...")

    # Probar cada endpoint
    print("\n1. Obteniendo mapa de la ciudad...")
    city_map = handler.get_city_map()
    print(f"Resultado: {'Éxito' if city_map else 'Fallo'}")

    print("\n2. Obteniendo pedidos...")
    jobs = handler.get_jobs()
    print(f"Resultado: {'Éxito' if jobs else 'Fallo'}")

    print("\n3. Obteniendo clima...")
    weather = handler.get_weather()
    print(f"Resultado: {'Éxito' if weather else 'Fallo'}")

    print(f"\nFuente de datos: {handler.last_source}")


if __name__ == "__main__":
    test_api_connection()