# player_manager.py
import arcade
import os
from typing import Tuple

PLAYER_SPEED_PIXELS_PER_SEC = 120

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
RESOURCE_PATH = os.path.join(BASE_PATH, "..", "..", "resources", "icons", "ciclista.png")
RESOURCE_PATH = os.path.normpath(RESOURCE_PATH)

class Player:
    def __init__(self, start_cell: Tuple[int, int], tile_size: int, map_rows: int, flip_y: bool = True):
        self.cell_x: int = int(start_cell[0])
        self.cell_y: int = int(start_cell[1])
        self.tile_size: int = tile_size
        self.map_rows: int = map_rows
        self.flip_y: bool = flip_y

        self.pixel_x, self.pixel_y = self.cell_to_pixel(self.cell_x, self.cell_y)
        self.target_pixel_x, self.target_pixel_y = self.pixel_x, self.pixel_y

        self.moving: bool = False

        self.texture: arcade.Texture = arcade.load_texture(RESOURCE_PATH)
        self.sprite = arcade.Sprite(
            self.texture,
            scale=self.tile_size / self.texture.width,
            center_x=self.pixel_x,
            center_y=self.pixel_y
        )
        self.sprite_list = arcade.SpriteList()
        self.sprite_list.append(self.sprite)

    def cell_to_pixel(self, cx: int, cy: int) -> Tuple[float, float]:
        px = (cx + 0.5) * self.tile_size
        py = (self.map_rows - cy - 0.5) * self.tile_size if self.flip_y else (cy + 0.5) * self.tile_size
        return px, py

    def request_move_to_cell(self, cx: int, cy: int) -> None:
        self.cell_x, self.cell_y = cx, cy
        self.target_pixel_x, self.target_pixel_y = self.cell_to_pixel(cx, cy)
        self.moving = True

    def update(self, dt: float) -> None:
        if not self.moving:
            return

        dx = self.target_pixel_x - self.pixel_x
        dy = self.target_pixel_y - self.pixel_y
        dist = (dx ** 2 + dy ** 2) ** 0.5

        if dist < 1:
            self.pixel_x, self.pixel_y = self.target_pixel_x, self.target_pixel_y
            self.moving = False
        else:
            step = PLAYER_SPEED_PIXELS_PER_SEC * dt
            if step >= dist:
                self.pixel_x, self.pixel_y = self.target_pixel_x, self.target_pixel_y
                self.moving = False
            else:
                self.pixel_x += dx / dist * step
                self.pixel_y += dy / dist * step

        self.sprite.center_x = self.pixel_x
        self.sprite.center_y = self.pixel_y

    def draw(self) -> None:
        # En Arcade 3.3.2 dibujamos la lista
        self.sprite_list.draw()
