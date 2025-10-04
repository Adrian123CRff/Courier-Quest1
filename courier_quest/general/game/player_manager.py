# player_manager.py (PARCHE COMPLETO)
import arcade
import os
from typing import Tuple, Optional, Any

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

        # referencia a PlayerStats
        self.bound_stats: Optional[Any] = None

        # velocidad base (celdas/segundo) - según PDF v0 = 3 celdas/seg
        self.base_cells_per_sec = 3.0

        # cargar textura
        try:
            tex = arcade.load_texture(RESOURCE_PATH)
        except Exception:
            # Fallback si no encuentra la textura
            tex = arcade.Sprite().texture
        self.texture = tex

        # Escalar para que quepa en una celda
        if getattr(self.texture, "width", 0) and getattr(self.texture, "height", 0):
            scale_x = self.tile_size / float(self.texture.width)
            scale_y = self.tile_size / float(self.texture.height)
            self._sprite_base_scale = min(scale_x, scale_y) * 0.9
        else:
            self._sprite_base_scale = 1.0

        self.sprite = arcade.Sprite(self.texture, scale=self._sprite_base_scale,
                                    center_x=self.pixel_x, center_y=self.pixel_y)
        self.sprite_list = arcade.SpriteList()
        self.sprite_list.append(self.sprite)

    def cell_to_pixel(self, cx: int, cy: int) -> Tuple[float, float]:
        """Convierte coordenadas de celda a píxeles."""
        px = (cx + 0.5) * self.tile_size
        if self.flip_y:
            py = (self.map_rows - cy - 0.5) * self.tile_size
        else:
            py = (cy + 0.5) * self.tile_size
        return px, py

    def bind_stats(self, stats_obj: Any):
        """Enlaza objeto PlayerStats."""
        self.bound_stats = stats_obj

    def request_move_to_cell(self, cx: int, cy: int) -> None:
        """Inicia movimiento suave hacia el centro de la celda."""
        self.target_pixel_x, self.target_pixel_y = self.cell_to_pixel(cx, cy)
        self.moving = True

    def move_by(self, dx: int, dy: int, game_map) -> bool:
        """Movimiento por input: intenta moverse una celda. Retorna True si aceptado."""
        tx = self.cell_x + dx
        ty = self.cell_y + dy

        # Verificar límites del mapa
        if not (0 <= tx < game_map.width and 0 <= ty < game_map.height):
            return False

        # Verificar stamina
        try:
            if self.bound_stats and getattr(self.bound_stats, "stamina", 0.0) <= 0.0:
                return False
        except Exception:
            pass

        # Verificar si la celda es transitable
        if not game_map.is_walkable(tx, ty):
            return False

        # Iniciar movimiento
        self.request_move_to_cell(tx, ty)
        return True
    @staticmethod
    def _get_climate_penalty_value(self, weather_cond: str) -> float:
        """Valor numérico de penalización por clima para consumo de stamina."""
        if weather_cond in ["rain", "wind"]:
            return 0.1
        if weather_cond == "storm":
            return 0.3
        if weather_cond == "heat":
            return 0.2
        return 0.0
    @staticmethod
    def _get_surface_multiplier(self, game_map, x: int, y: int) -> float:
        """Obtiene el multiplicador de superficie según el tipo de tile."""
        try:
            if hasattr(game_map, 'get_tile_surface_weight'):
                return game_map.get_tile_surface_weight(x, y)
            elif hasattr(game_map, 'tiles') and hasattr(game_map, 'legend'):
                # Lógica alternativa si existe la estructura de datos
                tile_type = game_map.tiles[y][x]
                legend_entry = game_map.legend.get(tile_type, {})
                return legend_entry.get('surface_weight', 1.0)
        except Exception:
            pass
        return 1.0

    def update(self, dt: float, player_state: Any = None, game_map: Any = None) -> None:
        """
        Actualiza la posición del jugador aplicando TODOS los multiplicadores de velocidad.
        """
        if not self.moving:
            self.sprite.center_x = self.pixel_x
            self.sprite.center_y = self.pixel_y
            return

        stats = getattr(player_state, 'player_stats', None) if player_state else self.bound_stats

        # Verificar stamina
        try:
            if stats and getattr(stats, "stamina", 1.0) <= 0.0:
                self.moving = False
                return
        except Exception:
            pass

        # 1. Velocidad base en píxeles/segundo
        pixels_per_sec = self.base_cells_per_sec * self.tile_size

        # 2. Multiplicador climático desde WeatherMarkov
        climate_mul = 1.0
        try:
            if player_state and hasattr(player_state, 'weather_multiplier'):
                climate_mul = float(player_state.weather_multiplier)
            elif player_state and hasattr(player_state, 'weather_system'):
                weather_state = player_state.weather_system.get_state()
                climate_mul = float(weather_state.get('multiplier', 1.0))
        except Exception:
            climate_mul = 1.0

        # 3. Multiplicador por stamina
        stamina_mul = 1.0
        try:
            if stats and hasattr(stats, "get_speed_multiplier"):
                stamina_mul = float(stats.get_speed_multiplier())
        except Exception:
            stamina_mul = 1.0

        # 4. Multiplicador por peso del inventario
        weight_mul = 1.0
        try:
            inventory = getattr(player_state, 'inventory', None)
            weight = float(getattr(inventory, "current_weight", 0.0)) if inventory else 0.0
            weight_mul = max(0.8, 1.0 - 0.03 * weight)  # Según PDF
        except Exception:
            weight_mul = 1.0

        # 5. Multiplicador por reputación
        reputation_mul = 1.0
        try:
            if stats and hasattr(stats, "reputation"):
                reputation = float(stats.reputation)
                reputation_mul = 1.03 if reputation >= 90 else 1.0  # +5% si reputación ≥90
        except Exception:
            reputation_mul = 1.0

        # 6. Multiplicador por superficie (tipo de tile)
        surface_mul = 1.0
        try:
            if game_map:
                surface_mul = self._get_surface_multiplier(game_map, self.cell_x, self.cell_y)
        except Exception:
            surface_mul = 1.0

        # ✅ APLICAR TODOS LOS MULTIPLICADORES según fórmula del PDF
        final_speed = (
                pixels_per_sec *
                climate_mul *
                stamina_mul *
                weight_mul *
                reputation_mul *
                surface_mul
        )

        # Movimiento hacia el target
        dx = self.target_pixel_x - self.pixel_x
        dy = self.target_pixel_y - self.pixel_y
        dist = (dx * dx + dy * dy) ** 0.5

        if dist <= 0.6:  # Llegada a la celda
            self.pixel_x = self.target_pixel_x
            self.pixel_y = self.target_pixel_y

            # Actualizar posición lógica
            new_cx = int(self.pixel_x // self.tile_size)
            if self.flip_y:
                new_cy = int((self.map_rows * self.tile_size - self.pixel_y) // self.tile_size)
            else:
                new_cy = int(self.pixel_y // self.tile_size)

            # Asegurar dentro de bounds
            new_cx = max(0, min(new_cx, getattr(game_map, 'width', self.map_rows) - 1))
            new_cy = max(0, min(new_cy, getattr(game_map, 'height', self.map_rows) - 1))
            self.cell_x, self.cell_y = new_cx, new_cy

            self.moving = False

            # ✅ CONSUMIR STAMINA POR CELDA COMPLETADA
            try:
                if stats and hasattr(stats, "consume_stamina"):
                    base_cost = 0.5  # Consumo base por celda según PDF

                    # Obtener peso actual
                    inventory = getattr(player_state, 'inventory', None)
                    weight_val = float(getattr(inventory, "current_weight", 0.0)) if inventory else 0.0

                    # Obtener condición climática actual
                    current_weather = "clear"
                    try:
                        if player_state and hasattr(player_state, 'current_weather_condition'):
                            current_weather = player_state.current_weather_condition
                        elif player_state and hasattr(player_state, 'weather_system'):
                            weather_state = player_state.weather_system.get_state()
                            current_weather = weather_state.get('condition', 'clear')
                    except Exception:
                        current_weather = "clear"

                    weather_penalty = self._get_climate_penalty_value(current_weather)

                    # Consumir stamina con todos los factores
                    stats.consume_stamina(base_cost, weight_val, current_weather)

            except Exception as e:
                print(f"Error consumiendo stamina: {e}")

        else:
            # Mover hacia el target
            move_dist = min(dist, final_speed * dt)
            if dist > 0:
                self.pixel_x += (dx / dist) * move_dist
                self.pixel_y += (dy / dist) * move_dist

        # Actualizar sprite
        self.sprite.center_x = self.pixel_x
        self.sprite.center_y = self.pixel_y

    def draw(self) -> None:
        """Dibuja al jugador."""
        if hasattr(self, "sprite_list") and self.sprite_list:
            self.sprite_list.draw()
        else:
            # Fallback: dibujar círculo si no hay sprite
            r = max(4, self.tile_size * 0.35)
            arcade.draw_circle_filled(self.pixel_x, self.pixel_y, r, arcade.color.AUBURN)
            arcade.draw_circle_outline(self.pixel_x, self.pixel_y, r, arcade.color.BLACK, 2)

    # Método auxiliar para debug
    def get_current_speed_factors(self, player_state: Any = None, game_map: Any = None) -> dict:
        """Retorna los factores de velocidad actuales para debug."""
        stats = getattr(player_state, 'player_stats', None) if player_state else self.bound_stats

        factors = {
            'base_speed': self.base_cells_per_sec,
            'climate_multiplier': 1.0,
            'stamina_multiplier': 1.0,
            'weight_multiplier': 1.0,
            'reputation_multiplier': 1.0,
            'surface_multiplier': 1.0,
            'final_speed': self.base_cells_per_sec
        }

        try:
            # Climate
            if player_state and hasattr(player_state, 'weather_multiplier'):
                factors['climate_multiplier'] = float(player_state.weather_multiplier)

            # Stamina
            if stats and hasattr(stats, "get_speed_multiplier"):
                factors['stamina_multiplier'] = float(stats.get_speed_multiplier())

            # Weight
            inventory = getattr(player_state, 'inventory', None)
            weight = float(getattr(inventory, "current_weight", 0.0)) if inventory else 0.0
            factors['weight_multiplier'] = max(0.8, 1.0 - 0.03 * weight)

            # Reputation
            if stats and hasattr(stats, "reputation"):
                reputation = float(stats.reputation)
                factors['reputation_multiplier'] = 1.03 if reputation >= 90 else 1.0

            # Surface
            if game_map:
                factors['surface_multiplier'] = self._get_surface_multiplier(game_map, self.cell_x, self.cell_y)

            # Final
            factors['final_speed'] = (
                    factors['base_speed'] *
                    factors['climate_multiplier'] *
                    factors['stamina_multiplier'] *
                    factors['weight_multiplier'] *
                    factors['reputation_multiplier'] *
                    factors['surface_multiplier']
            )

        except Exception:
            pass

        return factors