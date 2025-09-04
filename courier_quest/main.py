import arcade
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from general.graphics.game_window import CourierQuest
from general.graphics.handler_window import  SubMenu

def main():
    game = CourierQuest()
    game.setup()

    arcade.run()


if __name__ == "__main__":
    main()