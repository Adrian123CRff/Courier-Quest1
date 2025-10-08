# ui_view_gui.py
import arcade
import arcade.gui
import os
import time

# --- módulos del juego ---
from run_api.api_client import ApiClient
from run_api.state_initializer import init_game_state
from run_api.save_manager import save_game, load_game, list_saves
from graphics.game_window import MapPlayerView
from game.player_state import PlayerState

# --- score system (tabla de records) ---
# --- para la tabla de récords ---
from game.score_system import ScoreSystem, ScoreEntry


SCREEN_WIDTH = 800
SCREEN_HEIGHT = 800
SCREEN_TITLE = "Courier Quest"


# ========================
# Tema visual y utilidades
# ========================
THEME = {
    "bg_top": (45, 33, 122),        # morado oscuro
    "bg_bottom": (29, 20, 88),      # morado más oscuro
    "panel_fill": (69, 33, 141),    # violeta del panel
    "panel_outline": (137, 76, 249),
    "text": arcade.color.WHITE,
    "subtext": arcade.color.LIGHT_GRAY,
    "btn_green": (16, 158, 67),
    "btn_blue": (31, 106, 255),
    "btn_violet": (150, 54, 255),
    "btn_orange": (245, 88, 24),
}

_bike_texture = None
_bike_sprite = None
_ui_sprite_list = None

def _load_bike_texture():
    global _bike_texture
    if _bike_texture is None:
        try:
            icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                     "resources", "icons", "ciclista.png")
            if os.path.exists(icon_path):
                _bike_texture = arcade.load_texture(icon_path)
        except Exception:
            _bike_texture = None
    return _bike_texture


def _get_ui_sprite_list():
    global _ui_sprite_list
    if _ui_sprite_list is None:
        try:
            _ui_sprite_list = arcade.SpriteList()
        except Exception:
            _ui_sprite_list = None
    return _ui_sprite_list


def _scale_font(base_size, height):
    # Escala de fuente en función de la altura actual; mantiene límites razonables
    factor = max(0.75, min(1.35, height / 800.0))
    return int(base_size * factor)


def _update_ui_button_widths(manager, target_width):
    """Ajusta el ancho de los botones dentro del UIManager."""
    try:
        for child in getattr(manager, "children", []) or []:
            box = getattr(child, "child", None)
            if hasattr(box, "children"):
                for widget in box.children:
                    if hasattr(widget, "width"):
                        widget.width = int(target_width)
    except Exception:
        pass


# ========================
# Transición deslizante entre vistas
# ========================
class SlideTransitionView(arcade.View):
    def __init__(self, from_view: arcade.View, to_view: arcade.View, duration: float = 0.35):
        super().__init__()
        self.from_view = from_view
        self.to_view = to_view
        self.duration = max(0.1, float(duration))
        self.elapsed = 0.0

    def on_draw(self):
        self.clear()
        w, h = self.window.width, self.window.height
        progress = min(1.0, self.elapsed / self.duration)
        dx = int(w * progress)

        # Fondo
        arcade.draw_lrbt_rectangle_filled(0, w, 0, h, (10, 10, 20))

        # Dibuja contenidos de cada vista sin limpiar, usando viewport desplazado
        def _draw_contents(view, offset_x):
            try:
                if hasattr(view, "draw_contents"):
                    left, right, bottom, top = arcade.get_viewport()
                    arcade.set_viewport(left + offset_x, right + offset_x, bottom, top)
                    try:
                        view.draw_contents()
                    finally:
                        arcade.set_viewport(left, right, bottom, top)
                else:
                    # fallback: sin transición
                    pass
            except Exception:
                pass

        _draw_contents(self.from_view, -dx)
        _draw_contents(self.to_view, w - dx)

    def on_update(self, dt):
        self.elapsed += dt
        if self.elapsed >= self.duration:
            self.window.show_view(self.to_view)


def slide_to(current_view: arcade.View, next_view: arcade.View, duration: float = 0.35):
    try:
        current_view.window.show_view(SlideTransitionView(current_view, next_view, duration))
    except Exception:
        current_view.window.show_view(next_view)


def draw_vertical_gradient(width, height, color_top, color_bottom):
    """Dibuja un gradiente vertical sencillo mediante tiras horizontales."""
    steps = 80
    for i in range(steps):
        t = i / (steps - 1)
        r = int(color_top[0] * (1 - t) + color_bottom[0] * t)
        g = int(color_top[1] * (1 - t) + color_bottom[1] * t)
        b = int(color_top[2] * (1 - t) + color_bottom[2] * t)
        strip_h = height / steps
        top = height - (i * strip_h)
        bottom = top - strip_h
        arcade.draw_lrbt_rectangle_filled(0, width, bottom, top, (r, g, b))


