# game_view.py
import arcade
from map_manager import GameMap

class GameView(arcade.View):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.game_map = GameMap(state.city_map)

    def on_show(self):
        arcade.set_background_color(arcade.color.BLACK)

    def on_draw(self):
        self.clear()

        # Info del mapa
        arcade.draw_text(f"Mapa: {self.game_map.name}", 10, 580,
                         arcade.color.WHITE, 16)

        # Render de prueba (colores sólidos)
        self.game_map.draw_debug(tile_size=20)