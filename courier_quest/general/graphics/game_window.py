# general/graphics/game_window.py
import arcade
from general.game.game_state import GameState


class GameWindow(arcade.Window):
    def __init__(self):
        super().__init__(width=1024, height=768, title="Courier Quest")
        self.game_state = None
        self.setup()

    def setup(self):
        # Inicializar el estado del juego
        self.game_state = GameState()

        # Cargar datos del mapa, pedidos y clima
        from general.run_api.api_manager import APIManager
        api_manager = APIManager()
        map_data = api_manager.fetch_data("city/map")
        jobs_data = api_manager.fetch_data("city/jobs")
        weather_data = api_manager.fetch_data("city/weather")

        # Inicializar el estado del juego con estos datos
        self.game_state.initialize_game(map_data, jobs_data, weather_data)

    def on_draw(self):
        arcade.start_render()
        # Dibujar el mapa y otros elementos
        self.draw_map()
        self.draw_courier()
        self.draw_hud()

    def on_update(self, delta_time):
        # Actualizar lógica del juego
        self.game_state.update(delta_time)

    def on_key_press(self, key, modifiers):
        # Manejar entrada del teclado
        pass

    def draw_map(self):
        # Dibujar el mapa basado en game_state.map_data
        pass

    def draw_courier(self):
        # Dibujar el repartidor
        pass

    def draw_hud(self):
        # Dibujar la interfaz de usuario
        pass