def draw_header_and_subtitle(width=None, height=None):
    """Dibuja el encabezado con icono y subtítulo centrados arriba."""
    texture = _load_bike_texture()
    if width is None: width = SCREEN_WIDTH
    if height is None: height = SCREEN_HEIGHT
    cx = width / 2
    title = arcade.Text("Courier Quest", cx, height - 90, THEME["text"], font_size=_scale_font(52, height), anchor_x="center")
    subtitle = arcade.Text("Conviértete en el mejor repartidor de la ciudad",
                           cx, height - 140, THEME["subtext"], font_size=_scale_font(20, height), anchor_x="center")
    if texture:
        global _bike_sprite
        sprite_list = _get_ui_sprite_list()
        if _bike_sprite is None:
            # Crear sprite compatible con Arcade 3.3.x
            _bike_sprite = arcade.Sprite()
            _bike_sprite.texture = texture
            _bike_sprite.scale = 40 / max(texture.width, texture.height)
            if sprite_list is not None:
                sprite_list.append(_bike_sprite)
        _bike_sprite.center_x = cx - title.content_width/2 - 40
        _bike_sprite.center_y = height - 92
        if sprite_list is not None:
            try:
                sprite_list.draw()
            except Exception:
                pass
    else:
        # Fallback emoji si no hay textura
        ix = cx - title.content_width/2 - 40
        iy = height - 92
        arcade.draw_text("🚴", ix - 16, iy - 20, (255, 221, 0), 32)
    title.draw(); subtitle.draw()


def draw_center_panel(width=None, height=None):
    """Dibuja el panel central con borde redondeado simulado."""
    if width is None: width = SCREEN_WIDTH
    if height is None: height = SCREEN_HEIGHT
    panel_w = width * 0.78
    panel_h = height * 0.52
    cx = width / 2
    cy = height / 2
    left = cx - panel_w/2; right = cx + panel_w/2
    bottom = cy - panel_h/2; top = cy + panel_h/2
    arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, THEME["panel_fill"])
    try:
        arcade.draw_lrbt_rectangle_outline(left, right, bottom, top, THEME["panel_outline"], border_width=3)
    except Exception:
        # fallback si no existe la variante LRBT de outline
        arcade.draw_line(left, bottom, right, bottom, THEME["panel_outline"], 3)
        arcade.draw_line(right, bottom, right, top, THEME["panel_outline"], 3)
        arcade.draw_line(right, top, left, top, THEME["panel_outline"], 3)
        arcade.draw_line(left, top, left, bottom, THEME["panel_outline"], 3)


def draw_footer_help(width=None, height=None):
    msg1 = "Usa las flechas o WASD para moverte"
    msg2 = "Presiona ESC para pausar el juego"
    if width is None: width = SCREEN_WIDTH
    if height is None: height = SCREEN_HEIGHT
    font = _scale_font(16, height)
    t1 = arcade.Text(msg1, width/2, 90, THEME["subtext"], font, anchor_x="center")
    t2 = arcade.Text(msg2, width/2, 60, THEME["subtext"], font, anchor_x="center")
    t1.draw(); t2.draw()

