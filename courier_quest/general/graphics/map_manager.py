# map_manager.py
"""
GameMap manager - robusto y con fallback.
- Detecta / usa 'tiles' si están.
- Si no, reconstruye grid desde 'buildings' y 'roads' y (opcional) guarda tiles generados.
- Permite flip Y (fila 0 arriba) para dibujo.
- Aplica 'legend' para ampliar TILE_DEFS automáticamente si aparece en JSON.
"""

import arcade
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional

# ---------------- Configurables ----------------
RECONSTRUCT_AND_SAVE = True   # guarda el 'tiles' reconstruido en api_cache/city_map.json
CACHE_PATH = Path("api_cache") / "city_map.json"
FLIP_Y = True                 # True -> fila 0 en la parte superior (más natural para mapas)

# ---------------- Default TILE_DEFS (puedes ampliar) ----------------
TILE_DEFS: Dict[str, Dict[str, Any]] = {
    "C": {"name": "Calle", "walkable": True, "speed": 1.0, "color": arcade.color.LIGHT_GRAY},
    "R": {"name": "Carretera", "walkable": True, "speed": 1.5, "color": arcade.color.DARK_GRAY},
    "B": {"name": "Edificio", "walkable": False, "speed": 0, "color": arcade.color.DARK_BROWN},
    "P": {"name": "Parque", "walkable": True, "speed": 0.8, "color": arcade.color.DARK_GREEN},
    "W": {"name": "Agua", "walkable": False, "speed": 0, "color": arcade.color.BLUE},
    "?": {"name": "Desconocido", "walkable": False, "speed": 0, "color": arcade.color.RED},
}

# ---------------- Dibujo: escoger función disponible ----------------
if hasattr(arcade, "draw_xywh_rectangle_filled"):
    def _draw_tile(x: float, y: float, w: float, h: float, color):
        arcade.draw_xywh_rectangle_filled(x, y, w, h, color)
elif hasattr(arcade, "draw_rectangle_filled"):
    def _draw_tile(x: float, y: float, w: float, h: float, color):
        # center-based
        cx = x + w/2
        cy = y + h/2
        arcade.draw_rectangle_filled(cx, cy, w, h, color)
elif hasattr(arcade, "draw_lbwh_rectangle_filled"):
    def _draw_tile(x: float, y: float, w: float, h: float, color):
        arcade.draw_lbwh_rectangle_filled(x, y, w, h, color)
else:
    raise RuntimeError("No se encontró función de dibujo compatible en arcade (xywh / rectangle_filled / lbwh).")

# ---------------- Helpers utilitarios ----------------
def _safe_int(v: Any) -> int:
    try:
        return int(v)
    except Exception:
        try:
            return int(float(v))
        except Exception:
            return 0

def _mark_rectangle(grid: List[List[str]], x: int, y: int, w: int, h: int, symbol: str):
    rows = len(grid)
    cols = len(grid[0]) if rows>0 else 0
    for yy in range(y, y + h):
        if yy < 0 or yy >= rows: continue
        for xx in range(x, x + w):
            if xx < 0 or xx >= cols: continue
            grid[yy][xx] = symbol

def _mark_cells(grid: List[List[str]], cells: List[Tuple[int,int]], symbol: str):
    rows = len(grid)
    cols = len(grid[0]) if rows>0 else 0
    for (cx, cy) in cells:
        x = _safe_int(cx); y = _safe_int(cy)
        if 0 <= y < rows and 0 <= x < cols:
            grid[y][x] = symbol

def _cells_from_path(path: Any) -> List[Tuple[int,int]]:
    result: List[Tuple[int,int]] = []
    for p in path:
        if isinstance(p, dict):
            if "x" in p and "y" in p:
                result.append((_safe_int(p["x"]), _safe_int(p["y"])))
            elif "col" in p and "row" in p:
                result.append((_safe_int(p["col"]), _safe_int(p["row"])))
        elif isinstance(p, (list, tuple)) and len(p) >= 2:
            result.append((_safe_int(p[0]), _safe_int(p[1])))
    return result

def _hex_to_rgb(h: str) -> Optional[Tuple[int,int,int]]:
    try:
        h = h.lstrip("#")
        if len(h) == 6:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        if len(h) == 3:
            return (int(h[0]*2, 16), int(h[1]*2, 16), int(h[2]*2, 16))
    except Exception:
        pass
    return None

