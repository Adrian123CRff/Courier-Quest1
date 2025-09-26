# game_window.py
import arcade
from arcade import Window, View, Text
from run_api.api_client import ApiClient
from run_api.state_initializer import init_game_state
from map_manager import GameMap, FLIP_Y
from game.player_manager import Player

SCREEN_SIZE = 800
TILE_SIZE = 24

class MapPlayerView(View):
    def __init__(self, state) -> None:
        super().__init__()
        self.state = state
        self.game_map = GameMap(state.city_map if getattr(state, "city_map", None) else {})
        rows = len(self.game_map.grid)
        cols = len(self.game_map.grid[0]) if rows > 0 else 0

        start_cx = cols // 2
        start_cy = rows // 2
        self.player: Player = Player((start_cx, start_cy), TILE_SIZE, rows, flip_y=FLIP_Y)

        self.pos_text: Text = Text(
            f"Pos cell: ({self.player.cell_x},{self.player.cell_y})",
            10, SCREEN_SIZE - 20,
            arcade.color.WHITE,
            14
        )

    def on_show(self) -> None:
        arcade.set_background_color(arcade.color.DARK_SLATE_GRAY)

    def on_draw(self) -> None:
        self.clear()
        # Dibujar mapa (modo debug)
        self.game_map.draw_debug(tile_size=TILE_SIZE, draw_grid_lines=True)
        # Dibujar jugador con SpriteList
        self.player.draw()
        # HUD dinámico
        self.pos_text.text = f"Pos cell: ({self.player.cell_x},{self.player.cell_y})"
        self.pos_text.draw()

    def on_update(self, dt: float) -> None:
        self.player.update(dt)

    def on_key_press(self, key: int, modifiers: int) -> None:
        dx, dy = 0, 0
        if key == arcade.key.UP: dy = 1
        elif key == arcade.key.DOWN: dy = -1
        elif key == arcade.key.LEFT: dx = -1
        elif key == arcade.key.RIGHT: dx = 1
        else: return

        target_cx = self.player.cell_x + dx
        target_cy = self.player.cell_y + dy

        if 0 <= target_cx < self.game_map.width and 0 <= target_cy < self.game_map.height:
            if self.game_map.is_walkable(target_cx, target_cy):
                self.player.request_move_to_cell(target_cx, target_cy)
            else:
                print("Bloqueado por:", self.game_map.grid[target_cy][target_cx])

def main() -> None:
    api = ApiClient()
    state = init_game_state(api)
    window: Window = arcade.Window(SCREEN_SIZE, SCREEN_SIZE, "Test Mapa con Player")
    view = MapPlayerView(state)
    window.show_view(view)
    arcade.run()

if __name__ == "__main__":
    main()