# ------------------ Helper: snapshot al guardar ------------------
def build_save_snapshot(game_view, state_obj_or_dict):
    """
    Crea un snapshot del estado visible:
    - player_x / player_y (celda)
    - weather_state (congelado tal cual está)
    - elapsed_seconds (tiempo transcurrido de la simulación)
    - orders (pendientes + aceptados) preservando pickup/dropoff/picked_up/completed
    - player_stats (stamina, reputación, etc.)
    - score_system (dinero, entregas, etc.)
    - inventory (items y peso)
    - alias de compatibilidad y bandera __resume_from_save__
    """
    # 1) Base del estado como dict
    if isinstance(state_obj_or_dict, dict):
        out = dict(state_obj_or_dict)
    elif hasattr(state_obj_or_dict, "to_dict") and callable(state_obj_or_dict.to_dict):
        out = state_obj_or_dict.to_dict()
    else:
        out = {}

    # 2) Posición del jugador (celda)
    try:
        if hasattr(game_view, "player"):
            out["player_x"] = int(getattr(game_view.player, "cell_x", 0))
            out["player_y"] = int(getattr(game_view.player, "cell_y", 0))
            print(f"[SAVE] Posición jugador ({out['player_x']},{out['player_y']})")
    except Exception as e:
        print(f"[WARN] Snapshot posición: {e}")

    # 3) Clima actual (desde WeatherMarkov si está)
    try:
        wm = getattr(game_view, "weather_markov", None)
        ws = {}
        if wm:
            if hasattr(wm, "get_state") and callable(wm.get_state):
                ws = wm.get_state() or {}
            else:
                ws = {
                    "condition": getattr(wm, "current_condition", "clear"),
                    "intensity": getattr(wm, "current_intensity", "light"),
                    "multiplier": float(getattr(wm, "current_multiplier", 1.0)),
                }
        if not ws:
            # fallback: si ya venía en el state
            if isinstance(out, dict):
                ws = out.get("weather_state") or out.get("weather_data") or {}
        if ws:
            out["weather_state"] = ws
            out.setdefault("weather_data", ws)
    except Exception as e:
        print(f"[WARN] Snapshot clima: {e}")

    # 4) Tiempo transcurrido de la simulación
    try:
        gm = getattr(game_view, "game_manager", None)
        if gm and hasattr(gm, "get_game_time"):
            out["elapsed_seconds"] = float(gm.get_game_time())
    except Exception as e:
        print(f"[WARN] Snapshot tiempo: {e}")

    # 5) Pedidos (pendientes + aceptados) con pickup/dropoff
    try:
        # base que pudiera venir del estado
        orders_from_state = out.get("orders") or out.get("jobs_data") or []

        # colas internas de la vista
        incoming = getattr(game_view, "incoming_raw_jobs", []) or []
        rejected = getattr(game_view, "rejected_raw_jobs", []) or []

        # aceptados reales desde el JobManager
        jm = getattr(game_view, "job_manager", None)
        accepted = []
        if jm and hasattr(jm, "all_jobs"):
            for job in jm.all_jobs():
                # si el job expone to_dict lo usamos; si no, construimos a mano
                if hasattr(job, "to_dict") and callable(job.to_dict):
                    d = job.to_dict() or {}
                else:
                    d = {}
                # completar/asegurar todos los campos importantes
                d.setdefault("id",        getattr(job, "id", None))
                d.setdefault("payout",    getattr(job, "payout", 0))
                d.setdefault("weight",    getattr(job, "weight", 0))
                d.setdefault("priority",  getattr(job, "priority", 0))
                d.setdefault("release",   getattr(job, "release_time", getattr(job, "release", 0)))
                d.setdefault("deadline",  getattr(job, "deadline_seconds", getattr(job, "deadline", 0)))
                d.setdefault("accepted",  True)
                d.setdefault("picked_up", bool(getattr(job, "picked_up", False)))
                d.setdefault("completed", bool(getattr(job, "completed", False)))
                # MUY IMPORTANTE: preservar pickup/dropoff
                d.setdefault("pickup",   tuple(getattr(job, "pickup", ())) if getattr(job, "pickup", None) else None)
                d.setdefault("dropoff",  tuple(getattr(job, "dropoff", ())) if getattr(job, "dropoff", None) else None)
                accepted.append(d)

        def _as_dict(x):
            """Normaliza raws (por si son objetos)."""
            if isinstance(x, dict):
                return dict(x)
            if hasattr(x, "to_dict") and callable(x.to_dict):
                return x.to_dict()
            # mínimo: forzar id si existe como atributo
            d = {}
            if hasattr(x, "id"): d["id"] = getattr(x, "id")
            return d

        def _jid(x):
            if isinstance(x, dict):
                return x.get("id") or x.get("job_id") or x.get("req") or str(x)
            return getattr(x, "id", None) or str(x)

        # Mezcla deduplicada: incoming + state + rejected + accepted (accepted sobreescribe)
        merged_by_id = {}
        for src in (orders_from_state, incoming, rejected):
            for r in src:
                rd = _as_dict(r)
                merged_by_id[_jid(rd)] = rd

        for a in accepted:
            merged_by_id[_jid(a)] = a  # los aceptados pisan cualquier duplicado

        merged = [v for k, v in merged_by_id.items() if k is not None]
        out["orders"] = merged
        out["jobs_data"] = merged
        print(f"[SAVE] Pedidos serializados: {len(merged)}")
    except Exception as e:
        print(f"[WARN] Snapshot pedidos: {e}")

    # 6) Estadísticas del jugador (stamina, reputación, etc.)
    try:
        if hasattr(game_view, "player_stats") and game_view.player_stats:
            out["player_stats"] = {
                "stamina": getattr(game_view.player_stats, "stamina", 100.0),
                "reputation": getattr(game_view.player_stats, "reputation", 70),
                "consecutive_on_time_deliveries": getattr(game_view.player_stats, "consecutive_on_time_deliveries", 0),
                "first_late_delivery_of_day": getattr(game_view.player_stats, "first_late_delivery_of_day", True),
                "is_resting": getattr(game_view.player_stats, "is_resting", False),
                "is_at_rest_point": getattr(game_view.player_stats, "is_at_rest_point", False),
                "last_rest_time": getattr(game_view.player_stats, "last_rest_time", time.time()),
                "_idle_recover_accum": getattr(game_view.player_stats, "_idle_recover_accum", 0.0)
            }
            print(f"[SAVE] Player stats capturadas: stamina={out['player_stats']['stamina']}, reputation={out['player_stats']['reputation']}")
    except Exception as e:
        print(f"[WARN] Snapshot player_stats: {e}")

    # 7) Score system (dinero, entregas, etc.)
    try:
        if hasattr(game_view, "score_system") and game_view.score_system:
            out["score_system"] = {
                "total_money": getattr(game_view.score_system, "total_money", 0.0),
                "deliveries_completed": getattr(game_view.score_system, "deliveries_completed", 0),
                "on_time_deliveries": getattr(game_view.score_system, "on_time_deliveries", 0),
                "cancellations": getattr(game_view.score_system, "cancellations", 0),
                "lost_packages": getattr(game_view.score_system, "lost_packages", 0),
                "game_start_time": getattr(game_view.score_system, "game_start_time", time.time()),
                "game_duration": getattr(game_view.score_system, "game_duration", 900)
            }
            print(f"[SAVE] Score system capturado: money={out['score_system']['total_money']}, deliveries={out['score_system']['deliveries_completed']}")
    except Exception as e:
        print(f"[WARN] Snapshot score_system: {e}")

    # 8) Inventario (items y peso)
    try:
        if hasattr(game_view, "inventory") and game_view.inventory:
            out["inventory"] = {
                "items": getattr(game_view.inventory, "items", []),
                "current_weight": getattr(game_view.inventory, "current_weight", 0.0),
                "max_weight": getattr(game_view.inventory, "max_weight", 50.0)
            }
            print(f"[SAVE] Inventario capturado: {len(out['inventory']['items'])} items, weight={out['inventory']['current_weight']}")
    except Exception as e:
        print(f"[WARN] Snapshot inventory: {e}")

    # 9) Alias de compatibilidad
    if "map_data" in out and "city_map" not in out:
        out["city_map"] = out["map_data"]
    if "city_map" in out and "map_data" not in out:
        out["map_data"] = out["city_map"]
    if "weather_state" in out and "weather_data" not in out:
        out["weather_data"] = out["weather_state"]
    if "jobs_data" in out and "orders" not in out:
        out["orders"] = out["jobs_data"]

    # 10) Bandera para reanudar
    out["__resume_from_save__"] = True
    return out



