# player_manager.py

import arcade
from typing import Tuple, List
from game.coords import cell_to_pixel, pixel_to_cell

# Velocidad base en celdas/segundo según el PDF
CELLS_PER_SEC = 3.0  # Velocidad base en celdas/segundo según PDF
TILE_SIZE = 24.0  # Tamaño de celda en píxeles


class Player:
    def __init__(self, start_cell: Tuple[int, int], tile_size: int, map_rows: int, flip_y: bool = True):
        self.cell_x, self.cell_y = int(start_cell[0]), int(start_cell[1])
        self.tile_size = tile_size
        self.map_rows = map_rows
        self.flip_y = flip_y

        self.pixel_x, self.pixel_y = cell_to_pixel(self.cell_x, self.cell_y, self.tile_size, self.map_rows, self.flip_y)
        self.target_pixel_x, self.target_pixel_y = self.pixel_x, self.pixel_y

        self.moving = False
        self.radius = tile_size * 0.35
        self.color = arcade.color.AUBURN

        # Path following
        self.path: List[Tuple[int, int]] = []
        self.path_index = 0

        # base speed in cells/sec (will be converted to pixels/sec)
        self.base_cells_per_sec = CELLS_PER_SEC

    # ------------------ Movement primitives ------------------
    def teleport_to_cell(self, cx: int, cy: int):
        self.cell_x, self.cell_y = int(cx), int(cy)
        self.pixel_x, self.pixel_y = cell_to_pixel(cx, cy, self.tile_size, self.map_rows, self.flip_y)
        self.target_pixel_x, self.target_pixel_y = self.pixel_x, self.pixel_y
        self.moving = False
        self.path = []
        self.path_index = 0

    def request_move_to_cell(self, cx: int, cy: int):
        self.target_pixel_x, self.target_pixel_y = cell_to_pixel(cx, cy, self.tile_size, self.map_rows, self.flip_y)
        self.moving = True

    def set_path(self, path: List[Tuple[int, int]]):
        """Set a route (list of (x,y) cells). Player will follow it step-by-step."""
        if not path:
            self.path = []
            self.path_index = 0
            return
        # drop initial node if it equals current cell
        if len(path) > 0 and path[0][0] == self.cell_x and path[0][1] == self.cell_y:
            path = path[1:]
        self.path = path
        self.path_index = 0
        if self.path:
            nx, ny = self.path[0]
            self.request_move_to_cell(nx, ny)

    def stop(self):
        """Stop movement and clear active path (manual override)."""
        self.path = []
        self.path_index = 0
        self.moving = False
        self.target_pixel_x, self.target_pixel_y = self.pixel_x, self.pixel_y

    def move_by(self, dx: int, dy: int, game_map) -> bool:
        """
        Move one cell by (dx,dy). Manual control (keyboard). Cancels any current path.
        Returns True if movement accepted (cell was walkable).
        """
        tx = self.cell_x + dx
        ty = self.cell_y + dy
        if not (0 <= tx < game_map.width and 0 <= ty < game_map.height):
            return False
        if not game_map.is_walkable(tx, ty):
            return False
        # cancel any path
        self.path = []
        self.path_index = 0
        # start moving to the requested cell
        self.request_move_to_cell(tx, ty)
        return True

    # ------------------ Update & draw ------------------
    def calculate_player_speed(self, player_stats=None, weather_system=None, inventory=None):
        """
        Calcula la velocidad del jugador en píxeles/segundo según la fórmula del PDF.

        La velocidad se calcula como:
        v = v0 * climate_multiplier * weight_multiplier * reputation_multiplier * stamina_multiplier * surface_multiplier

        Donde v0 es la velocidad base en celdas/segundo, convertida a píxeles/segundo.
        """
        # Convertir celdas/seg a píxeles/seg
        pixels_per_sec = self.base_cells_per_sec * self.tile_size

        # Obtener multiplicadores con valores por defecto
        climate_multiplier = getattr(weather_system, "get_speed_multiplier", lambda: 1.0)()

        # Multiplicador por peso del inventario
        weight = getattr(inventory, "current_weight", 0.0)
        weight_multiplier = max(0.8, 1.0 - 0.03 * weight)

        # Multiplicador por reputación
        reputation_multiplier = 1.03 if getattr(player_stats, "reputation", 70) >= 90 else 1.0

        # Multiplicador por resistencia
        stamina_multiplier = 1.0
        if hasattr(player_stats, "stamina"):
            if player_stats.stamina <= 0:
                stamina_multiplier = 0.0  # Exhausto
            elif player_stats.stamina <= 30:
                stamina_multiplier = 0.8  # Cansado

        # Multiplicador por superficie (asumir 1.0 por defecto)
        surface_multiplier = 1.0

        # Calcular velocidad final
        final_speed = (pixels_per_sec * climate_multiplier * weight_multiplier *
                       reputation_multiplier * stamina_multiplier * surface_multiplier)

        return max(10.0, final_speed)  # Velocidad mínima

    def update(self, dt: float, player_stats=None, weather_system=None, inventory=None):
        if not self.moving:
            return

        # Calcular velocidad actual usando la función completa
        if player_stats and weather_system and inventory:
            speed = self.calculate_player_speed(player_stats, weather_system, inventory)
        else:
            # Velocidad por defecto si faltan parámetros
            speed = self.base_cells_per_sec * self.tile_size

        dx = self.target_pixel_x - self.pixel_x
        dy = self.target_pixel_y - self.pixel_y
        dist = (dx * dx + dy * dy) ** 0.5

        # Aplicar velocidad calculada
        if dist > 0:
            move_dist = min(dist, speed * dt)
            self.pixel_x += (dx / dist) * move_dist
            self.pixel_y += (dy / dist) * move_dist
        if dist < 1.0:
            # Arrived to the target cell center
            self.pixel_x = self.target_pixel_x
            self.pixel_y = self.target_pixel_y
            # update logical cell
            self.cell_x, self.cell_y = pixel_to_cell(self.pixel_x, self.pixel_y, self.tile_size, self.map_rows,
                                                     self.flip_y)
            self.moving = False
            # advance path if exists
            if self.path and self.path_index < len(self.path) - 1:
                self.path_index += 1
                nx, ny = self.path[self.path_index]
                self.request_move_to_cell(nx, ny)
            else:
                # path finished (either no path or last node reached)
                self.path = []
                self.path_index = 0
            return

    def draw(self):
        arcade.draw_circle_filled(self.pixel_x, self.pixel_y, self.radius, self.color)
        arcade.draw_circle_outline(self.pixel_x, self.pixel_y, self.radius, arcade.color.BLACK, 2)

    # ELIMINAR el segundo método calculate_player_speed duplicado