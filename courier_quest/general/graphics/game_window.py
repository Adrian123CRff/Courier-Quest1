import time
import arcade
from arcade import View, Text
from typing import List, Any

from run_api.api_client import ApiClient
from .map_manager import GameMap, FLIP_Y
from game.player_manager import Player
from game.player_stats import PlayerStats
from game.weather_markov import WeatherMarkov
from graphics.weather_renderer import WeatherRenderer

from game.game_manager import GameManager
from game.jobs_manager import JobManager

# --- NUEVO: import robusto de Inventory para partidas nuevas ---
try:
    from game.inventory import Inventory  # si existe, lo usamos
except Exception:
    Inventory = None  # seguimos funcionando aunque no esté disponible

SCREEN_WIDTH = 1150
SCREEN_HEIGHT = 800
MAP_WIDTH = 730
TILE_SIZE = 24


def _draw_rect_lrbt_filled(left: float, right: float, bottom: float, top: float, color):
    pts = [(left, bottom), (right, bottom), (right, top), (left, top)]
    arcade.draw_polygon_filled(pts, color)


def _draw_rect_lrbt_outline(left: float, right: float, bottom: float, top: float, color, border_width=2):
    pts = [(left, bottom), (right, bottom), (right, top), (left, top)]
    arcade.draw_polygon_outline(pts, color, border_width)