# ========================
# Vista: Menú Principal
# ========================
class MainMenuView(arcade.View):
    def __init__(self):
        super().__init__()
        self.manager = arcade.gui.UIManager()
        v_box = arcade.gui.UIBoxLayout(vertical=True, space_between=18)

        start_btn = arcade.gui.UIFlatButton(text="Entrar al Menú", width=380)
        v_box.add(start_btn)
        @start_btn.event("on_click")
        def on_click_start(event):
            slide_to(self, GameMenuView())

        quit_btn = arcade.gui.UIFlatButton(text="Salir", width=260)
        v_box.add(quit_btn)
        @quit_btn.event("on_click")
        def on_click_quit(event):
            arcade.close_window()

        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(child=v_box, anchor_x="center_x", anchor_y="center_y")
        self.manager.add(anchor)

        self._dummy_text = arcade.Text("", 0, 0, arcade.color.WHITE, font_size=1)

    def on_show(self):
        arcade.set_background_color(arcade.color.DARK_BLUE_GRAY)
    def on_show_view(self): self.manager.enable()
    def on_hide_view(self): self.manager.disable()
    def on_draw(self):
        self.clear()
        w, h = self.window.width, self.window.height
        draw_vertical_gradient(w, h, THEME["bg_top"], THEME["bg_bottom"])
        draw_header_and_subtitle(w, h)
        draw_center_panel(w, h)
        draw_footer_help(w, h)
        self.manager.draw()
        
    def on_resize(self, width, height):
        super().on_resize(width, height)
        new_w = max(260, min(520, int(width * 0.32)))
        _update_ui_button_widths(self.manager, new_w)


