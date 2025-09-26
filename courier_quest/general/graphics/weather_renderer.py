"""
WeatherRenderer: efectos visuales sencillos para el clima.
- update(dt, weather_state) actualiza estado interno (cloud_opacity, lluvia).
- draw() dibuja overlay global + overlays por tile para 'oscurecer' o 'niebla'.
"""

import arcade
import math
import random
from typing import List


class RainDrop:
    def __init__(self, x, y, speed, length):
        self.x = x
        self.y = y
        self.speed = speed
        self.length = length


class WeatherRenderer:
    def __init__(self, view, seed: int = None):
        self.view = view
        self.width = getattr(view.window, "width", 800)
        self.height = getattr(view.window, "height", 600)
        self.rng = random.Random(seed)
        self.drops: List[RainDrop] = []
        self.max_drops = 500
        self.cloud_opacity = 0.0
        self.fog_strength = 0.0

    def on_resize(self, width: int, height: int):
        self.width = width
        self.height = height

    def update(self, dt: float, weather_state: dict):
        cond = weather_state.get("condition", "clear")
        intensity = float(weather_state.get("intensity", 0.0))

        if cond in ("clouds", "rain_light", "rain", "storm", "fog"):
            target = min(0.95, 0.25 + intensity * 0.6)
        else:
            target = 0.0
        self.cloud_opacity += (target - self.cloud_opacity) * min(1.0, dt * 2.0)

        if cond == "fog":
            self.fog_strength += (min(0.9, 0.2 + intensity * 0.7) - self.fog_strength) * min(1.0, dt * 2.0)
        else:
            self.fog_strength += (0.0 - self.fog_strength) * min(1.0, dt * 2.0)

        if cond in ("rain_light", "rain"):
            target_drops = int(40 + intensity * 160)
        elif cond == "storm":
            target_drops = int(200 + intensity * 300)
        else:
            target_drops = 0

        target_drops = min(self.max_drops, target_drops)
        while len(self.drops) < target_drops:
            x = self.rng.uniform(0, self.width)
            y = self.rng.uniform(0, self.height)
            speed = self.rng.uniform(240, 420) * (1.0 + intensity)
            length = self.rng.uniform(6, 14)
            self.drops.append(RainDrop(x, y, speed, length))
        if len(self.drops) > target_drops:
            self.drops = self.drops[:target_drops]

        for d in self.drops:
            d.y -= d.speed * dt
            d.x += math.sin(d.y * 0.01) * 3 * dt
            if d.y < -20:
                d.y = self.height + self.rng.uniform(0, 50)
                d.x = self.rng.uniform(0, self.width)

    def _tile_overlay_alpha(self, cond: str, intensity: float) -> int:
        if cond == "storm":
            return int(min(220, 160 + intensity * 60))
        if cond == "rain":
            return int(min(180, 100 + intensity * 80))
        if cond == "rain_light":
            return int(min(120, 40 + intensity * 80))
        if cond == "clouds":
            return int(min(80, 10 + intensity * 50))
        if cond == "fog":
            return int(min(200, 60 + intensity * 140))
        return 0

    def draw(self):
        if self.cloud_opacity > 0.01:
            alpha = int(max(0, min(200, self.cloud_opacity * 255)))
            arcade.draw_lrbt_rectangle_filled(
                0, self.width, 0, self.height, (20, 24, 40, alpha)
            )

        gm = getattr(self.view, "game_map", None)
        tile_size = getattr(self.view, "tile_size", None)
        if gm and tile_size:
            grid = getattr(gm, "grid", None)
            if grid:
                rows = len(grid)
                cols = len(grid[0]) if rows > 0 else 0
                s = getattr(self.view, "state", None)
                ws = getattr(s, "weather_state", {}) if s else {}
                cond = ws.get("condition", "clear")
                intensity = float(ws.get("intensity", 0.0))
                alpha = self._tile_overlay_alpha(cond, intensity)
                for y in range(rows):
                    for x in range(cols):
                        px = x * tile_size + tile_size / 2
                        py = (rows - 1 - y) * tile_size + tile_size / 2
                        if alpha > 0:
                            if cond == "fog":
                                arcade.draw_lbwh_rectangle_filled(
                                    px - tile_size / 2,
                                    py - tile_size / 2,
                                    tile_size,
                                    tile_size,
                                    (220, 220, 220, int(alpha * 0.7))
                                )
                            else:
                                arcade.draw_lbwh_rectangle_filled(
                                    px - tile_size / 2,
                                    py - tile_size / 2,
                                    tile_size,
                                    tile_size,
                                    (0, 0, 0, alpha)
                                )

        if self.drops:
            for d in self.drops:
                arcade.draw_line(
                    d.x, d.y, d.x + 1.5, d.y + d.length, arcade.color.AZURE, 1
                )

