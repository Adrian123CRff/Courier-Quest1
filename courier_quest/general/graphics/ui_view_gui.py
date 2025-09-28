
import arcade
import arcade.gui

from run_api.api_client import ApiClient
from run_api.state_initializer import init_game_state
from run_api.save_manager import save_game, load_game, list_saves
from weather_markov import WeatherMarkov
from weather_renderer import WeatherRenderer

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

        # --- TEXTO: Courier Quest ---
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

            # --- TEXTO: Menú de Juego ---
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
# Vista: Juego en curso (con clima dinámico)
# ========================
import arcade
from graphics.weather_markov import WeatherMarkov
from graphics.weather_renderer import WeatherRenderer
from run_api.api_client import ApiClient

class GameView(arcade.View):
    def __init__(self, state):
        super().__init__()
        from .map_manager import GameMap  # import local para evitar ciclos

        # Estado inicial
        self.state = state or {}
        self.game_map = GameMap(self.state.get("city_map", {}))

        # Tamaño de celda inicial según ventana
        w = max(1, self.game_map.width)
        h = max(1, self.game_map.height)
        self.tile_size = max(4, min(self.window.width // w, self.window.height // h))

        # --- Clima dinámico ---
        self.weather_manager = WeatherMarkov(api=ApiClient(), seed=42)
        self.weather_manager.apply_to_game_state(self.state)
        self.weather_renderer = WeatherRenderer(self)

        # --- TEXTOS HUD ---
        self.weather_text = arcade.Text(
            "", 10, 10, arcade.color.WHITE, 14
        )
        self.status_text = arcade.Text(
            "Partida en curso",
            self.window.width / 2,
            self.window.height - 40,
            arcade.color.WHITE,
            20,
            anchor_x="center"
        )

    def on_show(self):
        arcade.set_background_color(arcade.color.DARK_GREEN)

    def on_resize(self, width: int, height: int):
        super().on_resize(width, height)
        # Recalcular tamaño de tile al cambiar ventana
        w = max(1, self.game_map.width)
        h = max(1, self.game_map.height)
        self.tile_size = max(4, min(width // w, height // h))
        # Ajustar overlay de clima
        self.weather_renderer.on_resize(width, height)
        # Actualizar posición del texto de estado
        self.status_text.x = width / 2
        self.status_text.y = height - 40

    def on_update(self, dt: float):
        # --- Actualizar clima con Markov ---
        self.weather_manager.update(dt)
        self.weather_manager.apply_to_game_state(self.state)
        # Actualizar renderer del clima
        self.weather_renderer.update(dt, self.state.get("weather_state", {}))

    def on_draw(self):
        self.clear()
        # Dibujar mapa
        self.game_map.draw_debug(tile_size=self.tile_size, draw_grid_lines=True)
        # Overlay de clima
        self.weather_renderer.draw()
        # HUD
        weather = self.state.get("weather_state", {})
        cond = weather.get("summary", "Desconocido")
        temp = weather.get("temperature", "--")
        self.weather_text.text = f"Clima: {cond} {temp}°C"
        self.weather_text.draw()
        self.status_text.draw()


# ========================
# Programa Principal
# ========================
def main():
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    window.show_view(MainMenuView())
    arcade.run()


if __name__ == "__main__":
    main()