# ========================
# Vista: Menú de Juego
# ========================
class GameMenuView(arcade.View):
    def __init__(self):
        super().__init__()
        self.manager = arcade.gui.UIManager()
        v_box = arcade.gui.UIBoxLayout(vertical=True, space_between=20)

        new_btn = arcade.gui.UIFlatButton(text="Nueva Partida", width=380)
        v_box.add(new_btn)
        @new_btn.event("on_click")
        def on_new(event): slide_to(self, NewGameMenuView())

        load_btn = arcade.gui.UIFlatButton(text="Cargar Partida", width=380)
        v_box.add(load_btn)
        @load_btn.event("on_click")
        def on_load(event): slide_to(self, LoadMenuView())

        # --- Nuevo botón: Tabla de records ---
        records_btn = arcade.gui.UIFlatButton(text="Tabla de records", width=380)
        v_box.add(records_btn)
        @records_btn.event("on_click")
        def on_records(event):
            slide_to(self, RecordsView())

        instr_btn = arcade.gui.UIFlatButton(text="Instrucciones", width=380)
        v_box.add(instr_btn)
        @instr_btn.event("on_click")
        def on_instr(event): slide_to(self, InstructionsView())

        back_btn = arcade.gui.UIFlatButton(text="Retroceder", width=260)
        v_box.add(back_btn)
        @back_btn.event("on_click")
        def on_back(event): slide_to(self, MainMenuView())

        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(child=v_box, anchor_x="center_x", anchor_y="center_y")
        self.manager.add(anchor)

        self.menu_text = arcade.Text("", 0, 0, arcade.color.WHITE, font_size=1)

    def on_show_view(self): self.manager.enable()
    def on_hide_view(self): self.manager.disable()
    def on_show(self): arcade.set_background_color(arcade.color.DARK_SLATE_GRAY)
    def on_draw(self):
        self.clear()
        w, h = self.window.width, self.window.height
        # fondo y cabecera estilo screenshot
        draw_vertical_gradient(w, h, THEME["bg_top"], THEME["bg_bottom"])
        draw_header_and_subtitle(w, h)
        draw_center_panel(w, h)
        draw_footer_help(w, h)
        self.manager.draw()

    def on_resize(self, width, height):
        super().on_resize(width, height)
        # Ancho relativo para botones con límites razonables
        new_w = max(260, min(520, int(width * 0.32)))
        _update_ui_button_widths(self.manager, new_w)


# ========================
# Vista: Instrucciones
# ========================
class InstructionsView(arcade.View):
    def __init__(self):
        super().__init__()
        self.manager = arcade.gui.UIManager()
        v_box = arcade.gui.UIBoxLayout(vertical=True, space_between=10)
        back_btn = arcade.gui.UIFlatButton(text="Volver", width=200)
        v_box.add(back_btn)
        @back_btn.event("on_click")
        def on_back(event):
            slide_to(self, GameMenuView())

        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(child=v_box, anchor_x="center_x", anchor_y="bottom", align_y=20)
        self.manager.add(anchor)

        # Textos principales
        self.header = arcade.Text("Instrucciones", SCREEN_WIDTH/2, SCREEN_HEIGHT - 100,
                                  THEME["text"], font_size=30, anchor_x="center")
        self.lines = [
            "Objetivo: completa entregas y gana reputación y dinero.",
            "Movimiento: WASD o Flechas.",
            "Pausa: ESC (abre menú de pausa).",
            "Acepta pedidos desde el panel derecho y planifica tu ruta.",
            "El clima afecta tu velocidad (ver panel superior).",
        ]

    def on_show(self):
        arcade.set_background_color(arcade.color.DARK_BLUE_GRAY)

    def on_show_view(self):
        self.manager.enable()

    def on_hide_view(self):
        self.manager.disable()

    def on_draw(self):
        self.clear()
        w, h = self.window.width, self.window.height
        # fondo con gradiente y panel para consistencia visual (sin cabecera global)
        draw_vertical_gradient(w, h, THEME["bg_top"], THEME["bg_bottom"])
        draw_center_panel(w, h)
        y = h - 170
        self.header.draw()
        for line in self.lines:
            arcade.draw_text(line, 120, y - 40, THEME["text"], _scale_font(16, h))
            y -= 30
        draw_footer_help(w, h)
        self.manager.draw()

    def on_resize(self, width, height):
        super().on_resize(width, height)
        new_w = max(220, min(360, int(width * 0.22)))
        _update_ui_button_widths(self.manager, new_w)