class MapPlayerView(View):
    def __init__(self, state) -> None:
        super().__init__()
        self.state = state or {}

        self.game_manager: Any = None
        self.job_manager: Any = None
        self.score_system: Any = None

        # extras: navegación/orden de inventario
        self.inventory_view_index = 0
        self.inventory_sort_mode = "normal"

        # player stats
        if isinstance(self.state, dict):
            if "player_stats" not in self.state or self.state.get("player_stats") is None:
                self.state["player_stats"] = PlayerStats()
            self.player_stats: PlayerStats = self.state["player_stats"]
        else:
            self.player_stats = getattr(self.state, "player_stats", None) or PlayerStats()

        # --- NUEVO: asegurar inventario al crear partida nueva ---
        self._ensure_inventory()

        # mapa
        if isinstance(self.state, dict):
            cm = self.state.get("map_data") or self.state.get("city_map") or {}
        else:
            cm = getattr(self.state, "map_data", None) or getattr(self.state, "city_map", {})
        self.game_map = GameMap(cm)

        rows = len(self.game_map.grid)
        cols = len(self.game_map.grid[0]) if rows > 0 else 0
        start_cx = cols // 2 if cols else 0
        start_cy = rows // 2 if rows else 0
        self.player: Player = Player((start_cx, start_cy), TILE_SIZE, rows, flip_y=FLIP_Y)
        try:
            self.player.bind_stats(self.player_stats)
        except Exception:
            self.player.bound_stats = self.player_stats

        # sprite scale
        try:
            tex = getattr(self.player, "texture", None)
            spr = getattr(self.player, "sprite", None)
            if tex is not None and spr is not None:
                max_dim = max(getattr(tex, "width", 1), getattr(tex, "height", 1))
                scale = (TILE_SIZE * 0.9) / max_dim
                spr.scale = scale
                self.player._sprite_base_scale = scale
        except Exception:
            pass

        self.base_scale = getattr(self.player, "_sprite_base_scale", 1.0)
        self.facing = "up"

        # notifs/jobs
        self.incoming_raw_jobs: List[dict] = []
        self.rejected_raw_jobs: List[dict] = []
        self.accepted_job_ids = set()
        self.accepted_raw_jobs: List[dict] = []
        self.notification_active = False
        self.notification_timer = 0.0
        self.next_spawn_timer = 0.0
        self.NOTIF_ACCEPT_SECONDS = 10.0
        self.NEXT_SPAWN_AFTER_ACCEPT = 10.0

        # textos
        self.panel_title = Text("COURIER QUEST", MAP_WIDTH + 10, SCREEN_HEIGHT - 30, arcade.color.GOLD, 16, bold=True)
        self.stats_text = Text("", MAP_WIDTH + 10, SCREEN_HEIGHT - 60, arcade.color.WHITE, 12)
        self.weather_text = Text("", MAP_WIDTH + 10, SCREEN_HEIGHT - 85, arcade.color.LIGHT_BLUE, 12)
        self.inventory_title = Text("INVENTARIO", MAP_WIDTH + 10, SCREEN_HEIGHT - 120, arcade.color.CYAN, 14, bold=True)
        self.inventory_text = Text("", MAP_WIDTH + 10, SCREEN_HEIGHT - 140, arcade.color.WHITE, 11)
        self.jobs_title = Text("PEDIDOS ACTIVOS", MAP_WIDTH + 10, SCREEN_HEIGHT - 200, arcade.color.ORANGE, 14, bold=True)
        self.jobs_text = Text("", MAP_WIDTH + 10, SCREEN_HEIGHT - 220, arcade.color.WHITE, 11)
        self.score_title = Text("ESTADÍSTICAS", MAP_WIDTH + 10, SCREEN_HEIGHT - 280, arcade.color.GREEN, 14, bold=True)
        self.score_text = Text("", MAP_WIDTH + 10, SCREEN_HEIGHT - 300, arcade.color.WHITE, 11)
        self.timer_text = Text("", MAP_WIDTH + 10, SCREEN_HEIGHT - 340, arcade.color.RED, 14, bold=True)
        self.notification_text = Text("", SCREEN_WIDTH - 350, 200, arcade.color.YELLOW, 12)
        self.stamina_text = Text("", MAP_WIDTH + 150, 50, arcade.color.WHITE, 12, anchor_x="center", anchor_y="center")

        self.job_notification_active = False
        self.job_notification_data = None
        self.job_notification_timer = 0.0

        self.weather_markov = WeatherMarkov(api=ApiClient())
        self.weather_renderer = WeatherRenderer(self)

        self._last_input_time = 0.0
        self.INPUT_ACTIVE_WINDOW = 0.25

        self.active_notification = None
        self.NOTIFICATION_DURATION = 5.0
        self._pending_offer = None
        self._offer_job_id = None

        # Reanudación (clima congelado al cargar partida)
        self._resume_mode = bool(
            (isinstance(self.state, dict) and self.state.get("__resume_from_save__"))
            or getattr(self.state, "__resume_from_save__", False)
        )
        self._freeze_weather = self._resume_mode
        self._resume_weather_state = None

        self._initialize_game_systems()

    # --- NUEVO: creador/asegurador de inventario para partidas nuevas ---
    def _ensure_inventory(self):
        try:
            if isinstance(self.state, dict):
                inv = self.state.get("inventory", None)
                if inv is None and Inventory is not None:
                    self.state["inventory"] = Inventory()
            else:
                inv = getattr(self.state, "inventory", None)
                if inv is None and Inventory is not None:
                    setattr(self.state, "inventory", Inventory())
        except Exception as e:
            print(f"[INV] No se pudo crear inventario: {e}")

    # ------------------ Inicialización sistemas ------------------
    def _initialize_game_systems(self):
        try:
            self.game_manager = GameManager()
            self.job_manager = JobManager()

            # Antes de nada, garantizar inventario presente también aquí
            self._ensure_inventory()

            # datos desde state
            if isinstance(self.state, dict):
                map_data = self.state.get("map_data") or self.state.get("city_map", {})
                jobs_data = self.state.get("jobs_data") or self.state.get("orders", [])
                weather_data = self.state.get("weather_data") or self.state.get("weather_state", {})
            else:
                map_data = getattr(self.state, "map_data", None) or getattr(self.state, "city_map", {})
                jobs_data = getattr(self.state, "jobs_data", None) or getattr(self.state, "orders", [])
                weather_data = getattr(self.state, "weather_data", None) or getattr(self.state, "weather_state", {})

            try:
                self.game_manager.initialize_game(map_data, jobs_data, weather_data)
            except Exception:
                pass

            try:
                if self.game_manager:
                    self.game_manager.set_game_map(self.game_map)
            except Exception:
                pass

            # reanudación: tiempo, clima, posición
            if self._resume_mode:
                self._fast_forward_elapsed()
                try:
                    ws = self.state.get("weather_state") if isinstance(self.state, dict) else getattr(
                        self.state, "weather_state", {}
                    )
                    if not ws:
                        ws = self.state.get("weather_data") if isinstance(self.state, dict) else getattr(
                            self.state, "weather_data", {}
                        )
                    self._resume_weather_state = ws or {}
                    if hasattr(self.weather_markov, "apply_external_state"):
                        self.weather_markov.apply_external_state(self._resume_weather_state)
                except Exception as e:
                    print(f"[RESUME] No se pudo fijar clima: {e}")

                try:
                    px = self.state.get("player_x") if isinstance(self.state, dict) else getattr(self.state, "player_x", None)
                    py = self.state.get("player_y") if isinstance(self.state, dict) else getattr(self.state, "player_y", None)
                    if px is not None and py is not None:
                        if hasattr(self.player, "set_cell"):
                            self.player.set_cell(int(px), int(py))
                        else:
                            self.player.cell_x = int(px)
                            self.player.cell_y = int(py)
                except Exception as e:
                    print(f"[RESUME] No se pudo fijar posición: {e}")

            self.set_game_systems(self.game_manager, self.job_manager)
            print("🎮 SISTEMAS DE JUEGO INICIALIZADOS")
        except Exception as e:
            print(f"Error inicializando sistemas de juego: {e}")

    def _fast_forward_elapsed(self):
        """Empuja el tiempo al elapsed guardado. Incluye fallbacks robustos."""
        try:
            elapsed = None
            if isinstance(self.state, dict):
                elapsed = self.state.get("elapsed_seconds")
            else:
                elapsed = getattr(self.state, "elapsed_seconds", None)
            if elapsed is None:
                return
            elapsed = float(elapsed)
            gm = self.game_manager
            if not gm:
                return

            # 1) setters nativos si existen
            try:
                if hasattr(gm, "set_elapsed") and callable(gm.set_elapsed):
                    gm.set_elapsed(elapsed)
                    return
                if hasattr(gm, "set_game_time") and callable(gm.set_game_time):
                    gm.set_game_time(elapsed)
                    return
            except Exception:
                pass

            # 2) atributo interno común
            for attr in ("_elapsed", "elapsed", "time_elapsed", "game_time"):
                if hasattr(gm, attr):
                    try:
                        setattr(gm, attr, elapsed)
                        if hasattr(gm, "_last_update"):
                            gm._last_update = time.time()
                        return
                    except Exception:
                        pass

            # 3) fallback con offset dinámico (monkey-patch)
            try:
                if hasattr(gm, "get_game_time") and callable(gm.get_game_time):
                    _orig_get_game_time = gm.get_game_time

                    def _wrapped_get_game_time():
                        try:
                            base = _orig_get_game_time()
                        except TypeError:
                            base = _orig_get_game_time
                        return float(base) + elapsed

                    gm.get_game_time = _wrapped_get_game_time

                if hasattr(gm, "get_time_remaining") and callable(gm.get_time_remaining):
                    total = getattr(gm, "max_duration", getattr(gm, "duration", 900))

                    def _wrapped_get_time_remaining():
                        return max(0.0, float(total) - gm.get_game_time())

                    gm.get_time_remaining = _wrapped_get_time_remaining

                if hasattr(gm, "get_current_map_time") and callable(gm.get_current_map_time):
                    import datetime
                    _orig_get_map_time = gm.get_current_map_time
                    start = getattr(gm, "map_start_time", None) or getattr(gm, "_map_start_time", None)
                    if start:
                        def _wrapped_get_current_map_time():
                            try:
                                return start + datetime.timedelta(seconds=gm.get_game_time())
                            except Exception:
                                return _orig_get_map_time()

                        gm.get_current_map_time = _wrapped_get_current_map_time
            except Exception as e:
                print(f"[RESUME] Offset de tiempo falló: {e}")
        except Exception as e:
            print(f"[RESUME] Fast-forward falló: {e}")

    def set_game_systems(self, game_manager, job_manager):
        self.game_manager = game_manager
        self.job_manager = job_manager
        self.score_system = getattr(game_manager, 'score_system', None)
        if game_manager:
            try:
                game_manager.player_manager = self.player
            except Exception:
                pass
        self._load_initial_jobs()

    def _load_initial_jobs(self):
        # 1) leer lista del save
        if isinstance(self.state, dict):
            orders = self.state.get("orders") or self.state.get("jobs_data", [])
        else:
            orders = getattr(self.state, "orders", None) or getattr(self.state, "jobs_data", [])
        orders = list(orders or [])

        self.incoming_raw_jobs = []
        self.rejected_raw_jobs = []
        self.accepted_raw_jobs = []

        # 2) separar aceptados vs pendientes
        for r in orders:
            if r and r.get("accepted"):
                self.accepted_raw_jobs.append(r)
            else:
                self.incoming_raw_jobs.append(r)

        # 3) sembrar los aceptados usando coordenadas guardadas
        if self.job_manager:
            for raw in self.accepted_raw_jobs:
                try:
                    jid = raw.get("id") or raw.get("job_id")
                    saved_pickup = tuple(raw.get("pickup")) if raw.get("pickup") else None
                    saved_dropoff = tuple(raw.get("dropoff")) if raw.get("dropoff") else None

                    spawn_hint = saved_pickup if saved_pickup is not None else None
                    self.job_manager.add_job_from_raw(raw, spawn_hint)

                    job = self.job_manager.get_job(jid)
                    if job:
                        if saved_pickup is not None:
                            job.pickup = saved_pickup
                        if saved_dropoff is not None:
                            job.dropoff = saved_dropoff
                        job.accepted = bool(raw.get("accepted", True))
                        job.picked_up = bool(raw.get("picked_up", False))
                        job.completed = bool(raw.get("completed", False))

                        # si estaba recogido, añadir al inventario
                        inv = self.state.get("inventory") if isinstance(self.state, dict) else getattr(self.state, "inventory", None)
                        if job.picked_up and inv:
                            try:
                                if hasattr(inv, "push"):
                                    inv.push(job)
                                elif hasattr(inv, "add"):
                                    inv.add(job)
                                elif hasattr(inv, "append"):
                                    inv.append(job)
                                elif hasattr(inv, "deque"):
                                    inv.deque.append(job)
                            except Exception:
                                pass
                except Exception as e:
                    print(f"[SEED] Error sembrando job aceptado: {e}")

        # 4) filtrar pendientes por ids ya aceptados
        accepted_ids = {(r.get("id") or r.get("job_id")) for r in self.accepted_raw_jobs}
        self.incoming_raw_jobs = [r for r in self.incoming_raw_jobs if (r.get("id") or r.get("job_id")) not in accepted_ids]
        print(f"[JOBS] Cargados {len(self.incoming_raw_jobs)} pendientes, {len(self.accepted_raw_jobs)} aceptados")

    def _raw_job_id(self, raw: dict) -> str:
        return raw.get("id") or raw.get("job_id") or raw.get("req") or str(raw)

    # ------------------ Helpers de dibujo centrado ------------------
    def _draw_centered_rect_filled(self, cx: float, cy: float, width: float, height: float, color):
        half_w = width / 2.0
        half_h = height / 2.0
        pts = [(cx - half_w, cy - half_h), (cx + half_w, cy - half_h),
               (cx + half_w, cy + half_h), (cx - half_w, cy + half_h)]
        arcade.draw_polygon_filled(pts, color)

    def _draw_centered_rect_outline(self, cx: float, cy: float, width: float, height: float, color, border_width=2):
        half_w = width / 2.0
        half_h = height / 2.0
        pts = [(cx - half_w, cy - half_h), (cx + half_w, cy - half_h),
               (cx + half_w, cy + half_h), (cx - half_w, cy + half_h)]
        arcade.draw_polygon_outline(pts, color, border_width)

    # ------------------ Marcadores de jobs ------------------
    def _get_job_pickup_coords(self, job):
        """Obtiene las coordenadas de pickup de un job de manera robusta"""
        try:
            return tuple(job.pickup)
        except Exception:
            try:
                raw = getattr(job, "raw", {}) or {}
                pickup_raw = raw.get("pickup", None)
                if pickup_raw:
                    return tuple(pickup_raw)
            except Exception:
                pass
        return None, None

    def _get_job_dropoff_coords(self, job):
        """Obtiene las coordenadas de dropoff de un job de manera robusta"""
        try:
            return tuple(job.dropoff)
        except Exception:
            try:
                raw = getattr(job, "raw", {}) or {}
                dropoff_raw = raw.get("dropoff", None)
                if dropoff_raw:
                    return tuple(dropoff_raw)
            except Exception:
                pass
        return None, None

    def _draw_job_markers(self):
        """Dibuja los marcadores de pickup y dropoff en el mapa"""
        if not self.job_manager:
            return
        try:
            for job in self.job_manager.all_jobs():
                # pickup: aceptado y no recogido
                if getattr(job, "accepted", False) and not getattr(job, "picked_up", False):
                    px_c, py_c = self._get_job_pickup_coords(job)
                    if px_c is not None and py_c is not None:
                        px, py = self._cell_to_pixel(int(px_c), int(py_c))
                        arcade.draw_circle_filled(px, py, TILE_SIZE * 0.4, arcade.color.GOLD)
                        arcade.draw_circle_outline(px, py, TILE_SIZE * 0.4, arcade.color.BLACK, 2)
                        job_label = getattr(job, "id", None) or (getattr(job, "raw", {}) or {}).get("id", "PICKUP")
                        Text(f"{job_label}", px - 18, py + 15, arcade.color.BLACK, 8).draw()

                # dropoff: recogido y no entregado
                if getattr(job, "picked_up", False) and not getattr(job, "completed", False):
                    dx_c, dy_c = self._get_job_dropoff_coords(job)
                    if dx_c is not None and dy_c is not None:
                        dx, dy = self._cell_to_pixel(int(dx_c), int(dy_c))
                        self._draw_centered_rect_filled(dx, dy, TILE_SIZE * 0.6, TILE_SIZE * 0.6, arcade.color.RED)
                        self._draw_centered_rect_outline(dx, dy, TILE_SIZE * 0.6, TILE_SIZE * 0.6, arcade.color.BLACK, 2)
                        drop_label = getattr(job, "id", None) or (getattr(job, "raw", {}) or {}).get("id", "DROPOFF")
                        Text(f"{drop_label}", dx - 25, dy + 15, arcade.color.WHITE, 8).draw()
        except Exception as e:
            print(f"[ERROR] Dibujando marcadores: {e}")

    # ------------------ Notificaciones / Jobs ------------------
    def _maybe_start_notification(self):
        if self.job_notification_active or self.next_spawn_timer > 0.0:
            return
        self.incoming_raw_jobs = [r for r in self.incoming_raw_jobs if self._raw_job_id(r) not in self.accepted_job_ids]
        if self.incoming_raw_jobs:
            self._spawn_next_notification_immediate()

    def _spawn_next_notification_immediate(self):
        if not self.incoming_raw_jobs:
            return
        raw = self.incoming_raw_jobs.pop(0)
        self.job_notification_active = True
        self.job_notification_data = raw
        self.job_notification_timer = self.NOTIF_ACCEPT_SECONDS

        jid = self._raw_job_id(raw)
        payout = raw.get("payout", 0)
        weight = raw.get("weight", 0)
        self.show_notification(f"📦 NUEVO PEDIDO\nID:{jid} Pago:${payout} Peso:{weight}kg\n(A) Aceptar (R) Rechazar")
        print(f"[NOTIF] Nuevo trabajo {jid}")

    def show_notification(self, message: str):
        self.active_notification = message
        self.notification_timer = self.NOTIFICATION_DURATION
        print(f"[NOTIFICATION] {message}")

    def _accept_notification(self):
        if not self.job_notification_data:
            return
        raw = self.job_notification_data
        jid = self._raw_job_id(raw)

        # Verificar capacidad del inventario
        inventory = self.state.get("inventory") if isinstance(self.state, dict) else getattr(self.state, "inventory", None)
        new_weight = float(raw.get("weight", 1.0))
        if inventory and (getattr(inventory, "current_weight", 0.0) + new_weight > getattr(inventory, "max_weight", 10.0)):
            self.show_notification("❌ Capacidad insuficiente")
            self.rejected_raw_jobs.append(raw)
            self.job_notification_active = False
            self.job_notification_data = None
            return

        # Aceptar el trabajo — ***FIX: NO forzar pickup_override***
        if self.job_manager:
            try:
                # Antes: self.job_manager.add_job_from_raw(raw, (self.player.cell_x, self.player.cell_y))
                # Ahora: respetar pickup/dropoff del JSON
                self.job_manager.add_job_from_raw(raw)
                job = self.job_manager.get_job(jid)
                if job:
                    job.accepted = True
                print(f"[ACCEPT] Trabajo {jid} añadido")
            except Exception as e:
                print(f"[ERROR] Añadiendo trabajo: {e}")

        self.accepted_job_ids.add(jid)
        self.job_notification_active = False
        self.job_notification_data = None
        self.next_spawn_timer = self.NEXT_SPAWN_AFTER_ACCEPT
        self.show_notification(f"✅ Pedido {jid} aceptado")

    def _reject_notification(self):
        if self.job_notification_data:
            jid = self._raw_job_id(self.job_notification_data)
            self.rejected_raw_jobs.append(self.job_notification_data)
            print(f"[REJECT] Trabajo {jid} rechazado")
        self.job_notification_active = False
        self.job_notification_data = None
        self.show_notification("❌ Pedido rechazado")

    # ------------------ Dibujo / panel / tiempo ------------------
    def _cell_to_pixel(self, cx, cy):
        x = cx * TILE_SIZE + TILE_SIZE // 2
        y = (len(self.game_map.grid) - 1 - cy) * TILE_SIZE + TILE_SIZE // 2
        return x, y

    def _draw_job_notification(self):
        if not self.job_notification_active or not self.job_notification_data:
            return
        raw = self.job_notification_data
        job_id = self._raw_job_id(raw)
        payout = raw.get("payout", 0)
        weight = raw.get("weight", 0)
        priority = raw.get("priority", 1)
        description = raw.get("description", "Sin descripción")

        panel_width = 400
        panel_height = 250
        left = SCREEN_WIDTH - panel_width - 20
        bottom = 100
        right = left + panel_width
        top = bottom + panel_height

        _draw_rect_lrbt_filled(left, right, bottom, top, arcade.color.DARK_BLUE)
        _draw_rect_lrbt_outline(left, right, bottom, top, arcade.color.GOLD, 3)
        Text("📦 NUEVO PEDIDO", left + 10, top - 25, arcade.color.GOLD, 16, bold=True).draw()

        info_y = top - 50
        Text(f"ID: {job_id}", left + 15, info_y, arcade.color.WHITE, 12).draw()
        Text(f"Pago: ${payout}", left + 15, info_y - 20, arcade.color.GREEN, 12).draw()
        Text(f"Peso: {weight}kg", left + 15, info_y - 40, arcade.color.CYAN, 12).draw()
        Text(f"Prioridad: {priority}", left + 15, info_y - 60, arcade.color.ORANGE, 12).draw()

        time_y = info_y - 80
        if self.game_manager:
            try:
                time_remaining = self.game_manager.get_job_time_remaining(raw)
                if time_remaining != float('inf'):
                    minutes = int(time_remaining // 60)
                    seconds = int(time_remaining % 60)
                    time_color = arcade.color.GREEN if time_remaining > 300 else arcade.color.ORANGE if time_remaining > 60 else arcade.color.RED
                    Text(f"Tiempo límite: {minutes:02d}:{seconds:02d}", left + 15, time_y, time_color, 12).draw()
                    time_y -= 20
            except Exception:
                pass

        desc = description[:80] + "..." if len(description) > 80 else description
        Text(f"Desc: {desc}", left + 15, time_y, arcade.color.LIGHT_GRAY, 10).draw()
        controls_y = bottom + 30
        Text("(A) Aceptar  (R) Rechazar", left + 15, controls_y, arcade.color.YELLOW, 12).draw()
        Text(f"Decidir en: {int(self.job_notification_timer)}s", left + 15, controls_y - 20, arcade.color.RED, 12).draw()

    def on_show(self) -> None:
        arcade.set_background_color(arcade.color.DARK_SLATE_GRAY)

    def on_draw(self) -> None:
        self.clear()
        self.game_map.draw_debug(tile_size=TILE_SIZE, draw_grid_lines=True)
        self._draw_job_markers()
        self.player.draw()
        self._draw_panel()
        self._draw_time_panel()
        try:
            self.weather_renderer.draw()
        except Exception:
            pass
        self._draw_job_notification()

        # notificación activa
        if self.active_notification and self.notification_timer > 0:
            self.notification_text.text = self.active_notification
            self.notification_text.draw()

    def _draw_panel(self):
        _draw_rect_lrbt_filled(MAP_WIDTH, SCREEN_WIDTH, 0, SCREEN_HEIGHT, arcade.color.DARK_SLATE_BLUE)
        _draw_rect_lrbt_outline(MAP_WIDTH, SCREEN_WIDTH, 0, SCREEN_HEIGHT, arcade.color.BLUE, 2)

        self.panel_title.draw()

        money = getattr(self.state, "money", 0) if not isinstance(self.state, dict) else self.state.get("money", 0)
        reputation = getattr(self.player_stats, "reputation", 70)
        if isinstance(self.state, dict):
            _m = self.state.get("map_data") or self.state.get("city_map") or {}
        else:
            _m = getattr(self.state, "map_data", None) or getattr(self.state, "city_map", {})
        goal = (_m or {}).get("goal", 3000)
        self.stats_text.text = f"Dinero: ${money:.0f}\nMeta: ${goal}\nReputación: {reputation}/100"
        self.stats_text.draw()

        if isinstance(self.state, dict):
            ws = self.state.get("weather_state") or self.state.get("weather_data", {})
        else:
            ws = getattr(self.state, "weather_state", None) or getattr(self.state, "weather_data", {})
        cond = ws.get("condition", "?")
        intensity = ws.get("intensity", "?")
        multiplier = ws.get("multiplier", 1.0)
        self.weather_text.text = f"Clima: {cond}\nIntensidad: {intensity}\nVelocidad: {multiplier:.0%}"
        self.weather_text.draw()

        self.inventory_title.draw()
        inventory = self.state.get("inventory", None) if isinstance(self.state, dict) else getattr(self.state, "inventory", None)
        if inventory:
            weight = getattr(inventory, "current_weight", 0)
            max_weight = getattr(inventory, "max_weight", 10)
            items = []
            try:
                if hasattr(inventory, 'get_deque_values'):
                    inventory_items = inventory.get_deque_values()
                else:
                    inventory_items = []
                    if hasattr(inventory, 'deque'):
                        for item in inventory.deque:
                            inventory_items.append(getattr(item, "val", item))

                # orden visual por modo
                if self.inventory_sort_mode == "priority":
                    try:
                        inventory_items = sorted(
                            inventory_items,
                            key=lambda j: getattr(j, "priority", None) or (getattr(j, "raw", {}) or {}).get("priority", 999)
                        )
                    except Exception:
                        pass
                elif self.inventory_sort_mode == "deadline":
                    try:
                        inventory_items = sorted(
                            inventory_items,
                            key=lambda j: getattr(j, "deadline", None) or (getattr(j, "raw", {}) or {}).get("deadline", 999999)
                        )
                    except Exception:
                        pass

                view = inventory_items[self.inventory_view_index:self.inventory_view_index + 4]
                for job in view:
                    job_id = getattr(job, "id", job.get("id") if isinstance(job, dict) else str(job))
                    items.append(f"- {job_id}")
            except Exception:
                items = ["- Error cargando"]
            inventory_info = f"Peso: {weight}/{max_weight}kg\n" + "\n".join(items or ["- Vacío"])
        else:
            inventory_info = "Peso: 0/10kg\n- Vacío"
        self.inventory_text.text = inventory_info
        self.inventory_text.draw()

        self.jobs_title.draw()
        if self.job_manager and self.game_manager:
            try:
                active_jobs = self.job_manager.get_active_jobs()
                jobs_info = []
                for job in active_jobs[:4]:
                    status = "✓" if getattr(job, "picked_up", False) else "📦"
                    job_id = getattr(job, "id", "Unknown")
                    payout = getattr(job, "payout", 0)
                    job_text = f"- {job_id} {status}"
                    job_text += " → 🎯" if getattr(job, "picked_up", False) else f" (${payout})"
                    jobs_info.append(job_text)
                if not jobs_info:
                    jobs_info = ["- No hay pedidos activos"]
                    try:
                        available = self.job_manager.get_available_jobs(self.game_manager.get_game_time())
                    except Exception:
                        available = []
                    if available:
                        jobs_info.append(f"- {len(available)} disponibles")
                self.jobs_text.text = "\n".join(jobs_info)
            except Exception as e:
                self.jobs_text.text = f"- Error: {str(e)[:30]}..."
        else:
            self.jobs_text.text = "- Sistemas cargando..."
        self.jobs_text.draw()

        if self.game_manager and hasattr(self.game_manager, 'get_time_remaining'):
            time_remaining = self.game_manager.get_time_remaining()
            minutes = int(time_remaining // 60)
            seconds = int(time_remaining % 60)
            self.timer_text.text = f"⏰ {minutes:02d}:{seconds:02d}"
            self.timer_text.color = (
                arcade.color.GREEN if time_remaining >= 600
                else arcade.color.ORANGE if time_remaining >= 300
                else arcade.color.RED
            )
        else:
            self.timer_text.text = "⏰ 15:00"
        self.timer_text.draw()

        self.score_title.draw()
        if self.score_system:
            try:
                stats = self.score_system.get_current_stats()
                tr = stats.get('time_remaining', 0)
                minutes = int(tr // 60)
                seconds = int(tr % 60)
                self.score_text.text = (f"Entregas: {stats['deliveries_completed']}\n"
                                        f"A tiempo: {stats['on_time_deliveries']}\n"
                                        f"Dinero: ${stats['total_money']:.0f}\n"
                                        f"Tiempo: {minutes:02d}:{seconds:02d}")
            except Exception as e:
                self.score_text.text = f"Error: {e}"
        else:
            self.score_text.text = "Cargando..."
        self.score_text.draw()

        stamina_val = getattr(self.player_stats, "stamina", 100.0)
        bar_w, bar_h = 200, 20
        left = MAP_WIDTH + 50
        bottom = 30
        right = left + bar_w
        top = bottom + bar_h
        _draw_rect_lrbt_filled(left, right, bottom, top, arcade.color.DARK_SLATE_GRAY)
        pct = max(0.0, min(1.0, stamina_val / 100.0))
        if pct > 0.0:
            fill_right = left + (bar_w * pct)
            color = arcade.color.GREEN if pct > 0.3 else arcade.color.ORANGE if pct > 0.1 else arcade.color.RED
            _draw_rect_lrbt_filled(left, fill_right, bottom, top, color)
        _draw_rect_lrbt_outline(left, right, bottom, top, arcade.color.BLACK, 2)
        self.stamina_text.position = (left + bar_w / 2, bottom + bar_h / 2)
        self.stamina_text.text = f"RESISTENCIA: {int(stamina_val)}%"
        self.stamina_text.draw()

    def _draw_time_panel(self):
        if not self.game_manager:
            return
        panel_x = 10
        panel_y = SCREEN_HEIGHT - 100
        panel_width = 300
        panel_height = 90
        _draw_rect_lrbt_filled(panel_x, panel_x + panel_width, panel_y - panel_height, panel_y, arcade.color.DARK_SLATE_GRAY)
        _draw_rect_lrbt_outline(panel_x, panel_x + panel_width, panel_y - panel_height, panel_y, arcade.color.BLUE, 2)
        Text("⏰ TIEMPO DE SIMULACIÓN", panel_x + 10, panel_y - 20, arcade.color.GOLD, 12, bold=True).draw()
        try:
            current_time = self.game_manager.get_game_time()
            minutes = int(current_time // 60)
            seconds = int(current_time % 60)
            time_remaining = self.game_manager.get_time_remaining()
            rem_minutes = int(time_remaining // 60)
            rem_seconds = int(time_remaining % 60)
            current_map_time = self.game_manager.get_current_map_time()
            time_str = current_map_time.strftime("%H:%M:%S")
            date_str = current_map_time.strftime("%Y-%m-%d")
            Text(f"Hora: {time_str}", panel_x + 15, panel_y - 40, arcade.color.WHITE, 11).draw()
            Text(f"Fecha: {date_str}", panel_x + 15, panel_y - 55, arcade.color.WHITE, 11).draw()
            Text(f"Transcurrido: {minutes:02d}:{seconds:02d}", panel_x + 15, panel_y - 70, arcade.color.CYAN, 11).draw()
            time_color = arcade.color.GREEN if time_remaining >= 600 else arcade.color.ORANGE if time_remaining >= 300 else arcade.color.RED
            Text(f"Restante: {rem_minutes:02d}:{rem_seconds:02d}", panel_x + 15, panel_y - 85, time_color, 11, bold=True).draw()
        except Exception:
            pass

    def on_update(self, dt: float) -> None:
        # Actualizar game manager
        if self.game_manager:
            try:
                self.game_manager.update(dt)
            except Exception as e:
                print(f"Error en game_manager.update: {e}")

        # Gestión notificaciones de jobs
        if self.job_notification_active:
            self.job_notification_timer -= dt
            if self.job_notification_timer <= 0:
                self._reject_notification()

        if self.next_spawn_timer > 0.0:
            self.next_spawn_timer -= dt

        if not self.job_notification_active:
            self._maybe_start_notification()

        # Temporal general de notificaciones
        if self.active_notification and self.notification_timer > 0:
            self.notification_timer -= dt
            if self.notification_timer <= 0:
                self.active_notification = None

        # Movimiento del jugador
        input_active = (time.time() - self._last_input_time) < self.INPUT_ACTIVE_WINDOW
        # --- por si alguien borró el inventario del estado en caliente:
        self._ensure_inventory()
        inventory = self.state.get("inventory", None) if isinstance(self.state, dict) else getattr(self.state, "inventory", None)
        was_moving = bool(self.player.moving)

        # Actualizar jugador
        try:
            self.player.update(dt, player_stats=self.player_stats, weather_system=self.weather_markov, inventory=inventory)
        except Exception:
            try:
                self.player.update(dt)
            except Exception:
                pass

        # LÓGICA DE PICKUP Y DROPOFF al detenerse
        if was_moving and not self.player.moving:
            px = int(self.player.cell_x)
            py = int(self.player.cell_y)

            # 1. Intentar pickup (misma celda o adyacente)
            picked_up = False

            # Primero intentar con GameManager si está disponible
            if self.game_manager and hasattr(self.game_manager, 'try_pickup_at'):
                try:
                    picked_up = self.game_manager.try_pickup_at(px, py)
                except Exception as e:
                    print(f"Error en try_pickup_at: {e}")

            # Si no se pudo recoger, intentar con lógica nearby
            if not picked_up:
                picked_up = self._pickup_nearby()

            if picked_up:
                self.show_notification("¡Paquete recogido! Ve al punto de entrega.")

            # 2. Intentar entrega (solo misma celda exacta)
            delivered = self._try_deliver_at_position(px, py)
            if delivered:
                self.show_notification("¡Pedido entregado! +$")

        # Actualizar player_stats
        try:
            current_weather = "clear"
            try:
                if hasattr(self.weather_markov, "current_condition"):
                    current_weather = self.weather_markov.current_condition
                else:
                    current_weather = self.weather_markov.get_state().get("condition", "clear")
            except Exception:
                current_weather = "clear"

            self.player_stats.update(
                dt,
                bool(self.player.moving),
                getattr(self, "at_rest_point", False),
                float(getattr(inventory, "current_weight", 0.0)) if inventory is not None else 0.0,
                current_weather,
                input_active=input_active
            )
        except Exception as e:
            print(f"Error actualizando player_stats: {e}")

        # Clima (congelado al reanudar)
        try:
            if self._freeze_weather:
                ws = self._resume_weather_state or (
                    self.state.get("weather_state") if isinstance(self.state, dict) else getattr(self.state, "weather_state", {})
                ) or {}
                self.weather_renderer.update(dt, ws)
            else:
                self.weather_markov.update(dt)
                self.weather_markov.apply_to_game_state(self.state)
                ws = self.state.get("weather_state", {}) if isinstance(self.state, dict) else getattr(self.state, "weather_state", {})
                self.weather_renderer.update(dt, ws)
        except Exception as e:
            print(f"Error actualizando clima: {e}")

    # ------------------ Lógica de pickup/dropoff ------------------
    def _pickup_nearby(self) -> bool:
        """Recoge pedidos aceptados y no recogidos en celda actual o adyacentes (Manhattan <= 1)."""
        if not self.job_manager:
            return False

        px = int(self.player.cell_x)
        py = int(self.player.cell_y)
        picked_any = False

        try:
            for job in self.job_manager.get_active_jobs():
                if not getattr(job, "accepted", False):
                    continue
                if getattr(job, "picked_up", False) or getattr(job, "completed", False):
                    continue

                jpx, jpy = self._get_job_pickup_coords(job)
                if jpx is None or jpy is None:
                    continue

                if abs(int(jpx) - px) + abs(int(jpy) - py) <= 1:
                    job.picked_up = True
                    job.dropoff_visible = True
                    picked_any = True

                    inventory = self.state.get("inventory") if isinstance(self.state, dict) else getattr(self.state, "inventory", None)
                    if inventory:
                        try:
                            if hasattr(inventory, "add"):
                                inventory.add(job)
                            elif hasattr(inventory, "push"):
                                inventory.push(job)
                        except Exception as e:
                            print(f"[PICKUP] Error añadiendo al inventario: {e}")

                    print(f"[PICKUP] Paquete {getattr(job,'id','?')} recogido en {px},{py} (pickup en {jpx},{jpy})")

            return picked_any
        except Exception as e:
            print(f"[PICKUP] Error en _pickup_nearby: {e}")
            return False

    def _try_deliver_at_position(self, px: int, py: int) -> bool:
        """Entrega paquetes recogidos si el jugador está exactamente en el dropoff."""
        if not self.job_manager:
            return False

        delivered_any = False

        try:
            for job in self.job_manager.get_active_jobs():
                if not getattr(job, "accepted", False) or not getattr(job, "picked_up", False):
                    continue
                if getattr(job, "completed", False):
                    continue

                dx, dy = self._get_job_dropoff_coords(job)
                if dx is None or dy is None:
                    continue

                if int(dx) == px and int(dy) == py:
                    job.completed = True
                    delivered_any = True

                    # Remover del inventario
                    inventory = self.state.get("inventory") if isinstance(self.state, dict) else getattr(self.state, "inventory", None)
                    if inventory:
                        try:
                            if hasattr(inventory, "remove"):
                                inventory.remove(job)
                            elif hasattr(inventory, "deque"):
                                for item in list(inventory.deque):
                                    if getattr(item, "id", None) == getattr(job, "id", None):
                                        inventory.deque.remove(item)
                                        break
                        except Exception as e:
                            print(f"[DELIVER] Error removiendo del inventario: {e}")

                    # Añadir recompensa
                    payout = getattr(job, "payout", 0) or (getattr(job, "raw", {}) or {}).get("payout", 0)
                    if isinstance(self.state, dict):
                        self.state["money"] = self.state.get("money", 0) + payout
                    else:
                        if hasattr(self.state, "money"):
                            self.state.money += payout

                    print(f"[DELIVER] Paquete {getattr(job,'id','?')} entregado en {px},{py} +${payout}")

            return delivered_any
        except Exception as e:
            print(f"[DELIVER] Error en _try_deliver_at_position: {e}")
            return False

    # ------------------ Input ------------------
    def on_key_press(self, key: int, modifiers: int) -> None:
        # Registrar input
        self._last_input_time = time.time()

        # Tecla P: intentar recoger paquete cercano/manual
        if key == arcade.key.P:
            try:
                picked = False
                # Primero intentar con GameManager exacto
                if self.game_manager and hasattr(self.game_manager, 'try_pickup_at'):
                    picked = self.game_manager.try_pickup_at(self.player.cell_x, self.player.cell_y)
                # Si no recogió, intentar nearby
                if not picked:
                    picked = self._pickup_nearby()
                if picked:
                    self.show_notification("¡Paquete recogido! Ve al punto de entrega.")
                else:
                    self.show_notification("No hay paquete para recoger aquí o adyacente.")
            except Exception as e:
                print(f"[INPUT] Error recogiendo paquete (P): {e}")
            return

        # Aceptación / navegación
        if key == arcade.key.A:
            if self.job_notification_active and self.job_notification_data:
                self._accept_notification()
                return
            if self._pending_offer:
                try:
                    on_accept, _ = self._pending_offer
                    if on_accept:
                        on_accept(None)
                finally:
                    self._pending_offer = None
                    self._offer_job_id = None
                return
            if self.inventory_view_index > 0:
                self.inventory_view_index -= 1
                self.show_notification("◀ Página anterior del inventario")
                return

        if key == arcade.key.D:
            if self.job_notification_active and self.job_notification_data:
                return
            inventory = self.state.get("inventory", None) if isinstance(self.state, dict) else getattr(self.state, "inventory", None)
            if inventory:
                try:
                    if hasattr(inventory, 'get_deque_values'):
                        inventory_items = inventory.get_deque_values()
                    else:
                        inventory_items = []
                        if hasattr(inventory, 'deque'):
                            for item in inventory.deque:
                                inventory_items.append(getattr(item, "val", item))

                    if self.inventory_view_index + 4 < len(inventory_items):
                        self.inventory_view_index += 1
                        self.show_notification("▶ Página siguiente del inventario")
                        return
                except Exception:
                    pass

        if key == arcade.key.R:
            if self.job_notification_active and self.job_notification_data:
                self._reject_notification()
                return
            if self._pending_offer:
                try:
                    _, on_reject = self._pending_offer
                    if on_reject:
                        on_reject(None)
                finally:
                    self._pending_offer = None
                    self._offer_job_id = None
                return

        # Ordenar inventario con S
        if key == arcade.key.S:
            if self.inventory_sort_mode == "normal":
                self.inventory_sort_mode = "priority"
            elif self.inventory_sort_mode == "priority":
                self.inventory_sort_mode = "deadline"
            else:
                self.inventory_sort_mode = "normal"
            self.show_notification(f"📋 Ordenando por: {self.inventory_sort_mode}")
            return

        # Debug reload jobs
        if key == arcade.key.L and modifiers & arcade.key.MOD_CTRL:
            self._load_initial_jobs()
            self.show_notification("🔄 Pedidos recargados")
            return

        # Debug spawn
        if key == arcade.key.N and modifiers & arcade.key.MOD_CTRL:
            if self.job_manager and self.game_manager:
                try:
                    job = self.job_manager.peek_next_eligible(self.game_manager.get_game_time())
                    if job:
                        self._spawn_next_notification_immediate()
                    else:
                        self.show_notification("❌ No hay pedidos disponibles")
                except Exception:
                    self.show_notification("❌ No hay pedidos disponibles")
            return

        # Undo
        if key == arcade.key.Z and (modifiers & arcade.key.MOD_CTRL):
            if self.game_manager and hasattr(self.game_manager, 'undo_last_action'):
                if self.game_manager.undo_last_action():
                    self.show_notification("Última acción deshecha")
            return

        # Movement
        dx, dy = 0, 0
        if key == arcade.key.UP:
            dy = -1
            self.facing = "up"
        elif key == arcade.key.DOWN:
            dy = 1
            self.facing = "down"
        elif key == arcade.key.LEFT:
            dx = -1
            self.facing = "left"
        elif key == arcade.key.RIGHT:
            dx = 1
            self.facing = "right"
        else:
            return

        # Apply facing
        self._apply_facing()

        # Si el GameManager intercepta movimiento, usarlo
        if self.game_manager:
            try:
                if hasattr(self.game_manager, 'handle_player_movement'):
                    self.game_manager.handle_player_movement(dx, dy)
                    return
                if hasattr(self.game_manager, 'handle_Player_movement'):
                    self.game_manager.handle_Player_movement(dx, dy)
                    return
            except Exception:
                pass

        moved = self.player.move_by(dx, dy, self.game_map)
        if not moved:
            if self.player.bound_stats and hasattr(self.player.bound_stats, "can_move") and not self.player.bound_stats.can_move():
                self.show_notification("[INFO] No puedes moverte: resistencia agotada.")
            else:
                self.show_notification("Movimiento bloqueado")

    def on_key_release(self, key: int, modifiers: int):
        if not self._pending_offer:
            return
        try:
            on_accept, on_reject = self._pending_offer
            if key == arcade.key.A and on_accept:
                on_accept(None)
            elif key == arcade.key.R and on_reject:
                on_reject(None)
        finally:
            self._pending_offer = None
            self._offer_job_id = None

    def _apply_facing(self):
        spr = getattr(self.player, "sprite", None)
        if spr is None:
            return
        mag = getattr(self.player, "_sprite_base_scale", getattr(spr, "scale", 1.0))
        try:
            spr.scale = mag
        except Exception:
            try:
                spr.scale_x = mag
                spr.scale_y = mag
            except Exception:
                pass
        spr.angle = {"up": 0, "right": 90, "down": 180, "left": -90}.get(self.facing, 0)

    def show_job_offer(self, job_data, on_accept, on_reject):
        try:
            job_id = job_data.get("id", "Unknown")
            payout = job_data.get("payout", 0)
            weight = job_data.get("weight", 0)
            message = f"📦 NUEVO PEDIDO\n{job_id}\nPago: ${payout}\nPeso: {weight}kg\n(A) Aceptar  (R) Rechazar"
            self.show_notification(message)
            self._pending_offer = (on_accept, on_reject)
            self._offer_job_id = job_id
        except Exception as e:
            print(f"Error mostrando oferta: {e}")
            self._pending_offer = None

