#!/usr/bin/env python3
import arcade
from arcade import Window, View
from run_api.api_client import ApiClient
from run_api.state_initializer import init_game_state
from .map_manager import GameMap, FLIP_Y
from game.player_manager import Player
import time

# Importaciones condicionales
try:
    from graphics.weather_markov import WeatherMarkov
    from graphics.weather_renderer import WeatherRenderer
except ImportError:
    class WeatherMarkov:
        def __init__(self, api=None): pass

        def update(self, dt): pass

        def apply_to_game_state(self, state): pass


    class WeatherRenderer:
        def __init__(self, view): pass

        def update(self, dt, weather_state): pass

        def draw(self): pass

SCREEN_SIZE = 800
TILE_SIZE = 24


class MapPlayerView(View):
    def __init__(self, state):
        super().__init__()
        self.state = state

        # Inicializar mapa
        self.game_map = GameMap(self.state.city_map)
        rows = len(self.game_map.grid)
        cols = len(self.game_map.grid[0]) if rows > 0 else 0

        # Posición inicial
        start_cx = cols // 2
        start_cy = rows // 2

        # Jugador
        self.player = Player((start_cx, start_cy), TILE_SIZE, rows, flip_y=FLIP_Y)

        # SIN DELAY - Movimiento inmediato
        self.facing = "right"
        self.base_scale = 1.0

        # Sistemas de clima
        self.weather_markov = WeatherMarkov(api=ApiClient())
        self.weather_renderer = WeatherRenderer(self)

        # Estado del juego
        self.job_manager = None
        self.player_state = state
        self._messages = []
        self.inventory_visible = False

    def on_show_view(self):
        arcade.set_background_color(arcade.color.DARK_SLATE_GRAY)

    def on_draw(self):
        self.clear()

        # Dibujar mapa
        try:
            self.game_map.draw_debug(tile_size=TILE_SIZE, draw_grid_lines=True)
        except Exception as e:
            print(f"Error dibujando mapa: {e}")

        # Dibujar jugador
        try:
            self.player.draw()
        except Exception as e:
            print(f"Error dibujando jugador: {e}")

        # Dibujar HUD
        self._draw_hud()

        # Dibujar mensajes
        self._draw_messages()

        # Dibujar inventario si está visible
        if self.inventory_visible:
            self._draw_inventory()

    def _draw_hud(self):
        """Dibuja la interfaz de usuario"""
        # Posición
        arcade.draw_text(
            f"Pos: ({self.player.cell_x},{self.player.cell_y})",
            10, SCREEN_SIZE - 20,
            arcade.color.WHITE, 14
        )

        # Clima
        weather_condition = "clear"
        if hasattr(self.state, 'weather_state'):
            weather_condition = self.state.weather_state.get('condition', 'clear')

        arcade.draw_text(
            f"Clima: {weather_condition}",
            10, SCREEN_SIZE - 40,
            arcade.color.LIGHT_BLUE, 14
        )

        # Stats del jugador
        stamina = getattr(self.state, 'stamina', 100)
        reputation = getattr(self.state, 'reputation', 50)
        money = getattr(self.state, 'money', 0)

        arcade.draw_text(
            f"Stamina: {stamina:.0f} | Rep: {reputation:.0f} | Dinero: ${money:.0f}",
            10, SCREEN_SIZE - 60,
            arcade.color.YELLOW, 14
        )

    def _draw_messages(self):
        """Dibuja mensajes temporales"""
        if not hasattr(self, '_messages'):
            return

        now = time.time()
        self._messages = [(msg, expiry) for msg, expiry in self._messages if expiry > now]

        y_pos = SCREEN_SIZE - 100
        for msg, expiry in self._messages:
            arcade.draw_text(msg, 10, y_pos, arcade.color.WHITE, 14)
            y_pos -= 20

    def _draw_inventory(self):
        """Dibuja el inventario"""
        panel_width, panel_height = 300, 200
        x, y = 50, SCREEN_SIZE - panel_height - 50

        # Fondo del panel
        arcade.draw_rectangle_filled(
            x + panel_width // 2,
            y + panel_height // 2,
            panel_width, panel_height,
            arcade.color.DARK_SLATE_GRAY
        )

        # Borde
        arcade.draw_rectangle_outline(
            x + panel_width // 2,
            y + panel_height // 2,
            panel_width, panel_height,
            arcade.color.WHITE, 2
        )

        # Título
        arcade.draw_text(
            "Inventario (I para cerrar)",
            x + 10, y + panel_height - 30,
            arcade.color.WHITE, 16
        )

        # Contenido del inventario
        inventory = getattr(self.state, 'inventory', [])
        if not inventory:
            arcade.draw_text(
                "Inventario vacío",
                x + 10, y + panel_height - 60,
                arcade.color.LIGHT_GRAY, 14
            )
        else:
            for i, item in enumerate(inventory[:8]):
                item_text = f"{i + 1}. {str(item)}"
                arcade.draw_text(
                    item_text,
                    x + 10, y + panel_height - 60 - (i * 20),
                    arcade.color.WHITE, 12
                )

    def on_update(self, delta_time):
        """Actualiza la lógica del juego"""
        # Actualizar jugador
        try:
            self.player.update(delta_time)
        except Exception as e:
            print(f"Error actualizando jugador: {e}")

        # Actualizar clima
        try:
            self.weather_markov.update(delta_time)
            self.weather_markov.apply_to_game_state(self.state)
            self.weather_renderer.update(delta_time, getattr(self.state, 'weather_state', {}))
        except Exception as e:
            print(f"Error actualizando clima: {e}")

    def on_key_press(self, key, modifiers):
        """Maneja las teclas presionadas - SIN DELAY"""
        # Tecla I para inventario
        if key == arcade.key.I:
            self.inventory_visible = not self.inventory_visible
            return

        # Movimiento - SIN VERIFICACIÓN DE COOLDOWN
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

        # Aplicar movimiento inmediatamente
        self._apply_movement(dx, dy)

    def _apply_movement(self, dx, dy):
        """Aplica el movimiento del jugador - SIN DELAY"""
        target_x = self.player.cell_x + dx
        target_y = self.player.cell_y + dy

        # Verificar límites del mapa
        if not (0 <= target_x < self.game_map.width and 0 <= target_y < self.game_map.height):
            return

        # Verificar si la celda es transitable
        if not self.game_map.is_walkable(target_x, target_y):
            return

        # Mover jugador inmediatamente
        try:
            self.player.request_move_to_cell(target_x, target_y)

            # Aplicar dirección
            self._apply_facing()

            # Procesar eventos de la celda
            self._handle_cell_events(target_x, target_y)

        except Exception as e:
            print(f"Error en movimiento: {e}")

    def _apply_facing(self):
        """Aplica la dirección del sprite del jugador"""
        if not hasattr(self.player, 'sprite'):
            return

        try:
            if self.facing == "right":
                self.player.sprite.angle = 0
                self.player.sprite.scale_x = -abs(self.player.sprite.scale_x)
            elif self.facing == "left":
                self.player.sprite.angle = 0
                self.player.sprite.scale_x = abs(self.player.sprite.scale_x)
            elif self.facing == "up":
                self.player.sprite.angle = 90
            elif self.facing == "down":
                self.player.sprite.angle = 270
        except Exception as e:
            print(f"Error aplicando dirección: {e}")

    def _handle_cell_events(self, x, y):
        """Maneja los eventos cuando el jugador entra a una celda"""
        # Aquí puedes agregar lógica para recoger paquetes, entregas, etc.
        message = f"Movido a: ({x}, {y})"
        self._show_message(message, 2.0)

    def _show_message(self, text, duration=3.0):
        """Muestra un mensaje temporal"""
        if not hasattr(self, '_messages'):
            self._messages = []
        expiry = time.time() + duration
        self._messages.append((text, expiry))


def main():
    """Función principal"""
    window = Window(SCREEN_SIZE, SCREEN_SIZE, "Courier Quest")

    # Inicializar estado del juego
    api = ApiClient()
    state = init_game_state(api)

    # Crear y mostrar vista
    game_view = MapPlayerView(state)
    window.show_view(game_view)

    arcade.run()


if __name__ == "__main__":
    main()