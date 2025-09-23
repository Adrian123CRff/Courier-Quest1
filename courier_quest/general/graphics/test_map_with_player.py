# test_map_with_player.py
import arcade
from run_api.api_client import ApiClient
from run_api.state_initializer import init_game_state
from map_manager import GameMap, FLIP_Y
from game.player_manager import Player

SCREEN_SIZE = 800
TILE_SIZE = 24  # ajustar si quieres más grande/pequeño

class MapPlayerView(arcade.View):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.game_map = GameMap(state.city_map if getattr(state, "city_map", None) else {})
        rows = len(self.game_map.grid)
        cols = len(self.game_map.grid[0]) if rows>0 else 0

        # Crear jugador en centro aprox
        start_cx = cols // 2
        start_cy = rows // 2
        self.player = Player((start_cx, start_cy), TILE_SIZE, rows, flip_y=FLIP_Y)

        # cámara (opcional)
        #self.camera = arcade.Camera(SCREEN_SIZE, SCREEN_SIZE)

    def on_show(self):
        arcade.set_background_color(arcade.color.DARK_SLATE_GRAY)

    def on_draw(self):
        self.clear()
        # dibujar mapa
        self.game_map.draw_debug(tile_size=TILE_SIZE, draw_grid_lines=True)
        # dibujar player
        self.player.draw()
        # HUD
        arcade.draw_text(f"Pos cell: ({self.player.cell_x},{self.player.cell_y})", 10, SCREEN_SIZE - 20, arcade.color.WHITE, 14)

    def on_update(self, dt: float):
        self.player.update(dt)
        # opcional: centrar cámara en player
        # self.camera.move_to((self.player.pixel_x - SCREEN_SIZE/2, self.player.pixel_y - SCREEN_SIZE/2))
        # self.camera.use()

    def on_key_press(self, key, modifiers):
        # Movimiento por teclas (4 direcciones)
        dx, dy = 0, 0
        if key == arcade.key.UP:
            dy = 1
        elif key == arcade.key.DOWN:
            dy = -1
        elif key == arcade.key.LEFT:
            dx = -1
        elif key == arcade.key.RIGHT:
            dx = 1
        else:
            return

        # calcular destino según convención de celdas
        target_cx = self.player.cell_x + dx
        target_cy = self.player.cell_y + dy

        # comprobar límites y colisión con map
        if 0 <= target_cx < self.game_map.width and 0 <= target_cy < self.game_map.height:
            if self.game_map.is_walkable(target_cx, target_cy):
                # solicitar movimiento suave
                self.player.request_move_to_cell(target_cx, target_cy)
            else:
                # feedback: sonido o flash (opcional)
                print("Bloqueado por:", self.game_map.grid[target_cy][target_cx])

def main():
    api = ApiClient()
    state = init_game_state(api)
    window = arcade.Window(SCREEN_SIZE, SCREEN_SIZE, "Test Mapa con Player")
    view = MapPlayerView(state)
    window.show_view(view)
    arcade.run()

if __name__ == "__main__":
    main()
