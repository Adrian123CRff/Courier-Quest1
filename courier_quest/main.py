import arcade
import arcade.gui

from run_api.api_client import ApiClient
from run_api.state_initializer import init_game_state
from run_api.save_manager import save_game, load_game, list_saves
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from general.graphics.ui_view_gui import MainMenuView, SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE
#from graphics.handler_window import SubMenu

def main():
    #game = CourierQuest()
    #game.setup()
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    window.show_view(MainMenuView())
    arcade.run()


if __name__ == "__main__":
    main()