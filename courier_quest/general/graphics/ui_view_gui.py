#ui_view_gui.py
import arcade
import arcade.gui

from run_api.api_client import ApiClient
from run_api.state_initializer import init_game_state
from run_api.save_manager import save_game, load_game, list_saves

from graphics.game_window import MapPlayerView   # usamos la ventana real del juego
from game.player_state import PlayerState            # para reconstruir el estado

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 800
SCREEN_TITLE = "Courier Quest"

# ========================
# Vista: Menú Principal
# ========================
class MainMenuView(arcade.View):
    def __init__(self):
        super().__init__()
        self.manager = arcade.gui.UIManager()

        v_box = arcade.gui.UIBoxLayout(vertical=True, space_between=20)

        # Botón: Continuar
        continue_btn = arcade.gui.UIFlatButton(text="Continuar", width=200)
        v_box.add(continue_btn)

        @continue_btn.event("on_click")
        def on_click_continue(event):
            self.window.show_view(GameMenuView())

        # Botón: Salir
        quit_btn = arcade.gui.UIFlatButton(text="Salir", width=200)
        v_box.add(quit_btn)

        @quit_btn.event("on_click")
        def on_click_quit(event):
            arcade.close_window()

        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(child=v_box, anchor_x="center_x", anchor_y="center_y")
        self.manager.add(anchor)

        self.title_text = arcade.Text(
            "Courier Quest",
            SCREEN_WIDTH / 2,
            SCREEN_HEIGHT - 100,
            arcade.color.WHITE,
            font_size=36,
            anchor_x="center"
        )

    def on_show(self):
        arcade.set_background_color(arcade.color.DARK_BLUE_GRAY)

    def on_show_view(self):
        self.manager.enable()

    def on_hide_view(self):
        self.manager.disable()

    def on_draw(self):
        self.clear()
        self.manager.draw()
        self.title_text.draw()


# ========================
# Vista: Menú de Juego
# ========================
class GameMenuView(arcade.View):
    def __init__(self):
        super().__init__()
        self.manager = arcade.gui.UIManager()

        v_box = arcade.gui.UIBoxLayout(vertical=True, space_between=20)

        # --- Botón Nueva Partida ---
        new_game_button = arcade.gui.UIFlatButton(text="Nueva Partida ", width=250)
        v_box.add(new_game_button)

        @new_game_button.event("on_click")
        def on_click_new(event):
            try:
                api = ApiClient()
                state = init_game_state(api)
                save_game(state, "slot1.sav")
                self.window.show_view(MapPlayerView(state))
            except Exception as e:
                print(f"[UI] Error creando nueva partida: {e}")

        # --- Botón Cargar Partida ---
        load_button = arcade.gui.UIFlatButton(text="Cargar Partida ", width=250)
        v_box.add(load_button)

        @load_button.event("on_click")
        def on_click_load(event):
            try:
                saves = list_saves()
                if "slot1.sav" in saves:
                    data = load_game("slot1.sav")
                    if data:
                        # reconstruir GameState manualmente
                        state = PlayerState()
                        state.city_map = data.get("city_map", {})
                        state.jobs = data.get("jobs", [])
                        state.weather_state = data.get("weather_state", {})

                        self.window.show_view(MapPlayerView(state))
                        return
                print("[INFO] No hay partidas guardadas en slot1")
            except Exception as e:
                print(f"[UI] Error al cargar partida: {e}")

        # --- Botón Retroceder ---
        back_button = arcade.gui.UIFlatButton(text="Retroceder", width=200)
        v_box.add(back_button)

        @back_button.event("on_click")
        def on_click_back(event):
            self.window.show_view(MainMenuView())

        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(child=v_box, anchor_x="center_x", anchor_y="center_y")
        self.manager.add(anchor)

        # Título
        self.menu_text = arcade.Text(
            "Menú de Juego",
            SCREEN_WIDTH / 2,
            SCREEN_HEIGHT - 100,
            arcade.color.WHITE,
            font_size=30,
            anchor_x="center"
        )

    def on_show_view(self):
        self.manager.enable()

    def on_hide_view(self):
        self.manager.disable()

    def on_show(self):
        arcade.set_background_color(arcade.color.DARK_SLATE_GRAY)

    def on_draw(self):
        self.clear()
        self.manager.draw()
        self.menu_text.draw()




# ========================
# Programa Principal
# ========================
def main():
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    window.show_view(MainMenuView())
    arcade.run()


if __name__ == "_main_":
    main()