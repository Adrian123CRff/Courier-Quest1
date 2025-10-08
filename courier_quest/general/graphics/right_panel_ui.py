from __future__ import annotations

from typing import Any
import arcade


class RightPanelUI:
    def __init__(self, view: Any) -> None:
        self.view = view

    def draw_frame(self) -> None:
        v = self.view
        from .game_window import _draw_rect_lrbt_filled, _draw_rect_lrbt_outline
        map_width = getattr(v, 'MAP_WIDTH', 730)
        screen_width = getattr(v, 'SCREEN_WIDTH', getattr(v, 'width', 0))
        screen_height = getattr(v, 'SCREEN_HEIGHT', getattr(v, 'height', 0))
        _draw_rect_lrbt_filled(map_width, screen_width, 0, screen_height, arcade.color.DARK_SLATE_BLUE)
        _draw_rect_lrbt_outline(map_width, screen_width, 0, screen_height, arcade.color.BLUE, 2)
        v.panel_title.draw()