# ---------------- Legend parser ----------------
def _apply_legend_to_tile_defs(map_data: Dict[str,Any]):
    """
    Si 'legend' está presente y tiene estructura esperada, incorporar símbolos a TILE_DEFS.
    legend esperado: { "C": {"name":"Calle", "walkable": True, "speed":1.0, "color":"#RRGGBB"}, ... }
    """
    legend = map_data.get("legend")
    if not isinstance(legend, dict):
        return

    for sym, info in legend.items():
        try:
            name = info.get("name", TILE_DEFS.get(sym, {}).get("name", str(sym)))
            walkable = bool(info.get("walkable", TILE_DEFS.get(sym, {}).get("walkable", False)))
            speed = float(info.get("speed", TILE_DEFS.get(sym, {}).get("speed", 0)))
            color_val = info.get("color", None)
            color = TILE_DEFS.get(sym, {}).get("color", arcade.color.GRAY)
            if isinstance(color_val, str):
                rgb = _hex_to_rgb(color_val)
                if rgb:
                    color = rgb  # arcade acepta tuplas (r,g,b)
            TILE_DEFS[sym] = {"name": name, "walkable": walkable, "speed": speed, "color": color}
        except Exception as e:
            print(f"[LEGEND] error parsing legend for {sym}: {e}")