# ========================
# Submenú: Nueva Partida
# ========================
class NewGameMenuView(arcade.View):
    def __init__(self):
        super().__init__()
        self.manager = arcade.gui.UIManager()
        v_box = arcade.gui.UIBoxLayout(vertical=True, space_between=15)

        self.saves = list_saves()
        for i in range(1, 4):
            slot = f"slot{i}.sav"
            txt = f"Slot {i}: {'Ocupado' if slot in self.saves else 'Vacío'}"
            btn = arcade.gui.UIFlatButton(text=txt, width=380); v_box.add(btn)
            @btn.event("on_click")
            def on_click(event, slot=slot): self.confirm_overwrite(slot)

        new_slot_btn = arcade.gui.UIFlatButton(text="Crear Nuevo Slot", width=380)
        v_box.add(new_slot_btn)
        @new_slot_btn.event("on_click")
        def on_new_slot(event):
            new_index = len(self.saves) + 1
            new_slot = f"slot{new_index}.sav"
            self.create_game(new_slot)

        back_btn = arcade.gui.UIFlatButton(text="Volver", width=260)
        v_box.add(back_btn)
        @back_btn.event("on_click")
        def on_back(event): slide_to(self, GameMenuView())

        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(child=v_box, anchor_x="center_x", anchor_y="center_y")
        self.manager.add(anchor)

    def confirm_overwrite(self, slot):
        self.manager.clear()
        confirm_box = arcade.gui.UIBoxLayout(vertical=True, space_between=15)
        confirm_text = arcade.Text(
            f"El {slot} ya existe.\n¿Deseas sobreescribirlo?",
            SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 60,
            arcade.color.WHITE, font_size=18, anchor_x="center"
        )
        yes_btn = arcade.gui.UIFlatButton(text="Sí, sobreescribir", width=200)
        no_btn = arcade.gui.UIFlatButton(text="Cancelar", width=200)
        confirm_box.add(yes_btn); confirm_box.add(no_btn)

        @yes_btn.event("on_click")
        def on_yes(event): self.create_game(slot)
        @no_btn.event("on_click")
        def on_no(event): slide_to(self, NewGameMenuView())

        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(child=confirm_box, anchor_x="center_x", anchor_y="center_y")
        self.manager.add(anchor)
        self.confirm_text = confirm_text

    def create_game(self, slot):
        try:
            api = ApiClient()
            state = init_game_state(api)
            save_game(state, slot)
            print(f"[INFO] Nueva partida creada en {slot}")
            self.window.show_view(MapPlayerViewWithPause(state, slot))
        except Exception as e:
            print(f"[UI] Error creando partida en {slot}: {e}")

    def on_show_view(self): self.manager.enable()
    def on_hide_view(self): self.manager.disable()
    def on_show(self): arcade.set_background_color(arcade.color.DARK_BLUE_GRAY)
    def on_draw(self):
        self.clear()
        w, h = self.window.width, self.window.height
        draw_vertical_gradient(w, h, THEME["bg_top"], THEME["bg_bottom"])
        header = arcade.Text("Nueva Partida", w/2, h - 90, THEME["text"], 36, anchor_x="center")
        draw_header_and_subtitle(w, h)
        draw_center_panel(w, h)
        header.draw()
        if hasattr(self, "confirm_text"): self.confirm_text.draw()
        draw_footer_help(w, h)
        self.manager.draw()

    def on_resize(self, width, height):
        super().on_resize(width, height)
        new_w = max(260, min(520, int(width * 0.32)))
        _update_ui_button_widths(self.manager, new_w)


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
            self.empty_text = arcade.Text(
                "No hay partidas guardadas.", SCREEN_WIDTH/2, SCREEN_HEIGHT/2,
                arcade.color.LIGHT_GRAY, font_size=20, anchor_x="center"
            )
        else:
            saves = sorted(saves, key=lambda x: int(x.replace("slot", "").replace(".sav", "")))
            for slot in saves:
                btn = arcade.gui.UIFlatButton(text=f"Cargar {slot}", width=380); v_box.add(btn)
                @btn.event("on_click")
                def on_click(event, slot=slot):
                    try:
                        data = load_game(slot)
                        if not data:
                            print(f"[INFO] No se pudo cargar {slot}"); return

                        # alias
                        if "map_data" not in data and "city_map" in data: data["map_data"] = data["city_map"]
                        if "city_map" not in data and "map_data" in data: data["city_map"] = data["map_data"]
                        if "weather_data" not in data and "weather_state" in data: data["weather_data"] = data["weather_state"]
                        if "weather_state" not in data and "weather_data" in data: data["weather_state"] = data["weather_data"]
                        if "jobs_data" not in data and "orders" in data: data["jobs_data"] = data["orders"]
                        if "orders" not in data and "jobs_data" in data: data["orders"] = data["jobs_data"]

                        # reconstrucción PlayerState (si lo usas internamente)
                        state = PlayerState().from_dict(data)
                        state.map_data = data.get("map_data", {})
                        state.city_map = data.get("city_map", state.map_data)
                        jobs_list = data.get("jobs_data", []) or data.get("orders", []) or data.get("jobs", [])
                        state.jobs_data = jobs_list; state.orders = jobs_list
                        weather = data.get("weather_data", {}) or data.get("weather_state", {})
                        state.weather_data = weather; state.weather_state = weather
                        if "player_x" in data and "player_y" in data:
                            state.player_x = data["player_x"]; state.player_y = data["player_y"]

                        # reanudación
                        data["__resume_from_save__"] = True
                        state.__resume_from_save__ = True
                        if "elapsed_seconds" in data: state.elapsed_seconds = data["elapsed_seconds"]

                        self.window.show_view(MapPlayerViewWithPause(state, slot))
                    except Exception as e:
                        print(f"[UI] Error cargando {slot}: {e}")

        back_btn = arcade.gui.UIFlatButton(text="Volver", width=260); v_box.add(back_btn)
        @back_btn.event("on_click")
        def on_back(event): self.window.show_view(GameMenuView())

        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(child=v_box, anchor_x="center_x", anchor_y="center_y"); self.manager.add(anchor)

    def on_show_view(self): self.manager.enable()
    def on_hide_view(self): self.manager.disable()
    def on_show(self): arcade.set_background_color(arcade.color.DARK_BLUE_GRAY)
    def on_draw(self):
        self.clear()
        w, h = self.window.width, self.window.height
        draw_vertical_gradient(w, h, THEME["bg_top"], THEME["bg_bottom"])
        # título y panel central (sin cabecera global para evitar solapes)
        header = arcade.Text("Cargar Partida", w/2, h - 90, THEME["text"], 36, anchor_x="center")
        draw_center_panel(w, h)
        header.draw()
        if hasattr(self, "empty_text"): self.empty_text.draw()
        draw_footer_help(w, h)
        self.manager.draw()

    def on_resize(self, width, height):
        super().on_resize(width, height)
        new_w = max(260, min(520, int(width * 0.32)))
        _update_ui_button_widths(self.manager, new_w)


