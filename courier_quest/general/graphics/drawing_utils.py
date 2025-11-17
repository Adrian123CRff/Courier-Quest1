#drawing_utils.py
"""
Drawing utilities - Helper functions for drawing rectangles
"""
import arcade

def cancelelo():
    return

def _draw_rect_lrbt_filled(left: float, right: float, bottom: float, top: float, color) -> None:
    """Draw a filled rectangle with left, right, bottom, top coordinates."""
    arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, color)


def _draw_rect_lrbt_outline(left: float, right: float, bottom: float, top: float, color, line_width: int = 1) -> None:
    """Draw an outlined rectangle with left, right, bottom, top coordinates."""
    arcade.draw_lrbt_rectangle_outline(left, right, bottom, top, color, line_width)
    #hola como estan