# ---------------- Cache save ----------------
def _save_tiles_to_cache(map_data: Dict[str,Any], tiles: List[List[str]]):
    try:
        cache_dir = CACHE_PATH.parent
        cache_dir.mkdir(exist_ok=True, parents=True)
        if CACHE_PATH.exists():
            try:
                current = json.load(CACHE_PATH.open(encoding="utf-8"))
            except Exception:
                current = {}
        else:
            current = {}

        current["tiles"] = tiles
        current["name"] = current.get("name", map_data.get("city_name", map_data.get("name", "TigerCity")))
        current["width"] = current.get("width", map_data.get("width", len(tiles[0]) if tiles else 0))
        current["height"] = current.get("height", map_data.get("height", len(tiles)))
        meta = current.get("_meta", {})
        meta.update({
            "last_generated": datetime.utcnow().isoformat() + "Z",
            "generated_by": "map_manager.reconstruction",
            "source": map_data.get("source", "api_or_cache")
        })
        current["_meta"] = meta

        with CACHE_PATH.open("w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
        print(f"[MAP SAVE] tiles guardados en {CACHE_PATH}")
    except Exception as e:
        print("[MAP SAVE] fallo al guardar cache:", e)

# ---------------- Main GameMap class ----------------
class GameMap:
    def __init__(self, map_data: Dict[str,Any]):
        if not isinstance(map_data, dict):
            map_data = {}

        # metadata
        self.name = map_data.get("city_name", map_data.get("name", "Unknown"))
        self.width = int(map_data.get("width", 0) or 0)
        self.height = int(map_data.get("height", 0) or 0)

        # Prefer 'tiles' (una matriz). Fallback a 'map' o reconstruir
        raw_tiles = map_data.get("tiles") or map_data.get("map") or None

        if raw_tiles:
            # normalizar filas (acepta filas como strings o listas)
            normalized: List[List[str]] = []
            for r in raw_tiles:
                if isinstance(r, str):
                    normalized.append(list(r))
                else:
                    normalized.append([str(x) for x in r])

            if self.height == 0:
                self.height = len(normalized)
            if self.width == 0 and len(normalized) > 0:
                self.width = len(normalized[0])

            fixed: List[List[str]] = []
            for r in normalized:
                if len(r) < self.width:
                    r = r + ["?"]*(self.width - len(r))
                elif len(r) > self.width:
                    r = r[:self.width]
                fixed.append(r)

            if len(fixed) < self.height:
                for _ in range(self.height - len(fixed)):
                    fixed.append(["?"] * self.width)

            self.grid = fixed
            print("[MAP INIT] Usando 'tiles' directo (map_data).")
        else:
            # No hay 'tiles' -> intentar reconstruir desde objetos
            print("[MAP INIT] No se encontraron 'tiles' ni 'map' -> intentando reconstruir desde 'buildings'/'roads'...")
            # intentar obtener width/height alternativos
            if not self.width:
                self.width = int(map_data.get("cols", map_data.get("columns", 0) or 0))
            if not self.height:
                self.height = int(map_data.get("rows", map_data.get("rows_count", 0) or 0))
            if self.width <= 0:
                self.width = int(map_data.get("width", 30) or 30)
            if self.height <= 0:
                self.height = int(map_data.get("height", 30) or 30)

            # inicializar con 'C' (calles/transitables) en vez de '?'
            grid: List[List[str]] = [["C" for _ in range(self.width)] for _ in range(self.height)]

            # imprimir samples para depuración
            if "buildings" in map_data:
                print("[MAP INIT] muestras buildings (primeros 5):", map_data["buildings"][:5])
            if "roads" in map_data:
                print("[MAP INIT] muestras roads (primeros 5):", map_data["roads"][:5])
            if "legend" in map_data:
                print("[MAP INIT] legend keys:", list(map_data["legend"].keys()))

            # procesar buildings
            for b in map_data.get("buildings", []):
                if isinstance(b, dict) and ("x" in b and "y" in b):
                    bx = _safe_int(b.get("x", 0))
                    by = _safe_int(b.get("y", 0))
                    bw = _safe_int(b.get("w", b.get("width", 1)))
                    bh = _safe_int(b.get("h", b.get("height", 1)))
                    _mark_rectangle(grid, bx, by, bw, bh, "B")
                elif isinstance(b, dict) and "cells" in b:
                    cells = []
                    for c in b["cells"]:
                        if isinstance(c, dict) and "x" in c and "y" in c:
                            cells.append((c["x"], c["y"]))
                        elif isinstance(c, (list, tuple)) and len(c) >= 2:
                            cells.append((c[0], c[1]))
                    _mark_cells(grid, cells, "B")
                elif isinstance(b, (list, tuple)):
                    cells = []
                    for item in b:
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            cells.append((item[0], item[1]))
                    _mark_cells(grid, cells, "B")

            # procesar roads
            for r in map_data.get("roads", []):
                if isinstance(r, dict):
                    if "cells" in r:
                        pts = []
                        for c in r["cells"]:
                            if isinstance(c, (list, tuple)) and len(c) >= 2:
                                pts.append((c[0], c[1]))
                            elif isinstance(c, dict) and "x" in c and "y" in c:
                                pts.append((c["x"], c["y"]))
                        _mark_cells(grid, pts, "R")
                    elif "path" in r:
                        pts = _cells_from_path(r["path"])
                        _mark_cells(grid, pts, "R")
                    elif "points" in r:
                        pts = _cells_from_path(r["points"])
                        _mark_cells(grid, pts, "R")
                    elif "x" in r and "y" in r:
                        _mark_cells(grid, [(r["x"], r["y"])], "R")
                elif isinstance(r, (list, tuple)):
                    pts = _cells_from_path(r)
                    _mark_cells(grid, pts, "R")

            self.grid = grid
            print("[MAP INIT] Grid reconstruido desde objetos. (puedes pegar muestras de buildings/roads si algo falta)")

            # aplicar legend antes de dibujar / guardar
            _apply_legend_to_tile_defs(map_data)

            # guardar reconstrucción si está habilitado
            if RECONSTRUCT_AND_SAVE:
                try:
                    _save_tiles_to_cache(map_data, self.grid)
                except Exception as e:
                    print("[MAP INIT] No se pudo guardar tiles en cache:", e)

        # asegurar dimensiones finales
        if len(self.grid) > 0:
            if self.height == 0:
                self.height = len(self.grid)
            if self.width == 0:
                self.width = len(self.grid[0])

        print(f"[MAP INIT] name={self.name}, size={self.width}x{self.height}, rows={len(self.grid)}")

    # ---------------- API util para la lógica del juego ----------------
    def is_walkable(self, x: int, y: int) -> bool:
        # x,y esperados en coordenadas de celdas (0..width-1, 0..height-1)
        if 0 <= y < len(self.grid) and 0 <= x < len(self.grid[y]):
            return TILE_DEFS.get(self.grid[y][x], TILE_DEFS["?"])["walkable"]
        return False

    def get_speed(self, x: int, y: int) -> float:
        if 0 <= y < len(self.grid) and 0 <= x < len(self.grid[y]):
            return TILE_DEFS.get(self.grid[y][x], TILE_DEFS["?"])["speed"]
        return 0.0

    # ---------------- Dibujo debug ----------------
    def draw_debug(self, tile_size: int = 20, draw_grid_lines: bool = True):
        rows = len(self.grid)
        cols = len(self.grid[0]) if rows>0 else 0
        for y in range(rows):
            for x in range(cols):
                symbol = self.grid[y][x]
                props = TILE_DEFS.get(symbol, TILE_DEFS["?"])
                color = props["color"]

                px = x * tile_size
                # Si FLIP_Y True, fila 0 se dibuja en la parte superior
                if FLIP_Y:
                    py = (rows - 1 - y) * tile_size
                else:
                    py = y * tile_size

                _draw_tile(px, py, tile_size, tile_size, color)

                if draw_grid_lines:
                    cx = px + tile_size/2
                    cy = py + tile_size/2
                    try:
                        arcade.draw_rectangle_outline(cx, cy, tile_size, tile_size, arcade.color.BLACK, 1)
                    except Exception:
                        # fallback dibujo simple de dos líneas
                        arcade.draw_line(px, py + tile_size, px + tile_size, py + tile_size, arcade.color.BLACK)
                        arcade.draw_line(px, py, px, py + tile_size, arcade.color.BLACK)
