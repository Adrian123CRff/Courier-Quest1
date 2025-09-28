# test_weather_visual.py
# test_weather_visual.py

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
import arcade
from run_api.state_initializer import init_game_state
from run_api.api_client import ApiClient
from graphics.weather_markov import WeatherMarkov
from graphics.weather_renderer import WeatherRenderer
from graphics.map_manager import GameMap

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
SCREEN_TITLE = "Test Visual Clima + Mapa"


class WeatherTestView(arcade.View):
    def __init__(self, state, debug=False):
        super().__init__()
        self.state = state
        self.game_map = GameMap(state.city_map)

        # Configuración clima
        self.weather_markov = WeatherMarkov(api=ApiClient(), seed=123, debug=debug)
        self.weather_renderer = WeatherRenderer(self)

        self.total_time = 0.0
        self.tile_size = 20

        # Texto informativo
        self.info_text = arcade.Text(
            "",
            10,
            SCREEN_HEIGHT - 30,
            arcade.color.WHITE,
            16
        )

    def on_show(self):
        arcade.set_background_color(arcade.color.BLACK)
        # Para pruebas podrías forzar un clima inicial:
        # self.weather_markov.force_state("storm", 1.0)

    def on_update(self, delta_time: float):
        self.weather_markov.update(delta_time)
        self.weather_markov.apply_to_game_state(self.state)

        self.weather_renderer.update(delta_time, self.state.weather_state)

        cond = self.state.weather_state["condition"]
        temp = self.state.weather_state.get("temperature", "?")
        intensity = self.state.weather_state.get("intensity", "?")
        self.info_text.text = f"Clima: {cond} ({temp}°C, int={intensity})"

        #self.total_time += delta_time
        #if self.total_time > 15:
        #    arcade.close_window()

    def on_draw(self):
        self.clear()
        self.game_map.draw_debug(tile_size=self.tile_size, draw_grid_lines=True)
        self.weather_renderer.draw()
        self.info_text.draw()


def main(debug=False):  # 👈 por defecto es False
    api = ApiClient()
    state = init_game_state(api)

    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    view = WeatherTestView(state, debug=debug)
    window.show_view(view)
    arcade.run()


if __name__ == "__main__":
    # ✅ Ahora corre en modo normal (45–60 seg por clima)
    main()