# ========================
# NUEVA VISTA: Tabla de records
# ========================
class RecordsView(arcade.View):
    """
    Muestra la tabla de records (highscores) usando ScoreSystem.
    Tiene un botón 'Volver' que regresa a GameMenuView.
    """
    def __init__(self):
        super().__init__()
        self.manager = arcade.gui.UIManager()
        self.score_system = ScoreSystem(save_dir="saves")  # usa el mismo directorio por defecto
        self.scores = self.score_system.get_high_scores(limit=10)  # lista de ScoreEntry

        # UI: sólo el botón volver (abajo)
        v_box = arcade.gui.UIBoxLayout(vertical=True, space_between=10)
        back_btn = arcade.gui.UIFlatButton(text="Volver", width=200)
        v_box.add(back_btn)
        @back_btn.event("on_click")
        def on_back(event):
            self.window.show_view(GameMenuView())

        anchor = arcade.gui.UIAnchorLayout()
        # ubicar el botón en la parte inferior central
        anchor.add(child=v_box, anchor_x="center_x", anchor_y="bottom", align_y=20)
        self.manager.add(anchor)

        # precomputar textos (si hay)
        self.header = arcade.Text(
            "Tabla de records 🏆",
            SCREEN_WIDTH/2, SCREEN_HEIGHT - 80,
            arcade.color.WHITE, font_size=28, anchor_x="center"
        )

        # si no hay scores, mostrar mensaje
        if not self.scores:
            self.empty_text = arcade.Text(
                "No hay records aún. Disfruta de unas partidas y vuelve luego!", SCREEN_WIDTH/2, SCREEN_HEIGHT/2,
                arcade.color.LIGHT_GRAY, font_size=18, anchor_x="center"
            )
        else:
            # preparar líneas para dibujar
            self.table_lines = []
            # encabezados de columnas
            header_line = f"{'Rk':<3} {'Jugador':<14} {'Score':>6} {'$':>8} {'Rep':>5} {'Entregas':>9} {'A tiempo':>8} {'Fecha':>19}"
            self.table_lines.append(header_line)
            # cada entry
            for idx, e in enumerate(self.scores, start=1):
                name = getattr(e, "player_name", "Unknown")[:14]
                score = getattr(e, "score", 0)
                money = getattr(e, "money_earned", 0.0)
                rep = getattr(e, "reputation", 0.0)
                deliveries = getattr(e, "deliveries_completed", 0)
                on_time = getattr(e, "on_time_deliveries", 0)
                date = getattr(e, "date", "")
                line = f"{idx:<3} {name:<14} {score:>6} {money:>8.2f} {rep:>5.0f} {deliveries:>9} {on_time:>8} {date:>19}"
                self.table_lines.append(line)

    def on_show(self):
        arcade.set_background_color(arcade.color.DARK_BLUE_GRAY)

    def on_show_view(self):
        self.manager.enable()

    def on_hide_view(self):
        self.manager.disable()

    def on_draw(self):
        self.clear()
        w, h = self.window.width, self.window.height
        draw_vertical_gradient(w, h, THEME["bg_top"], THEME["bg_bottom"])
        draw_center_panel(w, h)
        # dibujar encabezado
        self.header.draw()
        # dibujar tabla o mensaje vacío sobre el panel
        if hasattr(self, "empty_text"):
            self.empty_text.draw()
        else:
            start_y = h - 150
            line_h = 24
            left_margin = 60
            arcade.draw_text(self.table_lines[0], left_margin, start_y, arcade.color.LIGHT_GRAY, _scale_font(14, h), font_name="monospace")
            for i, line in enumerate(self.table_lines[1:], start=1):
                y = start_y - (i * line_h)
                arcade.draw_text(line, left_margin, y, arcade.color.WHITE, _scale_font(14, h), font_name="monospace")
        draw_footer_help(w, h)
        self.manager.draw()


