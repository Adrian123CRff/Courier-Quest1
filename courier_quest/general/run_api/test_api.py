# test_api.py
from api_client import ApiClient
from state_initializer import init_game_state


def test_api_connection():
    client = ApiClient(ttl=60)  # TTL de 60 segundos

    print("=== Test de conexión con la API ===")
    print(f"Base URL: {client.base_url}\n")

    # --- 1. Mapa de la ciudad ---
    print("1. Obteniendo mapa de la ciudad...")
    city_map = client.get_city_map()
    if city_map:
        print(f"   ✔ Nombre: {city_map.get('name')}")
        print(f"   ✔ Tamaño: {city_map['width']} x {city_map['height']}")
        print(f"   ✔ Nº de edificios: {len(city_map['buildings'])}")
        print(f"   ✔ Nº de carreteras: {len(city_map['roads'])}")
    else:
        print("   ✘ No se pudo obtener el mapa")

    # --- 2. Pedidos (jobs) ---
    print("\n2. Obteniendo pedidos (jobs)...")
    jobs = client.get_jobs()
    if jobs:
        print(f"   ✔ Total de pedidos: {len(jobs)}")
        for i, job in enumerate(jobs[:3]):  # muestra los primeros 3
            print(f"     - Pedido {i+1}: ID={job.get('id', 'N/A')}, "
                  f"Pickup={job.get('pickup')}, Dropoff={job.get('dropoff')}")
    else:
        print("   ✘ No se pudo obtener pedidos")

    # --- 3. Clima ---
    print("\n3. Obteniendo clima...")
    weather = client.get_weather()
    if weather:
        print(f"   ✔ Condición: {weather['summary']} ({weather['condition']})")
        print(f"   ✔ Temperatura: {weather['temperature']}°C")
    else:
        print("   ✘ No se pudo obtener clima")

if __name__ == "__main__":
    test_api_connection()
    init_game_state(ApiClient())