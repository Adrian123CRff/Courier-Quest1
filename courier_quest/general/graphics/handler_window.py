import arcade
import arcade.gui
from api_handler import APIHandler

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
SCREEN_TITLE = "Menú basado en boceto"


# ------------------------------
# VISTA PRINCIPAL DEL MENÚ
# ------------------------------
class MainMenu(arcade.View):
    def __init__(self):
        super().__init__()
        self.manager = arcade.gui.UIManager()

        # Botón Empezar
        start_button = arcade.gui.UIFlatButton(text="Empezar", width=200, height=50)
        @start_button.event("on_click")
        def on_click_start(event):
            submenu = SubMenu()
            self.window.show_view(submenu)

        # Botón Salir
        exit_button = arcade.gui.UIFlatButton(text="Salir", width=200, height=50)
        @exit_button.event("on_click")
        def on_click_exit(event):
            arcade.exit()

        # Layout vertical
        layout = arcade.gui.UIBoxLayout(space_between=20)
        layout.add(start_button)
        layout.add(exit_button)

        # Centrar layout
        self.anchor = self.manager.add(arcade.gui.UIAnchorLayout())
        self.anchor.add(anchor_x="center_x", anchor_y="center_y", child=layout)

    def on_show_view(self):
        arcade.set_background_color(arcade.color.DARK_BLUE_GRAY)
        self.manager.enable()

    def on_hide_view(self):
        self.manager.disable()

    def on_draw(self):
        self.clear()
        arcade.draw_text("Menú Principal", 100, 550, arcade.color.WHITE, 20)
        self.manager.draw()


# ------------------------------
# SUBMENÚ (Partida nueva / Cargar)
# ------------------------------
class SubMenu(arcade.View):
    def __init__(self):
        super().__init__()
        self.manager = arcade.gui.UIManager()

        # Botón Partida Nueva
        new_game_button = arcade.gui.UIFlatButton(text="Partida Nueva", width=250, height=50)
        @new_game_button.event("on_click")
        def on_click_new(event):
            print("Iniciar partida nueva")  # Aquí pondrías la lógica del juego

        # Botón Cargar
        load_button = arcade.gui.UIFlatButton(text="Cargar", width=250, height=50)
        @load_button.event("on_click")
        def on_click_load(event):
            print("Cargar partida guardada")

        # Botón Regresar
        back_button = arcade.gui.UIFlatButton(text="Volver", width=250, height=50)
        @back_button.event("on_click")
        def on_click_back(event):
            self.window.show_view(MainMenu())

        # Layout vertical
        layout = arcade.gui.UIBoxLayout(space_between=20)
        layout.add(new_game_button)
        layout.add(load_button)
        layout.add(back_button)

        # Centrar layout
        self.anchor = self.manager.add(arcade.gui.UIAnchorLayout())
        self.anchor.add(anchor_x="center_x", anchor_y="center_y", child=layout)

    def on_show_view(self):
        arcade.set_background_color([c - 50 for c in arcade.color.DARK_BLUE_GRAY])
        self.manager.enable()

    def on_hide_view(self):
        self.manager.disable()

    def on_draw(self):
        self.clear()
        arcade.draw_text("Submenú", 400, 550, arcade.color.WHITE, 24, anchor_x="center")
        self.manager.draw()


# ------------------------------
# MAIN
# ------------------------------
def main():
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    window.show_view(MainMenu())
    arcade.run()


if __name__ == "__main__":
    main()
