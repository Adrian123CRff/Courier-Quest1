# graphics/weather_renderer.py
"""
WeatherRenderer: efectos visuales para el clima.
- Lluvia: gotas que caen (líneas vert.) (RainDrop)
- Nieve: copos lentos (SnowFlake)
- Viento: partículas/trazos horizontales (WindParticle)
- Niebla: reutiliza la implementación de viento con parámetros más suaves
- Overlays globales y por-tile (sombra / niebla / lluvia / nieve)
Compatible con Arcade 3.3.2 (usa draw_lrbt_rectangle_filled, draw_lbwh_rectangle_filled, draw_line, draw_circle_filled).
"""

import arcade
import math
import random
from typing import List, Tuple


class RainDrop:
    def __init__(self, x: float, y: float, speed: float, length: float):
        self.x = x
        self.y = y
        self.speed = speed
        self.length = length


class SnowFlake:
    def __init__(self, x: float, y: float, speed: float, size: float):
        self.x = x
        self.y = y
        self.speed = speed
        self.size = size


class WindParticle:
    """
    Partícula de viento: una línea horizontal que se desplaza lateralmente.
    direction: 1 -> derecha, -1 -> izquierda
    length: longitud del trazo en píxeles
    thickness: grosor del trazo (px)
    """
    def __init__(self, x: float, y: float, speed: float, length: float, direction: int, thickness: float, alpha: int):
        self.x = x
        self.y = y
        self.speed = speed
        self.length = length
        self.direction = direction
        self.thickness = thickness
        self.alpha = alpha


