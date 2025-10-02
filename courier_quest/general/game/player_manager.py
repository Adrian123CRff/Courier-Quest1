# game/player_manager.py
import os
from typing import Tuple, Optional, Any

import arcade

# Velocidad base en celdas/segundo (ajustable)
CELLS_PER_SEC = 9.0

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
RESOURCE_PATH = os.path.join(BASE_PATH, "..", "..", "resources", "icons", "ciclista.png")
RESOURCE_PATH = os.path.normpath(RESOURCE_PATH)


class Player:
    def __init__(self, start_cell: Tuple[int, int], tile_size: int, map_rows: int, flip_y: bool = True):
        self.cell_x: int = int(start_cell[0])
        self.cell_y: int = int(start_cell[1])
        self.tile_size: int = int(tile_size)
        self.map_rows: int = int(map_rows)
        self.flip_y: bool = bool(flip_y)

        self.pixel_x, self.pixel_y = self.cell_to_pixel(self.cell_x, self.cell_y)
        self.target_pixel_x, self.target_pixel_y = self.pixel_x, self.pixel_y

        self.moving: bool = False

        # referencia a PlayerStats (si la enlazan desde MapPlayerView)
        self.bound_stats: Optional[Any] = None

        # velocidad base (celdas/segundo)
        self.base_cells_per_sec = float(CELLS_PER_SEC)

        # cargar textura (single load por instancia)
        try:
            tex = arcade.load_texture(RESOURCE_PATH)
        except Exception:
            tex = arcade.Sprite().texture
        self.texture = tex

        # Escalar para que quepa EN UNA celda con un pequeño padding
        if getattr(self.texture, "width", 0) and getattr(self.texture, "height", 0):
            scale_x = self.tile_size / float(self.texture.width)
            scale_y = self.tile_size / float(self.texture.height)
            self._sprite_base_scale = min(scale_x, scale_y) * 0.9  # 90% del tile para padding
        else:
            self._sprite_base_scale = 1.0

        self.sprite = arcade.Sprite(self.texture, scale=self._sprite_base_scale,
                                    center_x=self.pixel_x, center_y=self.pixel_y)
        self.sprite_list = arcade.SpriteList()
        self.sprite_list.append(self.sprite)

    def cell_to_pixel(self, cx: int, cy: int) -> Tuple[float, float]:
        px = (cx + 0.5) * self.tile_size
        py = (self.map_rows - cy - 0.5) * self.tile_size if self.flip_y else (cy + 0.5) * self.tile_size
        return px, py

    def bind_stats(self, stats_obj: Any):
        """Enlaza objeto PlayerStats para consumo por celda y chequeos."""
        self.bound_stats = stats_obj

    def request_move_to_cell(self, cx: int, cy: int) -> None:
        """Inicia movimiento suave hacia el centro de la celda (no actualiza cell_x hasta llegar)."""
        self.target_pixel_x, self.target_pixel_y = self.cell_to_pixel(cx, cy)
        self.moving = True

    def move_by(self, dx: int, dy: int, game_map) -> bool:
        """Movimiento por input: intenta moverse una celda. Retorna True si aceptado."""
        tx = self.cell_x + dx
        ty = self.cell_y + dy
        if not (0 <= tx < game_map.width and 0 <= ty < game_map.height):
            return False

        # Verificar stamina (si hay stats enlazados)
        try:
            if self.bound_stats and getattr(self.bound_stats, "stamina", 0.0) <= 0.0:
                # Bloqueado únicamente si stamina == 0
                return False
        except Exception:
            pass

        if not game_map.is_walkable(tx, ty):
            return False

        # iniciar movimiento hacia la celda
        self.request_move_to_cell(tx, ty)
        return True

    def _get_climate_penalty_value(self, weather_cond: str) -> float:
        """Valor numérico de penalización por clima usado al consumir stamina por celda."""
        if weather_cond in ["rain", "wind"]:
            return 0.1
        if weather_cond == "storm":
            return 0.3
        if weather_cond == "heat":
            return 0.2
        return 0.0

    def update(self, dt: float, player_stats: Any = None, weather_system: Any = None, inventory: Any = None) -> None:
        """
        Actualiza la posición (moviéndose hacia target). Al llegar al centro de la celda
        consume stamina POR CELDA completada llamando a player_stats.consume_stamina(...).
        """
        if not self.moving:
            # mantener sprite centrado
            self.sprite.center_x = self.pixel_x
            self.sprite.center_y = self.pixel_y
            return

        stats = player_stats or self.bound_stats

        # impedir movimiento si stamina == 0 (por seguridad, si comenzó a moverse pero quedó sin stamina)
        try:
            if stats and getattr(stats, "stamina", 1.0) <= 0.0:
                self.moving = False
                return
        except Exception:
            pass

        # velocidad en píxeles/seg
        pixels_per_sec = self.base_cells_per_sec * self.tile_size

        # multiplicador climático (si weather_system es WeatherMarkov)
        climate_mul = 1.0
        try:
            if weather_system is not None:
                if hasattr(weather_system, "current_multiplier"):
                    climate_mul = float(weather_system.current_multiplier)
                elif hasattr(weather_system, "get_state"):
                    climate_mul = float(weather_system.get_state().get("multiplier", 1.0))
        except Exception:
            climate_mul = 1.0

        # multiplicador por stamina
        stamina_mul = 1.0
        try:
            if stats and hasattr(stats, "get_speed_multiplier"):
                stamina_mul = float(stats.get_speed_multiplier())
        except Exception:
            stamina_mul = 1.0

        # multiplicador por peso del inventario
        weight_mul = 1.0
        try:
            weight = float(getattr(inventory, "current_weight", 0.0)) if inventory is not None else 0.0
            weight_mul = max(0.7, 1.0 - 0.03 * weight)
        except Exception:
            weight_mul = 1.0

        final_speed = pixels_per_sec * climate_mul * stamina_mul * weight_mul

        # desplazar hacia target
        dx = self.target_pixel_x - self.pixel_x
        dy = self.target_pixel_y - self.pixel_y
        dist = (dx * dx + dy * dy) ** 0.5

        if dist <= 0.6:
            # llegada a celda
            self.pixel_x = self.target_pixel_x
            self.pixel_y = self.target_pixel_y

            # determinar nueva celda lógica (más robusto)
            new_cx = int(self.pixel_x // self.tile_size)
            new_cy = int((self.map_rows * self.tile_size - self.pixel_y) // self.tile_size) if self.flip_y else int(self.pixel_y // self.tile_size)
            # asegurar dentro de bounds
            new_cx = max(0, min(new_cx, self.map_rows - 1))
            new_cy = max(0, min(new_cy, self.map_rows - 1))
            self.cell_x, self.cell_y = new_cx, new_cy

            self.moving = False

            # Consumir stamina POR CELDA completada (si stats enlazados)
            try:
                if stats and hasattr(stats, "consume_stamina"):
                    base_cost = 0.5  # <--- consumo por celda solicitado
                    weight_val = float(getattr(inventory, "current_weight", 0.0)) if inventory is not None else 0.0

                    # clima string
                    current_weather = "clear"
                    try:
                        if weather_system is not None and hasattr(weather_system, "current_condition"):
                            current_weather = weather_system.current_condition
                        elif weather_system is not None and hasattr(weather_system, "get_state"):
                            current_weather = weather_system.get_state().get("condition", "clear")
                    except Exception:
                        current_weather = "clear"

                    weather_penalty = self._get_climate_penalty_value(current_weather or "clear")

                    # consume_stamina espera (base_cost, weight, weather_penalty) — coincide con PlayerStats.consume_stamina
                    stats.consume_stamina(base_cost, weight_val, weather_penalty)
            except Exception:
                pass
        else:
            # mover
            move_dist = min(dist, final_speed * dt)
            # evitar división por cero
            if dist > 0:
                self.pixel_x += (dx / dist) * move_dist
                self.pixel_y += (dy / dist) * move_dist

        # actualizar sprite
        self.sprite.center_x = self.pixel_x
        self.sprite.center_y = self.pixel_y

    def draw(self) -> None:
        if hasattr(self, "sprite_list") and self.sprite_list:
            self.sprite_list.draw()
        else:
            r = max(4, self.tile_size * 0.35)
            arcade.draw_circle_filled(self.pixel_x, self.pixel_y, r, arcade.color.AUBURN)
            arcade.draw_circle_outline(self.pixel_x, self.pixel_y, r, arcade.color.BLACK, 2)
