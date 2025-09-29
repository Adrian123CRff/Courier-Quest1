import arcade
from arcade import Window, View, Text
from run_api.api_client import ApiClient
from run_api.state_initializer import init_game_state
from .map_manager import GameMap, FLIP_Y
from game.player_manager import Player
from graphics.weather_markov import WeatherMarkov
from graphics.weather_renderer import WeatherRenderer

SCREEN_SIZE = 800
TILE_SIZE = 24


class MapPlayerView(View):
    def __init__(self, state) -> None:
        super().__init__()
        # Siempre trabajamos con GameState válido
        self.state = state
        self.game_map = GameMap(self.state.city_map)

        rows = len(self.game_map.grid)
        cols = len(self.game_map.grid[0]) if rows > 0 else 0

        # Posición inicial al centro
        start_cx = cols // 2
        start_cy = rows // 2
        self.player: Player = Player((start_cx, start_cy), TILE_SIZE, rows, flip_y=FLIP_Y)

        self.base_scale = 1.0
        if hasattr(self.player, "sprite"):
            self.base_scale = abs(self.player.sprite.scale_x)

        self.facing = "right"

        # Textos Arcade 3.3.2
        self.pos_text: Text = Text(
            f"Pos cell: ({self.player.cell_x},{self.player.cell_y})",
            10, SCREEN_SIZE - 20,
            arcade.color.WHITE,
            14
        )

        self.weather_markov = WeatherMarkov(api=ApiClient())
        self.weather_renderer = WeatherRenderer(self)

        self.weather_text: Text = Text(
            "Clima: clear (?)",
            10, SCREEN_SIZE - 40,
            arcade.color.LIGHT_BLUE,
            14
        )

    def on_show_view(self) -> None:
        arcade.set_background_color(arcade.color.DARK_SLATE_GRAY)

    def on_draw(self) -> None:
        self.clear()
        # Dibuja mapa + jugador
        self.game_map.draw_debug(tile_size=TILE_SIZE, draw_grid_lines=True)
        self.player.draw()

        # Actualiza y dibuja textos
        self.pos_text.text = f"Pos cell: ({self.player.cell_x},{self.player.cell_y})"
        self.pos_text.draw()
        self.weather_text.draw()

        # Renderiza clima
        self.weather_renderer.draw()

    def on_update(self, dt: float) -> None:
        # Actualizar jugador
        self.player.update(dt)

        # Clima dinámico
        self.weather_markov.update(dt)
        self.weather_markov.apply_to_game_state(self.state)
        self.weather_renderer.update(dt, self.state.weather_state)

        # Actualizar texto de clima
        cond = self.state.weather_state.get("condition", "?")
        intensity = self.state.weather_state.get("intensity", "?")
        self.weather_text.text = f"Clima: {cond} (int={intensity})"

    def _apply_facing(self):
        """Ajusta el sprite según la dirección actual."""
        if not hasattr(self.player, "sprite"):
            return
        mag = self.base_scale
        if self.facing == "right":
            self.player.sprite.angle = 0
            self.player.sprite.scale_x = -mag
        elif self.facing == "left":
            self.player.sprite.angle = 0
            self.player.sprite.scale_x = mag
        elif self.facing == "up":
            self.player.sprite.angle = 90
            self.player.sprite.scale_x = mag
        elif self.facing == "down":
            self.player.sprite.angle = 270
            self.player.sprite.scale_x = mag

    # ---------------- Input ----------------
    def on_key_press(self, key: int, modifiers: int) -> None:
        dx, dy = 0, 0
        if key == arcade.key.UP:
            dy = -1
            self.facing = "up"
        elif key == arcade.key.DOWN:
            dy = 1
            self.facing = "down"
        elif key == arcade.key.LEFT:
            dx = -1
            self.facing = "left"
        elif key == arcade.key.RIGHT:
            dx = 1
            self.facing = "right"
        else:
            return

        # aplicar orientación
        self._apply_facing()

        # mover si es válido
        target_cx = self.player.cell_x + dx
        target_cy = self.player.cell_y + dy

        if 0 <= target_cx < self.game_map.width and 0 <= target_cy < self.game_map.height:
            if self.game_map.is_walkable(target_cx, target_cy):
                self.player.request_move_to_cell(target_cx, target_cy)
            else:
                print("Bloqueado por:", self.game_map.grid[target_cy][target_cx])


def main() -> None:
    api = ApiClient()
    state = init_game_state(api)   # Devuelve GameState ya preparado
    window: Window = arcade.Window(SCREEN_SIZE, SCREEN_SIZE, "Courier Quest")
    view = MapPlayerView(state)
    window.show_view(view)
    arcade.run()


if __name__ == "__main__":
    main()