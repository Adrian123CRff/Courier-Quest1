# game_view.py
import arcade
from general.graphics.map_manager import GameMap

class GameView(arcade.View):
    def __init__(self, state):
        super().__init__()
        # Acepta tanto dict como objetos con atributo city_map
        self.state = state or {}
        if isinstance(state, dict):
            city_map = state.get("city_map", {})
        else:
            city_map = getattr(state, "city_map", {})
        self.game_map = GameMap(city_map)

    def on_show(self):
        arcade.set_background_color(arcade.color.BLACK)

    def on_draw(self):
        self.clear()

        # Info del mapa
        name = getattr(self.game_map, "name", "Mapa")
        arcade.draw_text(f"Mapa: {name}", 10, 580, arcade.color.WHITE,16)
        # Render de prueba (colores sólidos)
        self.game_map.draw_debug(tile_size=20)