import arcade
import arcade.gui
import os
import pyglet

from run_api.api_client import ApiClient
from run_api.state_initializer import init_game_state
from run_api.save_manager import SaveManager
from graphics.game_window import MapPlayerView
from game.player_state import PlayerState

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 800
SCREEN_TITLE = "Courier Quest"

save_manager = SaveManager()


class MainMenuView(arcade.View):
    def __init__(self):
        super().__init__()

        # Manager de UI
        self.manager = arcade.gui.UIManager()

        # Crear layout vertical
        v_box = arcade.gui.UIBoxLayout(space_between=20)

        # Botón Continuar
        continue_button = arcade.gui.UIFlatButton(text="Continuar", width=200)
        continue_button.on_click = self.on_continue_click
        v_box.add(continue_button)

        # Botón Salir
        quit_button = arcade.gui.UIFlatButton(text="Salir", width=200)
        quit_button.on_click = self.on_quit_click
        v_box.add(quit_button)

        # Centrar los botones
        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(child=v_box, anchor_x="center_x", anchor_y="center_y")
        self.manager.add(anchor)

    def on_continue_click(self, event):
        """Maneja el clic en Continuar"""
        self.manager.disable()
        # Usar el clock de pyglet directamente
        pyglet.clock.schedule_once(lambda dt: self.switch_to_game_menu(), 0.1)

    def switch_to_game_menu(self):
        """Cambia al menú de juego"""
        game_menu = GameMenuView()
        self.window.show_view(game_menu)

    def on_quit_click(self, event):
        """Maneja el clic en Salir"""
        arcade.close_window()

    def on_show_view(self):
        """Cuando se muestra la vista"""
        self.manager.enable()
        arcade.set_background_color(arcade.color.DARK_BLUE_GRAY)

    def on_hide_view(self):
        """Cuando se oculta la vista"""
        self.manager.disable()

    def on_draw(self):
        """Dibuja la vista"""
        self.clear()
        self.manager.draw()

        # Título
        arcade.draw_text(
            "Courier Quest",
            SCREEN_WIDTH // 2,
            SCREEN_HEIGHT - 100,
            arcade.color.WHITE,
            font_size=36,
            anchor_x="center"
        )


class GameMenuView(arcade.View):
    def __init__(self):
        super().__init__()

        self.manager = arcade.gui.UIManager()

        # Layout vertical
        v_box = arcade.gui.UIBoxLayout(space_between=20)

        # Botón Nueva Partida
        new_game_button = arcade.gui.UIFlatButton(text="Nueva Partida", width=200)
        new_game_button.on_click = self.on_new_game_click
        v_box.add(new_game_button)

        # Botón Cargar Partida
        load_button = arcade.gui.UIFlatButton(text="Cargar Partida", width=200)
        load_button.on_click = self.on_load_click
        v_box.add(load_button)

        # Botón Retroceder
        back_button = arcade.gui.UIFlatButton(text="Retroceder", width=200)
        back_button.on_click = self.on_back_click
        v_box.add(back_button)

        # Centrar
        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(child=v_box, anchor_x="center_x", anchor_y="center_y")
        self.manager.add(anchor)

    def on_new_game_click(self, event):
        """Maneja el clic en Nueva Partida"""
        self.manager.disable()
        pyglet.clock.schedule_once(lambda dt: self.start_new_game(), 0.1)

    def start_new_game(self):
        """Inicia una nueva partida"""
        try:
            api = ApiClient()
            state = init_game_state(api)
            save_manager.save_game(state, 1)

            # Crear vista del juego
            game_view = MapPlayerView(state)
            self.window.show_view(game_view)

        except Exception as e:
            print(f"Error iniciando nueva partida: {e}")

    def on_load_click(self, event):
        """Maneja el clic en Cargar Partida"""
        try:
            save_path = os.path.join(save_manager.save_dir, "slot1.sav")
            if os.path.exists(save_path):
                data = save_manager.load_game(1)
                if data:
                    # Reconstruir estado
                    state = PlayerState()
                    state.city_map = data.get("city_map", {})
                    state.jobs = data.get("jobs", [])
                    state.weather_state = data.get("weather_state", {})

                    # Crear vista del juego con estado cargado
                    game_view = MapPlayerView(state)
                    self.window.show_view(game_view)
                    return

            print("No hay partida guardada")
        except Exception as e:
            print(f"Error cargando partida: {e}")

    def on_back_click(self, event):
        """Maneja el clic en Retroceder"""
        self.manager.disable()
        pyglet.clock.schedule_once(lambda dt: self.window.show_view(MainMenuView()), 0.1)

    def on_show_view(self):
        """Cuando se muestra la vista"""
        self.manager.enable()
        arcade.set_background_color(arcade.color.DARK_SLATE_GRAY)

    def on_hide_view(self):
        """Cuando se oculta la vista"""
        self.manager.disable()

    def on_draw(self):
        """Dibuja la vista"""
        self.clear()
        self.manager.draw()

        # Título
        arcade.draw_text(
            "Menú de Juego",
            SCREEN_WIDTH // 2,
            SCREEN_HEIGHT - 100,
            arcade.color.WHITE,
            font_size=30,
            anchor_x="center"
        )


def main():
    """Función principal"""
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    menu_view = MainMenuView()
    window.show_view(menu_view)
    arcade.run()


if __name__ == "__main__":
    main()