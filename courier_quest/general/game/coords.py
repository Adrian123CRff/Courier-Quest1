# coords.py
from typing import Tuple

def cell_to_pixel(cx: int, cy: int, tile_size: int, rows: int, flip_y: bool = True) -> Tuple[float,float]:
    """Devuelve el centro en píxeles de la celda (cx,cy)."""
    px = cx * tile_size + tile_size / 2.0
    if flip_y:
        py = (rows - 1 - cy) * tile_size + tile_size / 2.0
    else:
        py = cy * tile_size + tile_size / 2.0
    return px, py

def pixel_to_cell(px: float, py: float, tile_size: int, rows: int, flip_y: bool = True) -> Tuple[int,int]:
    """Convierte coordenadas píxel a (cx,cy) (enteros)."""
    cx = int(px // tile_size)
    if flip_y:
        row_index = int(py // tile_size)
        cy = (rows - 1) - row_index
    else:
        cy = int(py // tile_size)
    return cx, cy
