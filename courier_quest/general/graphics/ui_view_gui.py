import arcade
import arcade.gui
import os

# --- tus módulos del juego ---
from run_api.api_client import APIDataManager
from run_api.state_initializer import init_game_state
from run_api.save_manager import save_game, load_game, list_saves
from graphics.game_window import MapPlayerView   # ventana real del juego
from game.player_state import PlayerState        # estado del jugador


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

        continue_btn = arcade.gui.UIFlatButton(text="Continuar", width=200)
        v_box.add(continue_btn)

        @continue_btn.event("on_click")
        def on_click_continue(event):
            self.window.show_view(GameMenuView())

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

        # Nueva partida
        new_btn = arcade.gui.UIFlatButton(text="Nueva Partida", width=200)
        v_box.add(new_btn)

        @new_btn.event("on_click")
        def on_new(event):
            self.window.show_view(NewGameMenuView())

        # Cargar partida
        load_btn = arcade.gui.UIFlatButton(text="Cargar Partida", width=200)
        v_box.add(load_btn)

        @load_btn.event("on_click")
        def on_load(event):
            self.window.show_view(LoadMenuView())

        # Retroceder
        back_btn = arcade.gui.UIFlatButton(text="Retroceder", width=200)
        v_box.add(back_btn)

        @back_btn.event("on_click")
        def on_back(event):
            self.window.show_view(MainMenuView())

        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(child=v_box, anchor_x="center_x", anchor_y="center_y")
        self.manager.add(anchor)

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
# Submenú: Nueva Partida
# ========================
class NewGameMenuView(arcade.View):
    def __init__(self):
        super().__init__()
        self.manager = arcade.gui.UIManager()
        v_box = arcade.gui.UIBoxLayout(vertical=True, space_between=15)

        self.saves = list_saves()

        # Mostrar slots existentes o vacíos
        for i in range(1, 4):
            slot = f"slot{i}.sav"
            txt = f"Slot {i}: {'Ocupado' if slot in self.saves else 'Vacío'}"
            btn = arcade.gui.UIFlatButton(text=txt, width=250)
            v_box.add(btn)

            @btn.event("on_click")
            def on_click(event, slot=slot):
                self.confirm_overwrite(slot)

        # Opción para crear un nuevo slot adicional
        new_slot_btn = arcade.gui.UIFlatButton(text="Crear Nuevo Slot", width=250)
        v_box.add(new_slot_btn)

        @new_slot_btn.event("on_click")
        def on_new_slot(event):
            new_index = len(self.saves) + 1
            new_slot = f"slot{new_index}.sav"
            self.create_game(new_slot)

        # Volver
        back_btn = arcade.gui.UIFlatButton(text="Volver", width=200)
        v_box.add(back_btn)

        @back_btn.event("on_click")
        def on_back(event):
            self.window.show_view(GameMenuView())

        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(child=v_box, anchor_x="center_x", anchor_y="center_y")
        self.manager.add(anchor)

    def confirm_overwrite(self, slot):
        """Pregunta al jugador si desea sobreescribir la partida."""
        self.manager.clear()
        confirm_box = arcade.gui.UIBoxLayout(vertical=True, space_between=15)

        confirm_text = arcade.Text(
            f"El {slot} ya existe.\n¿Deseas sobreescribirlo?",
            SCREEN_WIDTH / 2,
            SCREEN_HEIGHT / 2 + 60,
            arcade.color.WHITE,
            font_size=18,
            anchor_x="center"
        )

        yes_btn = arcade.gui.UIFlatButton(text="Sí, sobreescribir", width=200)
        no_btn = arcade.gui.UIFlatButton(text="Cancelar", width=200)
        confirm_box.add(yes_btn)
        confirm_box.add(no_btn)

        @yes_btn.event("on_click")
        def on_yes(event):
            self.create_game(slot)

        @no_btn.event("on_click")
        def on_no(event):
            self.window.show_view(NewGameMenuView())

        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(child=confirm_box, anchor_x="center_x", anchor_y="center_y")
        self.manager.add(anchor)

        self.confirm_text = confirm_text

    def create_game(self, slot):
        """Crea una nueva partida en el slot indicado."""
        try:
            api = APIDataManager()
            state = init_game_state(api)
            save_game(state, slot)
            print(f"[INFO] Nueva partida creada en {slot}")
            self.window.show_view(MapPlayerViewWithPause(state, slot))
        except Exception as e:
            print(f"[UI] Error creando partida en {slot}: {e}")

    def on_show_view(self):
        self.manager.enable()

    def on_hide_view(self):
        self.manager.disable()

    def on_show(self):
        arcade.set_background_color(arcade.color.DARK_BLUE_GRAY)

    def on_draw(self):
        self.clear()
        self.manager.draw()
        if hasattr(self, "confirm_text"):
            self.confirm_text.draw()