class WeatherRenderer:
    def __init__(self, view, seed: int = None):
        self.view = view
        # Usar dimensiones del mapa en lugar de la ventana completa
        self.map_width = getattr(view, 'MAP_WIDTH', 730)
        self.map_height = getattr(view, 'SCREEN_HEIGHT', 800)
        self.width = self.map_width
        self.height = self.map_height
        self.rng = random.Random(seed)

        # lluvia
        self.drops: List[RainDrop] = []
        self.max_drops = 500

        # nieve
        self.snowflakes: List[SnowFlake] = []
        self.max_flakes = 300

        # viento (partículas horizontales)
        self.wind_particles: List[WindParticle] = []
        self.max_wind_particles = 300

        # niebla: reutiliza la forma de "wind" pero con parámetros más lentos/tenues
        self.fog_particles: List[WindParticle] = []
        self.max_fog_particles = 250

        # overlays
        self.cloud_opacity = 0.0
        self.fog_strength = 0.0

    def on_resize(self, width: int, height: int):
        # Mantener las dimensiones del mapa, no de la ventana completa
        self.map_width = getattr(self.view, 'MAP_WIDTH', 730)
        self.map_height = getattr(self.view, 'SCREEN_HEIGHT', 800)
        self.width = self.map_width
        self.height = self.map_height

    # ---------------- update (gestión de partículas por clima) ----------------
    def update(self, dt: float, weather_state: dict):
        cond = weather_state.get("condition", "clear")
        intensity = float(weather_state.get("intensity", 0.0))

        # ---------------- cloud overlay / fog_strength ----------------
        if cond in ("clouds", "rain_light", "rain", "storm", "fog", "snow", "wind"):
            target = min(0.95, 0.25 + intensity * 0.6)
        else:
            target = 0.0
        self.cloud_opacity += (target - self.cloud_opacity) * min(1.0, dt * 2.0)

        if cond == "fog":
            self.fog_strength += (min(0.9, 0.2 + intensity * 0.7) - self.fog_strength) * min(1.0, dt * 2.0)
        else:
            self.fog_strength += (0.0 - self.fog_strength) * min(1.0, dt * 2.0)

        # ---------------- lluvia ----------------
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
            # ligero desvío horizontal
            d.x += math.sin(d.y * 0.01) * 30 * dt
            if d.y < -20:
                d.y = self.height + self.rng.uniform(0, 50)
                d.x = self.rng.uniform(0, self.width)

        # ---------------- nieve ----------------
        if cond == "snow":
            target_flakes = int(30 + intensity * 120)
        else:
            target_flakes = 0
        target_flakes = min(self.max_flakes, target_flakes)
        while len(self.snowflakes) < target_flakes:
            x = self.rng.uniform(0, self.width)
            y = self.rng.uniform(0, self.height)
            speed = self.rng.uniform(10, 70) * (0.6 + 0.8 * intensity)  # más lento que lluvia
            size = self.rng.uniform(1.5, 4.5)
            self.snowflakes.append(SnowFlake(x, y, speed, size))
        if len(self.snowflakes) > target_flakes:
            self.snowflakes = self.snowflakes[:target_flakes]
        for f in self.snowflakes:
            f.y -= f.speed * dt
            f.x += math.sin(f.y * 0.01) * 8 * dt
            if f.y < -10:
                f.y = self.height + self.rng.uniform(0, 50)
                f.x = self.rng.uniform(0, self.width)

        # ---------------- viento (partículas horizontales) ----------------
        # objetivo en función de intensidad
        if cond == "wind":
            target_wind = int(20 + intensity * 240)
        else:
            target_wind = 0
        target_wind = min(self.max_wind_particles, target_wind)
        while len(self.wind_particles) < target_wind:
            # dirección aleatoria por partícula
            direction = self.rng.choice([-1, 1])
            # si dirección positiva (-> derecha) colocarlo más a la izquierda al nacer, y viceversa
            x = self.rng.uniform(0, self.width)
            y = self.rng.uniform(0, self.height)
            speed = self.rng.uniform(140, 420) * (0.6 + intensity)  # velocidad lateral
            length = self.rng.uniform(40, 140) * (0.6 + intensity)
            thickness = self.rng.uniform(1.0, 2.4)
            alpha = int(min(220, 120 + intensity * 120))
            self.wind_particles.append(WindParticle(x, y, speed, length, direction, thickness, alpha))
        if len(self.wind_particles) > target_wind:
            self.wind_particles = self.wind_particles[:target_wind]
        for p in self.wind_particles:
            p.x += p.direction * p.speed * dt
            # ligero bamboleo vertical
            p.y += math.sin(p.x * 0.005) * 10 * dt
            # si sale por la derecha o izquierda lo regeneramos al lado opuesto
            if p.x < -p.length - 20:
                p.x = self.width + self.rng.uniform(0, 40)
                p.y = self.rng.uniform(0, self.height)
                p.direction = self.rng.choice([-1, 1])
            if p.x > self.width + p.length + 20:
                p.x = -self.rng.uniform(0, 40)
                p.y = self.rng.uniform(0, self.height)
                p.direction = self.rng.choice([-1, 1])

        # ---------------- NIEBLA visual (usar la misma implementación que viento) ----------------
        # Querías que fog sea visualmente igual a wind (misma forma/ráfaga) — aquí la copiamos
        if cond == "fog":
            target_fog = int(30 + intensity * 200)
        else:
            target_fog = 0
        target_fog = min(self.max_fog_particles, target_fog)
        while len(self.fog_particles) < target_fog:
            direction = self.rng.choice([-1, 1])
            x = self.rng.uniform(0, self.width)
            y = self.rng.uniform(0, self.height)
            # parámetros más suaves (más lentos, más tenues)
            speed = self.rng.uniform(30, 120) * (0.5 + 0.8 * intensity)
            length = self.rng.uniform(60, 220) * (0.3 + 0.7 * intensity)
            thickness = self.rng.uniform(1.0, 1.8)
            alpha = int(min(160, 40 + intensity * 120))
            self.fog_particles.append(WindParticle(x, y, speed, length, direction, thickness, alpha))
        if len(self.fog_particles) > target_fog:
            self.fog_particles = self.fog_particles[:target_fog]
        for p in self.fog_particles:
            # movimiento lateral suave + drift vertical ligero
            p.x += p.direction * p.speed * dt * 0.6
            p.y += math.sin(p.x * 0.003) * 8 * dt
            if p.x < -p.length - 20:
                p.x = self.width + self.rng.uniform(0, 40)
                p.y = self.rng.uniform(0, self.height)
                p.direction = self.rng.choice([-1, 1])
            if p.x > self.width + p.length + 20:
                p.x = -self.rng.uniform(0, 40)
                p.y = self.rng.uniform(0, self.height)
                p.direction = self.rng.choice([-1, 1])

    # ---------------- tile overlay alpha (sombra por clima) ----------------
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
        if cond == "snow":
            return int(min(160, 40 + intensity * 100))
        return 0

    # ---------------- draw (render) ----------------
    def draw(self):
        # overlay global (cielo nublado) - solo sobre el área del mapa
        if self.cloud_opacity > 0.01:
            alpha = int(max(0, min(200, self.cloud_opacity * 255)))
            # draw_lrbt_rectangle_filled(left, right, bottom, top, color) - solo sobre el mapa
            arcade.draw_lrbt_rectangle_filled(0, self.width, 0, self.height, (20, 24, 40, alpha))

        # overlay por tiles (sombra, niebla, nieve)
        gm = getattr(self.view, "game_map", None)
        tile_size = getattr(self.view, "tile_size", None)
        if gm and tile_size:
            grid = getattr(gm, "grid", None)
            if grid and len(grid) > 0:
                rows = len(grid)
                cols = len(grid[0]) if rows > 0 and len(grid[0]) > 0 else 0
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
                                # niebla: rectángulo tenue y claro
                                arcade.draw_lbwh_rectangle_filled(
                                    px - tile_size / 2,
                                    py - tile_size / 2,
                                    tile_size,
                                    tile_size,
                                    (220, 220, 220, int(alpha * 0.7))
                                )
                            elif cond == "snow":
                                arcade.draw_lbwh_rectangle_filled(
                                    px - tile_size / 2,
                                    py - tile_size / 2,
                                    tile_size,
                                    tile_size,
                                    (200, 220, 255, int(alpha * 0.3))
                                )
                            else:
                                arcade.draw_lbwh_rectangle_filled(
                                    px - tile_size / 2,
                                    py - tile_size / 2,
                                    tile_size,
                                    tile_size,
                                    (0, 0, 0, alpha)
                                )


        # ---------------- draw lluvia (azul) ----------------
        if self.drops:
            for d in self.drops:
                # color azul vivo para lluvia (RGB)
                rain_color = (60, 140, 255)  # azul Dodger-like
                # si quieres una línea algo más visible usa width=1.2 o 2
                arcade.draw_line(d.x, d.y, d.x + 1.5, d.y + d.length, rain_color, 1)

        # ---------------- draw nieve ----------------
        if self.snowflakes:
            for f in self.snowflakes:
                arcade.draw_circle_filled(f.x, f.y, f.size, (180, 220, 255, 220))

        # ---------------- draw viento (líneas horizontales) ----------------
        if self.wind_particles:
            for p in self.wind_particles:
                # color blanco/gris claro con alpha por partícula
                col = (220, 230, 245, p.alpha)
                # dibujar línea horizontal según direction y length
                x1 = p.x
                x2 = p.x + p.direction * p.length
                y1 = p.y
                y2 = p.y + math.sin(p.x * 0.01) * 2  # pequeña inclinación visual
                # grosor aproximado: arcade.draw_line usa 'width' (último parámetro)
                arcade.draw_line(x1, y1, x2, y2, col, p.thickness)

        # ---------------- draw niebla (usa la implementación de viento pero más tenue) ----------------
        if self.fog_particles:
            for p in self.fog_particles:
                col = (200, 200, 210, int(p.alpha * 0.7))
                x1 = p.x
                x2 = p.x + p.direction * p.length
                y1 = p.y
                y2 = p.y + math.sin(p.x * 0.01) * 1.5
                arcade.draw_line(x1, y1, x2, y2, col, p.thickness * 0.9)
