# test_weather_visual.py
import arcade
import time
from run_api.state_initializer import init_game_state
from run_api.api_client import ApiClient
from graphics.weather_markov import WeatherMarkov
from graphics.weather_renderer import WeatherRenderer
from graphics.map_manager import GameMap

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
SCREEN_TITLE = "Test Visual Clima + Mapa"

class WeatherTestView(arcade.View):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.game_map = GameMap(state["city_map"])

        # Configuración clima
        self.weather_markov = WeatherMarkov(api=ApiClient(), seed=123)
        self.weather_renderer = WeatherRenderer(self.window)

        self.total_time = 0.0
        self.tile_size = 20

    def on_show(self):
        arcade.set_background_color(arcade.color.BLACK)

    def on_update(self, delta_time: float):
        # Actualizar cadena de Markov
        self.weather_markov.update(delta_time)
        self.weather_markov.apply_to_game_state(self.state)

        # Actualizar renderer con nuevo estado
        self.weather_renderer.update(delta_time, self.state["weather_state"])

        self.total_time += delta_time
        # Cerrar automáticamente después de 15 segundos
        if self.total_time > 15:
            arcade.close_window()

    def on_draw(self):
        self.clear()
        # Dibujar mapa base
        self.game_map.draw_debug(tile_size=self.tile_size, draw_grid_lines=True)
        # Dibujar capa de clima
        self.weather_renderer.draw()

        # Texto informativo
        cond = self.state["weather_state"]["condition"]
        temp = self.state["weather_state"].get("temperature", "?")
        arcade.draw_text(
            f"Clima: {cond} ({temp}°C)", 10, SCREEN_HEIGHT - 30,
            arcade.color.WHITE, 16
        )

def main():
    api = ApiClient()
    state = init_game_state(api)

    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    view = WeatherTestView(state)
    window.show_view(view)
    arcade.run()

if __name__ == "__main__":
    main()
