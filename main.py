from src.logica.api.api_manager import APIManager

def load_game_data():
    api_manager = APIManager(base_url="https://tigerdatastructures.io")

    # Cargar datos del mapa
    map_data = api_manager.fetch_data("city/map")
    if map_data is None:
        map_data = api_manager.load_local_data("city/map")
        if map_data is None:
            raise Exception("No se pudo cargar el mapa.")

    # Cargar datos de pedidos
    jobs_data = api_manager.fetch_data("city/jobs")
    if jobs_data is None:
        jobs_data = api_manager.load_local_data("city/jobs")
        if jobs_data is None:
            raise Exception("No se pudieron cargar los pedidos.")

    # Cargar datos del clima
    weather_data = api_manager.fetch_data("city/weather")
    if weather_data is None:
        weather_data = api_manager.load_local_data("city/weather")
        if weather_data is None:
            raise Exception("No se pudo cargar el clima.")

    return map_data, jobs_data, weather_data


def main():
    try:
        map_data, jobs_data, weather_data = load_game_data()
        print("Datos cargados exitosamente.")
        # Aquí puedes pasar estos datos a tu juego o estado inicial
        # Por ejemplo:
        # game_state = GameState(map_data, jobs_data, weather_data)
    except Exception as e:
        print(f"Error al cargar los datos: {e}")


if __name__ == "__main__":
    main()