# ========================
# Menú de Pausa
# ========================
class PauseMenuView(arcade.View):
    def __init__(self, game_view, state, slot):
        super().__init__()
        self.game_view = game_view; self.state = state; self.slot = slot
        self.manager = arcade.gui.UIManager()
        v_box = arcade.gui.UIBoxLayout(vertical=True, space_between=20)

        resume_btn = arcade.gui.UIFlatButton(text="Reanudar", width=200); v_box.add(resume_btn)
        @resume_btn.event("on_click")
        def on_resume(event): self.window.show_view(self.game_view)

        save_btn = arcade.gui.UIFlatButton(text="Guardar", width=200); v_box.add(save_btn)
        @save_btn.event("on_click")
        def on_save(event):
            try:
                snapshot = build_save_snapshot(self.game_view, self.state)
                save_game(snapshot, self.slot)
                print(f"[INFO] Partida guardada en {self.slot}")
            except Exception as e:
                print(f"[UI] Error al guardar: {e}")

        exit_btn = arcade.gui.UIFlatButton(text="Salir", width=200); v_box.add(exit_btn)
        @exit_btn.event("on_click")
        def on_exit(event): self.window.show_view(MainMenuView())

        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(child=v_box, anchor_x="center_x", anchor_y="center_y"); self.manager.add(anchor)

    def on_show(self): arcade.set_background_color(arcade.color.DARK_BLUE_GRAY); self.manager.enable()
    def on_hide_view(self): self.manager.disable()
    def on_draw(self): self.clear(); self.manager.draw()
    def on_mouse_press(self,x,y,b,m): self.manager.on_mouse_press(x,y,b,m)
    def on_mouse_release(self,x,y,b,m): self.manager.on_mouse_release(x,y,b,m)
    def on_mouse_motion(self,x,y,dx,dy): self.manager.on_mouse_motion(x,y,dx,dy)
    def on_key_press(self, key, modifiers):
        if key == arcade.key.ESCAPE: self.window.show_view(self.game_view)


# ========================
# Vista del juego con pausa integrada
# ========================
class MapPlayerViewWithPause(MapPlayerView):
    def __init__(self, state, slot):
        super().__init__(state)
        self.state = state; self.slot = slot

        # Restaurar posición si existe
        try:
            if hasattr(self, "player"):
                px = getattr(state, "player_x", None); py = getattr(state, "player_y", None)
                if px is not None and py is not None:
                    if hasattr(self.player, "set_cell"): self.player.set_cell(int(px), int(py))
                    else: self.player.cell_x = int(px); self.player.cell_y = int(py)
                    print(f"[LOAD] Posición del jugador restaurada en celda ({px}, {py})")
        except Exception as e:
            print(f"[WARN] No se pudo restaurar la posición: {e}")

        # UI botón de pausa
        self.manager = arcade.gui.UIManager(); self.manager.enable()
        anchor = arcade.gui.UIAnchorLayout()
        pause_btn = arcade.gui.UIFlatButton(text="☰ Menú", width=100)
        anchor.add(child=pause_btn, anchor_x="right", anchor_y="top", align_x=-10, align_y=-10)
        @pause_btn.event("on_click")
        def on_pause(event): self.window.show_view(PauseMenuView(self, self.state, self.slot))
        self.manager.add(anchor)

    def on_draw(self): super().on_draw(); self.manager.draw()
    def on_key_press(self, key, modifiers):
        if key == arcade.key.ESCAPE: self.window.show_view(PauseMenuView(self, self.state, self.slot))
        else: super().on_key_press(key, modifiers)
    def on_mouse_press(self,x,y,b,m): self.manager.on_mouse_press(x,y,b,m)
    def on_mouse_release(self,x,y,b,m): self.manager.on_mouse_release(x,y,b,m)
    def on_mouse_motion(self,x,y,dx,dy): self.manager.on_mouse_motion(x,y,dx,dy)


def main():
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    window.show_view(MainMenuView())
    arcade.run()


if __name__ == "__main__":
    main()
