# main.py
import arcade
from general.graphics.ui_view_gui import MainMenuView

SCREEN_WIDTH = 1250
SCREEN_HEIGHT = 800
SCREEN_TITLE = "Courier Quest"


def main():
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    window.show_view(MainMenuView())
    arcade.run()


if __name__ == "__main__":
    main()
