import arcade
import arcade.gui

from run_api.api_client import ApiClient
from run_api.state_initializer import init_game_state
from run_api.save_manager import save_game, load_game, list_saves
#from game_view import GameView

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
SCREEN_TITLE = "Courier Quest"

# ========================
# Vista: Menú Principal
# ========================
class MainMenuView(arcade.View):
    def __init__(self):
        super().__init__()
        self.manager = arcade.gui.UIManager()
        #self.manager.enable() #habilitar on_show_view

        # Layout vertical
        v_box = arcade.gui.UIBoxLayout(vertical=True, space_between=20)

        # Botón: Continuar
        continue_btn = arcade.gui.UIFlatButton(text="Continuar", width=200)
        v_box.add(continue_btn)

        @continue_btn.event("on_click")
        def on_click_continue(event):
            try:
                saves = list_saves()
                if saves:
                    state = load_game(saves[0])
                    if state:
                        self.window.show_view(GameView(state))
                        return
                # Si no hay guardados o falla la carga, ir al menú de juego
                self.window.show_view(MainMenuView.GameMenuView())
            except Exception as e:
                print(f"[UI] Error al continuar: {e}")
                self.window.show_view(MainMenuView.GameMenuView())

        # Botón: Salir
        quit_btn = arcade.gui.UIFlatButton(text="Salir", width=200)
        v_box.add(quit_btn)

        @quit_btn.event("on_click")
        def on_click_quit(event):
            arcade.close_window()

        # Centrar todito
        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(child=v_box, anchor_x="center_x", anchor_y="center_y")
        self.manager.add(anchor)

    def on_show(self):
        arcade.set_background_color(arcade.color.DARK_BLUE_GRAY)

    def on_show_view(self):
        self.manager.enable()

    def on_hide_view(self):
        self.manager.disable()

    def on_draw(self):
        self.clear()
        self.manager.draw()
        arcade.draw_text("Courier Quest", SCREEN_WIDTH/2, SCREEN_HEIGHT-100,
                         arcade.color.WHITE, font_size=36, anchor_x="center")


# ========================
# Vista: Menú de Juego
# ========================
    class GameMenuView(arcade.View):
        def __init__(self):
            super().__init__()
            self.manager = arcade.gui.UIManager()
            #self.manager.enable() #habilitar on_show_view

            #layout vertical
            v_box = arcade.gui.UIBoxLayout(vertical=True, space_between=20)


            # Botón Nueva Partida
            new_game_button = arcade.gui.UIFlatButton(text="Nueva Partida", width=200)
            v_box.add(new_game_button)


            @new_game_button.event("on_click")
            def on_click_new(event):
                try:
                    api = ApiClient()
                    state = init_game_state(api)
                    save_game(state, "slot1.sav")  # guardar inmediatamente
                    self.window.show_view(GameView(state))
                except Exception as e:
                    print(f"[UI] Error creando nueva partida: {e}")

            # Botón Cargar Partida
            load_button = arcade.gui.UIFlatButton(text="Cargar Partida", width=200)
            v_box.add(load_button)

            @load_button.event("on_click")
            def on_click_load(event):
                try:
                    saves = list_saves()
                    if saves:
                        state = load_game(saves[0])  # carga el primer slot
                        if state:
                            self.window.show_view(GameView(state))
                            return
                    print("[INFO] No hay partidas guardadas")
                except Exception as e:
                    print(f"[UI] Error al cargar partida: {e}")

            # Botón Retroceder
            back_button = arcade.gui.UIFlatButton(text="Retroceder", width=200)
            v_box.add(back_button)

            @back_button.event("on_click")
            def on_click_back(event):
                self.window.show_view(MainMenuView())

            # Centrar layout
            anchor = arcade.gui.UIAnchorLayout()
            anchor.add(child=v_box, anchor_x="center_x", anchor_y="center_y")
            self.manager.add(anchor)

    def on_show_view(self):
        self.manager.enable()

    def on_hide_view(self):
        self.manager.disable()

    def on_show(self):
        arcade.set_background_color(arcade.color.DARK_SLATE_GRAY)

    def on_draw(self):
        self.clear()
        self.manager.draw()
        arcade.draw_text("Menú de Juego", SCREEN_WIDTH/2, SCREEN_HEIGHT-100,
                         arcade.color.WHITE, font_size=30, anchor_x="center")


# ========================
# Vista: Juego en curso
# ========================
class GameView(arcade.View):
    def __init__(self, state):
        super().__init__()
        from .map_manager import GameMap  # import local para evitar ciclos
        self.state = state or {}
        self.game_map = GameMap(self.state.get("city_map", {}))
        # tamaño de celda inicial basado en ventana actual
        w = max(1, self.game_map.width)
        h = max(1, self.game_map.height)
        self.tile_size = max(4, min(self.window.width // w, self.window.height // h))

    def on_show(self):
        arcade.set_background_color(arcade.color.DARK_GREEN)

    def on_resize(self, width: int, height: int):
        super().on_resize(width, height)
        # recalcular tamaño de tile al cambiar la ventana
        w = max(1, self.game_map.width)
        h = max(1, self.game_map.height)
        self.tile_size = max(4, min(width // w, height // h))

    def on_draw(self):
        self.clear()
        # Dibujo del mapa (modo debug, coloreado por tipo de celda)
        self.game_map.draw_debug(tile_size=self.tile_size, draw_grid_lines=True)
        # Overlay opcional
        arcade.draw_text("Partida en curso", self.window.width / 2, self.window.height - 40,
                         arcade.color.WHITE, 20, anchor_x="center")


# ... existing code ...

# ========================
# Programa Principal
# ========================
def main():
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    window.show_view(MainMenuView())
    arcade.run()


if __name__ == "__main__":
    main()
