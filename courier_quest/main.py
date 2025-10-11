# main.py
import logging
import arcade
from general.graphics.ui_view_gui import MainMenuView

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

SCREEN_WIDTH = 1250
SCREEN_HEIGHT = 800
SCREEN_TITLE = "Courier Quest"


def main():
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE, resizable=True)
    window.show_view(MainMenuView())
    arcade.run()


if __name__ == "__main__":
    main()
