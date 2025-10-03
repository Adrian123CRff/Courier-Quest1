# general/graphics/game_window.py
import time
import arcade
from arcade import Window, View, Text
from run_api.api_client import APIDataManager
from run_api.state_initializer import init_game_state
from .map_manager import GameMap, FLIP_Y
from game.player_manager import Player
from game.player_stats import PlayerStats
from graphics.weather_markov import WeatherMarkov
from graphics.weather_renderer import WeatherRenderer

SCREEN_SIZE = 800
TILE_SIZE = 24


# Helper drawing compatibles con diferentes versiones de arcade:
def _draw_rect_lrbt_filled(left: float, right: float, bottom: float, top: float, color):
    pts = [(left, bottom), (right, bottom), (right, top), (left, top)]
    arcade.draw_polygon_filled(pts, color)


def _draw_rect_lrbt_outline(left: float, right: float, bottom: float, top: float, color, border_width=2):
    pts = [(left, bottom), (right, bottom), (right, top), (left, top)]
    arcade.draw_polygon_outline(pts, color, border_width)


class MapPlayerView(View):
    def __init__(self, state) -> None:
        super().__init__()
        self.state = state or {}

        # asegurar player_stats
        if isinstance(self.state, dict):
            if "player_stats" not in self.state or self.state.get("player_stats") is None:
                self.state["player_stats"] = PlayerStats()
            self.player_stats = self.state["player_stats"]
        else:
            self.player_stats = getattr(self.state, "player_stats", None) or PlayerStats()

        cm = self.state["city_map"] if isinstance(self.state, dict) else getattr(self.state, "city_map", {})
        self.game_map = GameMap(cm)

        rows = len(self.game_map.grid)
        cols = len(self.game_map.grid[0]) if rows > 0 else 0

        start_cx = cols // 2
        start_cy = rows // 2
        self.player: Player = Player((start_cx, start_cy), TILE_SIZE, rows, flip_y=FLIP_Y)

        # bind stats si Player lo soporta
        try:
            self.player.bind_stats(self.player_stats)
        except Exception:
            self.player.bound_stats = self.player_stats

        # ajustar escala del sprite para que quepa en 1 tile
        try:
            tex = getattr(self.player, "texture", None)
            spr = getattr(self.player, "sprite", None)
            if tex is not None and spr is not None:
                max_dim = max(tex.width or 1, tex.height or 1)
                scale = (TILE_SIZE * 0.9) / max_dim
                spr.scale = scale
                self.player._sprite_base_scale = scale
        except Exception:
            pass

        self.base_scale = getattr(self.player, "_sprite_base_scale", 1.0)
        # initial facing: sprite image apunta hacia ARRIBA (norte)
        self.facing = "up"

        self.pos_text = Text("", 10, SCREEN_SIZE - 20, arcade.color.WHITE, 14)
        self.weather_text = Text("", 10, SCREEN_SIZE - 40, arcade.color.LIGHT_BLUE, 14)
        self.stamina_text = Text("", 0, 0, arcade.color.WHITE, 12)

        self.weather_markov = WeatherMarkov(api=APIDataManager())
        self.weather_renderer = WeatherRenderer(self)

        self._last_input_time = 0.0
        self.INPUT_ACTIVE_WINDOW = 0.25

    def on_show(self) -> None:
        arcade.set_background_color(arcade.color.DARK_SLATE_GRAY)

    def on_draw(self) -> None:
        self.clear()
        self.game_map.draw_debug(tile_size=TILE_SIZE, draw_grid_lines=True)
        self.player.draw()

        self.pos_text.text = f"Pos cell: ({self.player.cell_x},{self.player.cell_y})"
        self.pos_text.draw()

        # stamina bar abajo-derecha
        stamina_val = getattr(self.player_stats, "stamina", 100.0)
        bar_w, bar_h = 140, 14
        pad = 12
        right = self.window.width - pad
        bottom = pad
        left = right - bar_w
        top = bottom + bar_h

        # fondo y fill usando helpers (compatibilidad arcade 3.3.2)
        _draw_rect_lrbt_filled(left, right, bottom, top, arcade.color.DARK_SLATE_GRAY)
        pct = max(0.0, min(1.0, stamina_val / 100.0))
        if pct > 0.0:
            fill_right = left + (bar_w * pct)
            _draw_rect_lrbt_filled(left, fill_right, bottom, top - (bar_h * 0.05), arcade.color.AMAZON)

        _draw_rect_lrbt_outline(left, right, bottom, top, arcade.color.BLACK, 2)

        self.stamina_text.position = (left + bar_w / 2, bottom + 2)
        self.stamina_text.text = f"{int(stamina_val)}%"
        self.stamina_text.font_size = 12
        self.stamina_text.color = arcade.color.WHITE
        self.stamina_text.draw()

        # clima
        ws = self.state.get("weather_state", {}) if isinstance(self.state, dict) else getattr(self.state, "weather_state", {})
        cond = ws.get("condition", "?")
        intensity = ws.get("intensity", "?")
        self.weather_text.text = f"Clima: {cond} (int={intensity})"
        self.weather_text.draw()

        # renderer (nieve/lluvia/viento/niebla)
        self.weather_renderer.draw()

    def on_update(self, dt: float) -> None:
        # input activo
        input_active = (time.time() - self._last_input_time) < self.INPUT_ACTIVE_WINDOW

        inventory = self.state.get("inventory", None) if isinstance(self.state, dict) else getattr(self.state, "inventory", None)

        was_moving = bool(self.player.moving)

        # actualizar jugador (trata de pasar stats si Player.update lo acepta)
        try:
            self.player.update(dt, player_stats=self.player_stats, weather_system=self.weather_markov, inventory=inventory)
        except TypeError:
            self.player.update(dt)

        # Si completó movimiento (was_moving True -> ahora False): consumir stamina por CELDA
        if was_moving and not self.player.moving:
            weight = float(getattr(inventory, "current_weight", 0.0)) if inventory is not None else 0.0
            current_weather = getattr(self.weather_markov, "current_condition", "clear")

            weather_penalty = 0.0
            if current_weather in ["rain", "wind"]:
                weather_penalty = 0.1
            elif current_weather == "storm":
                weather_penalty = 0.3
            elif current_weather == "heat":
                weather_penalty = 0.2
            elif current_weather == "snow":
                weather_penalty = 0.15
            elif current_weather == "fog":
                weather_penalty = 0.05

            base_cost = 1.0
            if hasattr(self.player_stats, "consume_stamina"):
                ok = self.player_stats.consume_stamina(base_cost, weight, weather_penalty)
                if not ok:
                    print("[INFO] Resistencia agotada tras moverse.")

        # actualizar player_stats (recover si está quieto y no hay input)
        try:
            self.player_stats.update(
                dt,
                bool(self.player.moving),
                getattr(self, "at_rest_point", False),
                float(getattr(inventory, "current_weight", 0.0)) if inventory is not None else 0.0,
                getattr(self.weather_markov, "current_condition", "clear"),
                input_active=input_active
            )
        except Exception:
            pass

        # clima
        self.weather_markov.update(dt)
        self.weather_markov.apply_to_game_state(self.state)
        ws = self.state.get("weather_state", {}) if isinstance(self.state, dict) else getattr(self.state, "weather_state", {})
        self.weather_renderer.update(dt, ws)

    def _apply_facing(self):
        """Ajusta la rotación del sprite según self.facing.
        NOTA: la textura por defecto apunta hacia ARRIBA (north).
        Map:
            up    -> angle = 0
            right -> angle = +90   (ajustado para invertir rotación previa)
            down  -> angle = 180
            left  -> angle = -90
        """
        if not hasattr(self.player, "sprite"):
            return
        spr = self.player.sprite
        mag = getattr(self.player, "_sprite_base_scale", getattr(spr, "scale", 1.0))
        try:
            spr.scale = mag
        except Exception:
            try:
                spr.scale_x = mag
                spr.scale_y = mag
            except Exception:
                pass

        if self.facing == "up":
            spr.angle = 0
        elif self.facing == "right":
            spr.angle = 90
        elif self.facing == "down":
            spr.angle = 180
        elif self.facing == "left":
            spr.angle = -90

    # ---------------- Input ----------------
    def on_key_press(self, key: int, modifiers: int) -> None:
        self._last_input_time = time.time()

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

        self._apply_facing()

        # bloquear movimiento si exhausto
        try:
            if hasattr(self.player, "bound_stats") and self.player.bound_stats is not None:
                st_state = self.player.bound_stats.get_stamina_state() if hasattr(self.player.bound_stats, "get_stamina_state") else None
                if st_state == "exhausted":
                    print("[INFO] No puedes moverte: resistencia agotada.")
                    return
        except Exception:
            pass

        moved = self.player.move_by(dx, dy, self.game_map)
        if not moved:
            print("Bloqueado por:", "colisión o fuera de límites")
