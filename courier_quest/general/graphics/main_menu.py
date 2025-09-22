import arcade
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from run_api.api_client import ApiClient

WIDTH = 800
HEIGHT = 600
TITLE = "Courier Quest"
SPEED = 5

class CourierQuest(arcade.Window):
    def __init__(self,window):
        super().__init__(window)
        self.window = window
        self.api_handler = ApiClient()
        self.city_map = None
        self.jobs = None
        self.weather = None
        self.error_message = None
        self.game_state = "loading"

        bg_path = ":resources:images/miami_synth_parallax/layers/buildings.png"
        self.bg_texture = arcade.load_texture(bg_path)
        self.bg_sprite = arcade.Sprite()
        self.bg_sprite.texture = self.bg_texture
        self.bg_sprite.center_x = self.width // 2
        self.bg_sprite.center_y = self.height // 2
        self.bg_list = arcade.SpriteList()
        self.bg_list.append(self.bg_sprite)
        self._resize_bg_to_cover(self.width, self.height)

        center_x = self.width // 2
        self._txt_loading_title = arcade.Text(
            "Cargando datos...", center_x, self.height // 2, arcade.color.WHITE, 24,
            anchor_x="center"
        )
        self._txt_loading_sub = arcade.Text(
            "Por favor espera...", center_x, self.height // 2 - 40, arcade.color.LIGHT_GRAY, 14,
            anchor_x="center"
        )
        self._txt_menu_title = arcade.Text(
            "Courier Quest - Menú Principal", center_x, self.height - 120, arcade.color.WHITE, 30,
            anchor_x="center"
        )
        self._txt_menu_hint = arcade.Text(
            "[ENTER] Iniciar  |  [Q] Salir", center_x, 60, arcade.color.AQUA, 16,
            anchor_x="center"
        )
        self._txt_hud_source = arcade.Text("", 10, self.height - 20, arcade.color.LIGHT_GRAY, 12)
        self._txt_hud_back = arcade.Text("[ESC] Menú", self.width - 100, self.height - 20,
                                         arcade.color.LIGHT_GRAY, 12)
        self._txt_menu_source = arcade.Text("", 20, 20, arcade.color.LIGHT_GRAY, 12)
        self._txt_menu_jobs = arcade.Text("", 20, 40, arcade.color.LIGHT_GRAY, 12)
        self._txt_menu_weather = arcade.Text("", 20, 60, arcade.color.LIGHT_GRAY, 12)
        self._txt_menu_error = arcade.Text("", center_x, 100, arcade.color.SUNSET_ORANGE, 12,
                                           anchor_x="center")

        def setup(self):
            self.load_game_data()

        def load_game_data(self):
            self.game_state = "loading"
            self.error_message = None
            try:
                self.city_map = self.api_handler.get_city_map()
                self.jobs = self.api_handler.get_jobs()
                self.weather = self.api_handler.get_weather()
                if all([self.city_map, self.jobs, self.weather]):
                    self.game_state = "menu"
                    print("Datos del juego cargados exitosamente!")
                else:
                    self.error_message = "No se pudieron cargar todos los datos del juego."
                    self.game_state = "menu"
                    print("Advertencia:", self.error_message)
            except Exception as e:
                self.error_message = f"Error al cargar datos: {e}"
                self.game_state = "menu"
                print(self.error_message)

            source = "API" if self.api_handler.last_source == "api" else "Caché/Local"
            jobs_count = len(self.jobs) if isinstance(self.jobs, (list, tuple)) else ("OK" if self.jobs else "N/D")
            weather_txt = (self.weather.get("summary", "OK")
                           if isinstance(self.weather, dict)
                           else ("OK" if self.weather else "N/D"))
            self._txt_menu_source.text = f"Datos cargados desde: {source}"
            self._txt_menu_jobs.text = f"Jobs: {jobs_count}"
            self._txt_menu_weather.text = f"Weather: {weather_txt}"
            self._txt_menu_error.text = f"⚠ {self.error_message}" if self.error_message else ""

        def on_draw(self):
            self.clear()
            if self.game_state == "loading":
                self.draw_loading_screen()
            elif self.game_state == "menu":
                self.draw_menu()
            elif self.game_state == "playing":
                self.draw_playing()

        def draw_loading_screen(self):
            self.bg_list.draw()
            self._txt_loading_title.draw()
            self._txt_loading_sub.draw()

        def draw_menu(self):
            self.bg_list.draw()
            self._txt_menu_title.draw()
            self._txt_menu_source.draw()
            self._txt_menu_jobs.draw()
            self._txt_menu_weather.draw()
            if self._txt_menu_error.text:
                self._txt_menu_error.draw()
            self._txt_menu_hint.draw()