# ========================
# Submenú: Cargar Partida
# ========================
class LoadMenuView(arcade.View):
    def __init__(self):
        super().__init__()
        self.manager = arcade.gui.UIManager()
        v_box = arcade.gui.UIBoxLayout(vertical=True, space_between=15)

        saves = list_saves()
        if not saves:
            empty_text = arcade.Text(
                "No hay partidas guardadas.",
                SCREEN_WIDTH / 2,
                SCREEN_HEIGHT / 2,
                arcade.color.LIGHT_GRAY,
                font_size=20,
                anchor_x="center"
            )
            self.empty_text = empty_text
        else:
            # Ordenar los slots (slot1, slot2, ...)
            saves = sorted(saves, key=lambda x: int(x.replace("slot", "").replace(".sav", "")))

            for slot in saves:
                btn = arcade.gui.UIFlatButton(text=f"Cargar {slot}", width=250)
                v_box.add(btn)

                @btn.event("on_click")
                def on_click(event, slot=slot):
                    try:
                        data = load_game(slot)
                        if data:
                            state = PlayerState()
                            state.city_map = data.get("city_map", {})
                            state.jobs = data.get("jobs", [])
                            state.weather_state = data.get("weather_state", {})
                            self.window.show_view(MapPlayerViewWithPause(state, slot))
                        else:
                            print(f"[INFO] No se pudo cargar {slot}")
                    except Exception as e:
                        print(f"[UI] Error cargando {slot}: {e}")

        # Botón volver
        back_btn = arcade.gui.UIFlatButton(text="Volver", width=200)
        v_box.add(back_btn)

        @back_btn.event("on_click")
        def on_back(event):
            self.window.show_view(GameMenuView())

        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(child=v_box, anchor_x="center_x", anchor_y="center_y")
        self.manager.add(anchor)

    def on_show_view(self):
        self.manager.enable()

    def on_hide_view(self):
        self.manager.disable()

    def on_show(self):
        arcade.set_background_color(arcade.color.DARK_BLUE_GRAY)

    def on_draw(self):
        self.clear()
        self.manager.draw()
        if hasattr(self, "empty_text"):
            self.empty_text.draw()


# ========================
# Menú de Pausa
# ========================
class PauseMenuView(arcade.View):
    def __init__(self, game_view, state, slot):
        super().__init__()
        self.game_view = game_view
        self.state = state
        self.slot = slot

        self.manager = arcade.gui.UIManager()
        v_box = arcade.gui.UIBoxLayout(vertical=True, space_between=20)

        # Botón Reanudar
        resume_btn = arcade.gui.UIFlatButton(text="Reanudar", width=200)
        v_box.add(resume_btn)

        @resume_btn.event("on_click")
        def on_resume(event):
            self.window.show_view(self.game_view)

        # Botón Guardar
        save_btn = arcade.gui.UIFlatButton(text="Guardar", width=200)
        v_box.add(save_btn)

        @save_btn.event("on_click")
        def on_save(event):
            try:
                save_game(self.state, self.slot)
                print(f"[INFO] Partida guardada en {self.slot}")
            except Exception as e:
                print(f"[UI] Error al guardar: {e}")

        # Botón Salir (sin guardar)
        exit_btn = arcade.gui.UIFlatButton(text="Salir", width=200)
        v_box.add(exit_btn)

        @exit_btn.event("on_click")
        def on_exit(event):
            self.window.show_view(MainMenuView())

        # Layout central
        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(child=v_box, anchor_x="center_x", anchor_y="center_y")
        self.manager.add(anchor)

    def on_show(self):
        arcade.set_background_color(arcade.color.DARK_BLUE_GRAY)
        self.manager.enable()

    def on_hide_view(self):
        self.manager.disable()

    def on_draw(self):
        self.clear()
        self.manager.draw()

    # Reenviar eventos al manager
    def on_mouse_press(self, x, y, button, modifiers):
        self.manager.on_mouse_press(x, y, button, modifiers)

    def on_mouse_release(self, x, y, button, modifiers):
        self.manager.on_mouse_release(x, y, button, modifiers)

    def on_mouse_motion(self, x, y, dx, dy):
        self.manager.on_mouse_motion(x, y, dx, dy)

    def on_key_press(self, key, modifiers):
        if key == arcade.key.ESCAPE:
            self.window.show_view(self.game_view)



# ========================
# Vista del juego con pausa integrada
# ========================
class MapPlayerViewWithPause(MapPlayerView):
    def __init__(self, state, slot):
        super().__init__(state)
        self.state = state
        self.slot = slot

        # --- UI Manager para el botón ---
        self.manager = arcade.gui.UIManager()
        self.manager.enable()

        # Layout con el botón en la esquina superior derecha
        anchor = arcade.gui.UIAnchorLayout()

        pause_btn = arcade.gui.UIFlatButton(text="☰ Menú", width=100)
        anchor.add(child=pause_btn, anchor_x="right", anchor_y="top", align_x=-10, align_y=-10)

        @pause_btn.event("on_click")
        def on_pause(event):
            pause_menu = PauseMenuView(self, self.state, self.slot)
            self.window.show_view(pause_menu)

        self.manager.add(anchor)

    def on_draw(self):
        super().on_draw()  # dibuja el mapa del juego
        self.manager.draw()  # dibuja el botón encima

    def on_key_press(self, key, modifiers):
        if key == arcade.key.ESCAPE:
            pause_menu = PauseMenuView(self, self.state, self.slot)
            self.window.show_view(pause_menu)
        else:
            super().on_key_press(key, modifiers)

    # Necesario para que el botón reciba eventos
    def on_mouse_press(self, x, y, button, modifiers):
        self.manager.on_mouse_press(x, y, button, modifiers)

    def on_mouse_release(self, x, y, button, modifiers):
        self.manager.on_mouse_release(x, y, button, modifiers)

    def on_mouse_motion(self, x, y, dx, dy):
        self.manager.on_mouse_motion(x, y, dx, dy)


# ========================
# Programa Principal
# ========================
def main():
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    window.show_view(MainMenuView())
    arcade.run()


if __name__ == "__main__":
    main()
