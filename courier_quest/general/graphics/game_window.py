import arcade
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from general.run_api.api_handler import APIHandler

WIDTH = 800
HEIGHT = 600
TITLE = "Courier Quest"
SPEED = 5

class CourierQuest(arcade.Window):
    def __init__(self):
        super().__init__(width=WIDTH, height=HEIGHT, title=TITLE, update_rate=1/60)
        arcade.set_background_color(arcade.color.DARK_SLATE_BLUE)
        self.api_handler = APIHandler()
        self.city_map = None
        self.jobs = None
        self.weather = None
        self.error_message = None
        self.game_state = "loading"
        self.player_list = None
        self.player = None

        bg_path = ":resources:images/miami_synth_parallax/layers/buildings.png"
        self.bg_texture = arcade.load_texture(bg_path)
        self.bg_sprite = arcade.Sprite()
        self.bg_sprite.texture = self.bg_texture
        self.bg_sprite.center_x = self.width // 2
        self.bg_sprite.center_y = self.height // 2
        self.bg_list = arcade.SpriteList()
        self.bg_list.append(self.bg_sprite)
        self._resize_bg_to_cover(self.width, self.height)

        self.left_pressed = False
        self.right_pressed = False
        self.up_pressed = False
        self.down_pressed = False

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

    def draw_playing(self):
        self.bg_list.draw()
        if self.player_list:
            self.player_list.draw()
        source = "API" if self.api_handler.last_source == "api" else "Caché/Local"
        self._txt_hud_source.text = f"Origen: {source}"
        self._txt_hud_source.draw()
        self._txt_hud_back.draw()

    def on_update(self, delta_time: float):
        if self.game_state != "playing" or not self.player:
            return
        self.player.change_x = (self.right_pressed - self.left_pressed) * SPEED
        self.player.change_y = (self.up_pressed - self.down_pressed) * SPEED
        self.player_list.update()
        half_w = self.player.width / 2
        half_h = self.player.height / 2
        self.player.center_x = max(half_w, min(self.width - half_w, self.player.center_x))
        self.player.center_y = max(half_h, min(self.height - half_h, self.player.center_y))

    def on_key_press(self, symbol: int, modifiers: int):
        if self.game_state == "menu":
            if symbol == arcade.key.ENTER:
                self.start_playing()
            elif symbol in (arcade.key.Q, arcade.key.ESCAPE):
                arcade.exit()
        elif self.game_state == "playing":
            if symbol == arcade.key.ESCAPE:
                self.game_state = "menu"
                self.left_pressed = self.right_pressed = self.up_pressed = self.down_pressed = False
            if symbol in (arcade.key.A, arcade.key.LEFT):
                self.left_pressed = True
            elif symbol in (arcade.key.D, arcade.key.RIGHT):
                self.right_pressed = True
            elif symbol in (arcade.key.W, arcade.key.UP):
                self.up_pressed = True
            elif symbol in (arcade.key.S, arcade.key.DOWN):
                self.down_pressed = True

    def on_key_release(self, symbol: int, modifiers: int):
        if self.game_state != "playing":
            return
        if symbol in (arcade.key.A, arcade.key.LEFT):
            self.left_pressed = False
        elif symbol in (arcade.key.D, arcade.key.RIGHT):
            self.right_pressed = False
        elif symbol in (arcade.key.W, arcade.key.UP):
            self.up_pressed = False
        elif symbol in (arcade.key.S, arcade.key.DOWN):
            self.down_pressed = False

    def start_playing(self):
        self.player_list = arcade.SpriteList()
        self.player = arcade.Sprite(
            ":resources:images/animated_characters/female_person/femalePerson_idle.png",
            scale=0.5
        )
        self.player.center_x = self.width // 2
        self.player.center_y = self.height // 2
        self.player_list.append(self.player)
        self.left_pressed = self.right_pressed = self.up_pressed = self.down_pressed = False
        self.game_state = "playing"

    def on_resize(self, width: int, height: int):
        super().on_resize(width, height)
        cx = width // 2
        self._txt_loading_title.x = cx
        self._txt_loading_title.y = height // 2
        self._txt_loading_sub.x = cx
        self._txt_loading_sub.y = height // 2 - 40
        self._txt_menu_title.x = cx
        self._txt_menu_title.y = height - 120
        self._txt_menu_hint.x = cx
        self._txt_menu_hint.y = 60
        self._txt_menu_error.x = cx
        self._txt_menu_error.y = 100
        self._txt_hud_source.y = height - 20
        self._txt_hud_back.x = width - 100
        self._txt_hud_back.y = height - 20
        self.bg_sprite.center_x = width // 2
        self.bg_sprite.center_y = height // 2
        self._resize_bg_to_cover(width, height)

    def _resize_bg_to_cover(self, width: int, height: int):
        tex_w = self.bg_texture.width
        tex_h = self.bg_texture.height
        sx = width / tex_w
        sy = height / tex_h
        self.bg_sprite.scale = max(sx, sy)