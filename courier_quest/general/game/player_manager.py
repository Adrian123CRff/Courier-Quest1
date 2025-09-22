# player_manager.py
import arcade
from typing import Tuple

# Parámetros
PLAYER_SPEED_PIXELS_PER_SEC = 120  # velocidad para interpolación suave

class Player:
    def __init__(self, start_cell: Tuple[int,int], tile_size: int, map_rows: int, flip_y: bool = True):
        # posición actual en celdas (enteros)
        self.cell_x, self.cell_y = int(start_cell[0]), int(start_cell[1])
        self.tile_size = tile_size
        self.map_rows = map_rows
        self.flip_y = flip_y

        # pixel center inicial
        self.pixel_x, self.pixel_y = self.cell_to_pixel(self.cell_x, self.cell_y)
        self.target_pixel_x, self.target_pixel_y = self.pixel_x, self.pixel_y

        # estado de movimiento
        self.moving = False

        # apariencia
        self.radius = tile_size * 0.35
        self.color = arcade.color.AUBURN

    def cell_to_pixel(self, cx: int, cy: int):
        """Convierte coordenadas de celda a coordenadas de píxel (centro)."""
        px = cx * self.tile_size + self.tile_size / 2
        if self.flip_y:
            py = (self.map_rows - 1 - cy) * self.tile_size + self.tile_size / 2
        else:
            py = cy * self.tile_size + self.tile_size / 2
        return px, py

    def pixel_to_cell(self, px: float, py: float):
        """Convierte píxel a celda (entera)."""
        cx = int(px // self.tile_size)
        if self.flip_y:
            # invertir y
            row_index = int(py // self.tile_size)
            cy = (self.map_rows - 1) - row_index
        else:
            cy = int(py // self.tile_size)
        return cx, cy

    def teleport_to_cell(self, cx: int, cy: int):
        self.cell_x, self.cell_y = int(cx), int(cy)
        self.pixel_x, self.pixel_y = self.cell_to_pixel(cx, cy)
        self.target_pixel_x, self.target_pixel_y = self.pixel_x, self.pixel_y
        self.moving = False

    def request_move_to_cell(self, cx: int, cy: int):
        """Configura target si la celda es diferente."""
        self.cell_x = int(self.cell_x)  # maintain current cell index
        if cx == self.cell_x and cy == self.cell_y:
            return
        self.target_pixel_x, self.target_pixel_y = self.cell_to_pixel(cx, cy)
        self.moving = True
        # Notar: no cambiamos immediately cell_x/cell_y hasta llegar (opcional)

    def update(self, dt: float):
        """Interpolación suave hacia target_pixel."""
        if not self.moving:
            return
        dx = self.target_pixel_x - self.pixel_x
        dy = self.target_pixel_y - self.pixel_y
        dist = (dx*dx + dy*dy) ** 0.5
        if dist < 1.0:
            # llegamos
            self.pixel_x, self.pixel_y = self.target_pixel_x, self.target_pixel_y
            # actualizar cell indices basados en pixel position
            self.cell_x, self.cell_y = self.pixel_to_cell(self.pixel_x, self.pixel_y)
            self.moving = False
            return
        # avanzar proporcional al tiempo
        move = PLAYER_SPEED_PIXELS_PER_SEC * dt
        t = min(1.0, move / dist)
        self.pixel_x += dx * t
        self.pixel_y += dy * t

    def draw(self):
        arcade.draw_circle_filled(self.pixel_x, self.pixel_y, self.radius, self.color)
        # opcional: dibujar outline
        arcade.draw_circle_outline(self.pixel_x, self.pixel_y, self.radius, arcade.color.BLACK, 2)
