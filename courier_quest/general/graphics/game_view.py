# game_view.py
import arcade
from graphics.map_manager import GameMap

class GameView(arcade.View):
    def __init__(self, state):
        super().__init__()
        # Ahora asumimos que siempre es un GameState válido
        self.state = state
        self.game_map = GameMap(self.state.city_map)

        # Texto preparado (Arcade 3.3.2)
        self.map_title = arcade.Text(
            f"Mapa: {getattr(self.game_map, 'name', 'Mapa')}",
            start_x=10,
            start_y=580,
            color=arcade.color.WHITE,
            font_size=16,
        )

    def on_show_view(self):
        arcade.set_background_color(arcade.color.BLACK)

    def on_draw(self):
        self.clear()

        # Info del mapa
        self.map_title.draw()

        # Render de prueba (colores sólidos)
        self.game_map.draw_debug(tile_size=20)