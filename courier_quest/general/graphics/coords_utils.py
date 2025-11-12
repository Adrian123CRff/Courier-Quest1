#coords_utils.py
from __future__ import annotations

from typing import Any, Tuple


class CoordsUtils:
    def __init__(self, view: Any) -> None:
        self.view = view

    def split_xy_str(self, s: str):
        for sep in [",", "|", ";", " "]:
            if sep in s:
                a, b = s.split(sep, 1)
                return a.strip(), b.strip()
        return None, None

    def coerce_xy(self, val) -> Tuple[int | None, int | None]:
        try:
            if val is None:
                return None, None
            if isinstance(val, (list, tuple)) and len(val) >= 2:
                return int(float(val[0])), int(float(val[1]))
            if isinstance(val, dict):
                for kx, ky in [("x", "y"), ("cx", "cy"), ("col", "row"), ("c", "r")]:
                    x = val.get(kx, None)
                    y = val.get(ky, None)
                    if x is not None and y is not None:
                        return int(float(x)), int(float(y))
            if isinstance(val, str):
                a, b = self.split_xy_str(val)
                if a is not None and b is not None:
                    return int(float(a)), int(float(b))
        except Exception:
            pass
        return None, None


