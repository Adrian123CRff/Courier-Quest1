import time
import re
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

# Intento de import (para partidas nuevas) — no falla si no existe
try:
    from game.inventory import Inventory
except Exception:
    Inventory = None

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

        # UI inventario
        self.inventory_view_index = 0
        self.inventory_sort_mode = "normal"

        # player stats
        if isinstance(self.state, dict):
            if "player_stats" not in self.state or self.state.get("player_stats") is None:
                self.state["player_stats"] = PlayerStats()
            self.player_stats: PlayerStats = self.state["player_stats"]
        else:
            self.player_stats = getattr(self.state, "player_stats", None) or PlayerStats()

        # asegurar inventario al crear partida nueva
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

        # Dropoff adyacente (Manhattan <= 1)
        self.DROPOFF_ADJACENT = True

        # Entregas ya sumadas al dinero
        self._counted_deliveries = set()

        self._initialize_game_systems()

    # ---------- Inventario para partidas nuevas ----------
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

    # ---------- Dinero: utilidades base ----------
    def _parse_money(self, v) -> float:
        try:
            if v is None:
                return 0.0
            if isinstance(v, (int, float)):
                return float(v)
            s = str(v)
            m = re.search(r"-?\d+(?:[.,]\d+)?", s)
            if not m:
                return 0.0
            num = m.group(0).replace(",", ".")
            return float(num)
        except Exception:
            return 0.0

    def _get_state_money(self) -> float:
        if isinstance(self.state, dict):
            return self._parse_money(self.state.get("money", 0))
        return self._parse_money(getattr(self.state, "money", 0))

    def _set_state_money(self, value: float):
        try:
            v = self._parse_money(value)
            if isinstance(self.state, dict):
                self.state["money"] = v
            else:
                setattr(self.state, "money", v)
        except Exception as e:
            print(f"[MONEY] Error set_state_money: {e}")

    def _add_money(self, amount: float):
        amt = self._parse_money(amount)
        if amt <= 0:
            return
        try:
            current = self._get_state_money()
            self._set_state_money(current + amt)
            print(f"[MONEY] +${amt:.2f}  -> total ${self._get_state_money():.2f}")
        except Exception as e:
            print(f"[MONEY] Error actualizando state: {e}")

        # Reflejar (best-effort) en otros sistemas
        try:
            if self.game_manager:
                for attr in ["money", "cash", "balance"]:
                    if hasattr(self.game_manager, attr):
                        try:
                            old = self._parse_money(getattr(self.game_manager, attr))
                            setattr(self.game_manager, attr, old + amt)
                        except Exception:
                            pass
        except Exception:
            pass

        try:
            ss = self.score_system
            if ss:
                for name in ["add_money", "award", "add_cash"]:
                    if hasattr(ss, name):
                        try:
                            getattr(ss, name)(float(amt))
                        except Exception:
                            pass
        except Exception:
            pass

    # ------------------ Inicialización sistemas ------------------
    def _initialize_game_systems(self):
        try:
            self.game_manager = GameManager()
            self.job_manager = JobManager()

            # garantizar inventario también aquí
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

                        # asegurar payout
                        try:
                            if not getattr(job, "payout", None):
                                setattr(job, "payout", self._get_job_payout(job))
                        except Exception:
                            pass

                        job.accepted = bool(raw.get("accepted", True))
                        job.picked_up = bool(raw.get("picked_up", False))
                        job.completed = bool(raw.get("completed", False))

                        # si ya estaba completado en el save, NO volver a pagar
                        if job.completed:
                            self._counted_deliveries.add(jid)

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

    # ---------- helpers coords ----------
    def _split_xy_str(self, s: str):
        for sep in [",", "|", ";", " "]:
            if sep in s:
                a, b = s.split(sep, 1)
                return a.strip(), b.strip()
        return None, None

    def _coerce_xy(self, val):
        """Convierte val a (int x, int y) si es posible."""
        try:
            if val is None:
                return None, None
            if isinstance(val, (list, tuple)) and len(val) >= 2:
                return int(float(val[0])), int(float(val[1]))
            if isinstance(val, dict):
                for kx, ky in [("x", "y"), ("cx", "cy"), ("col", "row"), ("c", "r")]:
                    x = val.get(kx, None)
                    y = val.get(ky, None)
                    if x is not None and y is not None:
                        return int(float(x)), int(float(y))
            if isinstance(val, str):
                a, b = self._split_xy_str(val)
                if a is not None and b is not None:
                    return int(float(a)), int(float(b))
        except Exception:
            pass
        return None, None

    def _get_job_pickup_coords(self, job):
        try:
            x, y = self._coerce_xy(getattr(job, "pickup", None))
            if x is not None:
                return x, y
        except Exception:
            pass
        try:
            raw = getattr(job, "raw", {}) or {}
            return self._coerce_xy(raw.get("pickup", None))
        except Exception:
            return (None, None)

    def _get_job_dropoff_coords(self, job):
        try:
            x, y = self._coerce_xy(getattr(job, "dropoff", None))
            if x is not None:
                return x, y
        except Exception:
            pass
        try:
            raw = getattr(job, "raw", {}) or {}
            return self._coerce_xy(raw.get("dropoff", None))
        except Exception:
            return (None, None)

    # ---------- Parser robusto de payout ----------
    def _get_job_payout(self, job_or_raw) -> float:
        # atributos del objeto
        for name in ["payout", "pay", "reward", "price", "amount", "value", "money", "cash"]:
            if hasattr(job_or_raw, name):
                v = getattr(job_or_raw, name)
                if v is not None:
                    parsed = self._parse_money(v)
                    if parsed:
                        return parsed

        # job.raw
        raw = getattr(job_or_raw, "raw", None)
        if isinstance(raw, dict):
            for k in ["payout", "pay", "reward", "price", "amount", "value", "money", "cash"]:
                if k in raw and raw[k] is not None:
                    parsed = self._parse_money(raw[k])
                    if parsed:
                        return parsed

        # si directamente es un dict
        if isinstance(job_or_raw, dict):
            for k in ["payout", "pay", "reward", "price", "amount", "value", "money", "cash"]:
                if k in job_or_raw and job_or_raw[k] is not None:
                    parsed = self._parse_money(job_or_raw[k])
                    if parsed:
                        return parsed

        return 0.0

    # ------------------ Marcadores de jobs ------------------
    def _draw_job_markers(self):
        if not self.job_manager:
            return
        try:
            for job in self.job_manager.all_jobs():
                if getattr(job, "accepted", False) and not getattr(job, "picked_up", False):
                    px_c, py_c = self._get_job_pickup_coords(job)
                    if px_c is not None and py_c is not None:
                        px, py = self._cell_to_pixel(int(px_c), int(py_c))
                        arcade.draw_circle_filled(px, py, TILE_SIZE * 0.4, arcade.color.GOLD)
                        arcade.draw_circle_outline(px, py, TILE_SIZE * 0.4, arcade.color.BLACK, 2)
                        job_label = getattr(job, "id", None) or (getattr(job, "raw", {}) or {}).get("id", "PICKUP")
                        Text(f"{job_label}", px - 18, py + 15, arcade.color.BLACK, 8).draw()

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
        payout = self._get_job_payout(raw)
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

        inventory = self.state.get("inventory") if isinstance(self.state, dict) else getattr(self.state, "inventory", None)
        new_weight = float(raw.get("weight", 1.0))
        if inventory and (getattr(inventory, "current_weight", 0.0) + new_weight > getattr(inventory, "max_weight", 10.0)):
            self.show_notification("❌ Capacidad insuficiente")
            self.rejected_raw_jobs.append(raw)
            self.job_notification_active = False
            self.job_notification_data = None
            return

        if self.job_manager:
            try:
                self.job_manager.add_job_from_raw(raw)  # respetar pickup/dropoff originales
                job = self.job_manager.get_job(jid)
                if job:
                    job.accepted = True
                    if not getattr(job, "payout", None):
                        setattr(job, "payout", self._get_job_payout(job) or self._get_job_payout(raw))
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

    def _draw_job_notification(self):
        if not self.job_notification_active or not self.job_notification_data:
            return
        raw = self.job_notification_data
        job_id = self._raw_job_id(raw)
        payout = self._get_job_payout(raw)
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

    def _compute_fallback_stats(self):
        deliveries = 0
        on_time = 0
        try:
            if self.job_manager:
                for j in self.job_manager.all_jobs():
                    if getattr(j, "completed", False):
                        deliveries += 1
                        if getattr(j, "delivered_on_time", False):
                            on_time += 1
        except Exception:
            pass
        try:
            tr = self.game_manager.get_time_remaining() if self.game_manager else 0
        except Exception:
            tr = 0
        total_money = self._get_state_money()
        return {
            "deliveries_completed": deliveries,
            "on_time_deliveries": on_time,
            "total_money": total_money,
            "time_remaining": tr,
        }

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

        if self.active_notification and self.notification_timer > 0:
            self.notification_text.text = self.active_notification
            self.notification_text.draw()

    def _draw_panel(self):
        _draw_rect_lrbt_filled(MAP_WIDTH, SCREEN_WIDTH, 0, SCREEN_HEIGHT, arcade.color.DARK_SLATE_BLUE)
        _draw_rect_lrbt_outline(MAP_WIDTH, SCREEN_WIDTH, 0, SCREEN_HEIGHT, arcade.color.BLUE, 2)

        self.panel_title.draw()

        # Dinero SIEMPRE desde _get_state_money()
        money = self._get_state_money()
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
                active_jobs = [j for j in self.job_manager.all_jobs()
                               if getattr(j, "accepted", False) and not getattr(j, "completed", False)]
                jobs_info = []
                for job in active_jobs[:8]:
                    status = "✓" if getattr(job, "picked_up", False) else "📦"
                    job_id = getattr(job, "id", "Unknown")
                    payout = self._get_job_payout(job)
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

        stats = None
        if self.score_system:
            try:
                stats = self.score_system.get_current_stats()
            except Exception:
                stats = None
        if not stats:
            stats = self._compute_fallback_stats()

        try:
            tr = stats.get('time_remaining', 0)
            minutes = int(tr // 60)
            seconds = int(tr % 60)
            self.score_text.text = (f"Entregas: {stats.get('deliveries_completed', 0)}\n"
                                    f"A tiempo: {stats.get('on_time_deliveries', 0)}\n"
                                    f"Dinero: ${self._get_state_money():.0f}\n"
                                    f"Tiempo: {minutes:02d}:{seconds:02d}")
        except Exception:
            self.score_text.text = "Cargando..."
        self.score_text.draw()

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
        panel_y = SCREEN_HEIGHT - 100 + 100
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

    # ------------------ Sincronización de dinero ------------------
    def _synchronize_money_with_completed_jobs(self):
        """Garantiza que todo job completado sume exactamente una vez al dinero."""
        if not self.job_manager:
            return
        try:
            for job in self.job_manager.all_jobs():
                if getattr(job, "completed", False):
                    jid = getattr(job, "id", None)
                    if jid and jid not in self._counted_deliveries:
                        payout = self._get_job_payout(job)
                        if payout > 0:
                            self._add_money(payout)
                        self._counted_deliveries.add(jid)
        except Exception as e:
            print(f"[MONEY] Error sincronizando entregas: {e}")

    def _recompute_money_from_jobs(self):
        """Recalcula por si alguna ruta no actualizó state.money; si es mayor, corrige."""
        if not self.job_manager:
            return
        try:
            computed = 0.0
            for job in self.job_manager.all_jobs():
                if getattr(job, "completed", False):
                    computed += self._get_job_payout(job)
            current = self._get_state_money()
            if computed > current:
                self._set_state_money(computed)
                print(f"[MONEY] Recompute -> total ${computed:.2f}")
        except Exception as e:
            print(f"[MONEY] Error recompute: {e}")

    # ---------- helpers inventario ----------
    def _remove_job_from_inventory(self, job):
        """Remueve el job del inventario y, si el peso no cambia automáticamente, ajusta."""
        if job is None:
            return
        inv = self.state.get("inventory") if isinstance(self.state, dict) else getattr(self.state, "inventory", None)
        if not inv:
            return

        cw_before = getattr(inv, "current_weight", None)
        removed = False
        try:
            if hasattr(inv, "remove"):
                inv.remove(job)
                removed = True
            elif hasattr(inv, "deque"):
                for item in list(inv.deque):
                    if getattr(item, "id", None) == getattr(job, "id", None):
                        inv.deque.remove(item)
                        removed = True
                        break
        except Exception as e:
            print(f"[INV] Error remove(): {e}")

        # Ajuste de seguridad del peso si no bajó automáticamente
        try:
            cw_after = getattr(inv, "current_weight", None)
            if cw_before is not None and cw_after is not None:
                wt = float(getattr(job, "weight", 0.0) or 0.0)
                # si tras remover no bajó, forzamos el ajuste
                if removed and wt > 0 and cw_after >= cw_before - 1e-6:
                    try:
                        setattr(inv, "current_weight", max(0.0, float(cw_before) - wt))
                    except Exception:
                        pass
        except Exception:
            pass

    # ------------------ Update ------------------
    def on_update(self, dt: float) -> None:
        if self.game_manager:
            try:
                self.game_manager.update(dt)
            except Exception as e:
                print(f"Error en game_manager.update: {e}")

        if self.job_notification_active:
            self.job_notification_timer -= dt
            if self.job_notification_timer <= 0:
                self._reject_notification()

        if self.next_spawn_timer > 0.0:
            self.next_spawn_timer -= dt

        if not self.job_notification_active:
            self._maybe_start_notification()

        if self.active_notification and self.notification_timer > 0:
            self.notification_timer -= dt
            if self.notification_timer <= 0:
                self.active_notification = None

        input_active = (time.time() - self._last_input_time) < self.INPUT_ACTIVE_WINDOW
        self._ensure_inventory()
        inventory = self.state.get("inventory", None) if isinstance(self.state, dict) else getattr(self.state, "inventory", None)
        was_moving = bool(self.player.moving)

        try:
            self.player.update(dt, player_stats=self.player_stats, weather_system=self.weather_markov, inventory=inventory)
        except Exception:
            try:
                self.player.update(dt)
            except Exception:
                pass

        if was_moving and not self.player.moving:
            px = int(self.player.cell_x)
            py = int(self.player.cell_y)

            picked_up = False
            if self.game_manager and hasattr(self.game_manager, 'try_pickup_at'):
                try:
                    picked_up = self.game_manager.try_pickup_at(px, py)
                except Exception as e:
                    print(f"Error en try_pickup_at: {e}")

            if not picked_up:
                picked_up = self._pickup_nearby()

            if picked_up:
                self.show_notification("¡Paquete recogido! Ve al punto de entrega.")

            delivered = False
            if self.game_manager and hasattr(self.game_manager, 'try_deliver_at'):
                try:
                    result = self.game_manager.try_deliver_at(px, py)
                    if result:
                        delivered = True
                        try:
                            jid = result.get('job_id') if isinstance(result, dict) else None
                            job = self.job_manager.get_job(jid) if (jid and self.job_manager) else None
                        except Exception:
                            job = None

                        # **Remover del inventario también en el flujo de GameManager**
                        self._remove_job_from_inventory(job)

                        # asegurar estado del job
                        try:
                            if job and not getattr(job, "completed", False):
                                job.completed = True
                        except Exception:
                            pass

                        pay_hint = 0.0
                        try:
                            if isinstance(result, dict):
                                pay_hint = result.get("pay", 0)
                        except Exception:
                            pass
                        pay = self._get_job_payout(job) if job is not None else self._parse_money(pay_hint)

                        on_time = True
                        try:
                            if hasattr(self.game_manager, "get_job_time_remaining"):
                                rem = self.game_manager.get_job_time_remaining(
                                    getattr(job, "raw", {}) if job is not None else {}
                                )
                                on_time = (rem == float("inf")) or (rem > 0)
                        except Exception:
                            pass

                        self._notify_delivery(job, pay, on_time)

                        if isinstance(result, dict):
                            jid = result.get('job_id', '¿?')
                            self.show_notification(f"¡Pedido {jid} entregado!\n+${pay:.0f}")
                        else:
                            self.show_notification(f"¡Pedido entregado! +${pay:.0f}")
                except Exception as e:
                    print(f"Error deliver (GameManager): {e}")

            if not delivered:
                delivered = self._try_deliver_at_position(px, py)
                if delivered:
                    self.show_notification("¡Pedido entregado! +$")

        # 1) pagar entregas no contabilizadas
        self._synchronize_money_with_completed_jobs()
        # 2) y forzar consistencia si algo lo desfasó
        self._recompute_money_from_jobs()

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

    # ---------- Centralizar notificación de entrega ----------
    def _notify_delivery(self, job, payout: float, on_time: bool):
        payout = self._parse_money(payout)
        if payout > 0:
            self._add_money(payout)

        jid = getattr(job, "id", None) if job is not None else None

        # **Marcar como contabilizada ya mismo para evitar duplicados**
        try:
            if jid:
                self._counted_deliveries.add(jid)
        except Exception:
            pass

        try:
            if self.game_manager:
                for name in ["register_delivery", "on_job_delivered", "complete_delivery", "record_delivery", "apply_delivery"]:
                    if hasattr(self.game_manager, name):
                        try:
                            getattr(self.game_manager, name)(jid, payout, on_time)
                        except Exception:
                            pass
        except Exception:
            pass

        try:
            ss = self.score_system
            if ss:
                for name in ["register_delivery", "record_delivery", "add_delivery", "on_delivery_completed"]:
                    if hasattr(ss, name):
                        try:
                            getattr(ss, name)(jid, payout, on_time)
                        except Exception:
                            pass
        except Exception:
            pass

        # reputación: leve ajuste
        try:
            rep = getattr(self.player_stats, "reputation", 70)
            rep += 2 if on_time else 1
            setattr(self.player_stats, "reputation", max(0, min(100, rep)))
        except Exception:
            pass

        try:
            if job is not None:
                setattr(job, "delivered_on_time", bool(on_time))
        except Exception:
            pass

    # ------------------ Lógica fallback pickup/dropoff ------------------
    def _pickup_nearby(self) -> bool:
        if not self.job_manager:
            return False

        px = int(self.player.cell_x)
        py = int(self.player.cell_y)
        picked_any = False

        try:
            for job in self.job_manager.all_jobs():
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
        if not self.job_manager:
            return False

        delivered_any = False

        try:
            for job in self.job_manager.all_jobs():
                if not getattr(job, "accepted", False) or not getattr(job, "picked_up", False):
                    continue
                if getattr(job, "completed", False):
                    continue

                dx, dy = self._get_job_dropoff_coords(job)
                if dx is None or dy is None:
                    continue

                cond = (
                    abs(int(dx) - px) + abs(int(dy) - py) <= 1
                    if getattr(self, "DROPOFF_ADJACENT", False)
                    else (int(dx) == px and int(dy) == py)
                )
                if cond:
                    job.completed = True
                    delivered_any = True

                    # Remover del inventario (fallback)
                    self._remove_job_from_inventory(job)

                    payout = self._get_job_payout(job)

                    on_time = True
                    try:
                        if self.game_manager and hasattr(self.game_manager, "get_job_time_remaining"):
                            rem = self.game_manager.get_job_time_remaining(getattr(job, "raw", {}) or {})
                            on_time = (rem == float("inf")) or (rem > 0)
                    except Exception:
                        pass

                    self._notify_delivery(job, payout, on_time)

                    print(f"[DELIVER] Paquete {getattr(job,'id','?')} entregado cerca/en {px},{py} +${payout}")

            return delivered_any
        except Exception as e:
            print(f"[DELIVER] Error en _try_deliver_at_position: {e}")
            return False

    # ------------------ Input ------------------
    def on_key_press(self, key: int, modifiers: int) -> None:
        self._last_input_time = time.time()

        # P: pickup manual (misma o adyacente)
        if key == arcade.key.P:
            try:
                picked = False
                if self.game_manager and hasattr(self.game_manager, 'try_pickup_at'):
                    picked = self.game_manager.try_pickup_at(self.player.cell_x, self.player.cell_y)
                if not picked:
                    picked = self._pickup_nearby()
                if picked:
                    self.show_notification("¡Paquete recogido! Ve al punto de entrega.")
                else:
                    self.show_notification("No hay paquete para recoger aquí o adyacente.")
            except Exception as e:
                print(f"[INPUT] Error recogiendo paquete (P): {e}")
            return

        # E: entrega manual (misma o adyacente)
        if key == arcade.key.E:
            px, py = int(self.player.cell_x), int(self.player.cell_y)
            delivered = False

            if self.game_manager and hasattr(self.game_manager, 'try_deliver_at'):
                try:
                    result = self.game_manager.try_deliver_at(px, py)
                    if result:
                        delivered = True
                        try:
                            jid = result.get('job_id') if isinstance(result, dict) else None
                            job = self.job_manager.get_job(jid) if (jid and self.job_manager) else None
                        except Exception:
                            job = None

                        # también en atajo manual, remover del inventario
                        self._remove_job_from_inventory(job)

                        try:
                            if job and not getattr(job, "completed", False):
                                job.completed = True
                        except Exception:
                            pass

                        pay_hint = 0.0
                        try:
                            if isinstance(result, dict):
                                pay_hint = result.get("pay", 0)
                        except Exception:
                            pass
                        pay = self._get_job_payout(job) if job is not None else self._parse_money(pay_hint)

                        on_time = True
                        try:
                            if hasattr(self.game_manager, "get_job_time_remaining"):
                                rem = self.game_manager.get_job_time_remaining(
                                    getattr(job, "raw", {}) if job is not None else {}
                                )
                                on_time = (rem == float("inf")) or (rem > 0)
                        except Exception:
                            pass

                        self._notify_delivery(job, pay, on_time)

                        if isinstance(result, dict):
                            jid = result.get('job_id', '¿?')
                            self.show_notification(f"¡Pedido {jid} entregado!\n+${pay:.0f}")
                        else:
                            self.show_notification(f"¡Pedido entregado! +${pay:.0f}")
                except Exception as e:
                    print(f"[INPUT] Error deliver (E, GM): {e}")

            if not delivered:
                if self._try_deliver_at_position(px, py):
                    self.show_notification("¡Pedido entregado! +$")
                else:
                    self.show_notification("No hay entrega aquí.")
            return

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

        if key == arcade.key.S:
            if self.inventory_sort_mode == "normal":
                self.inventory_sort_mode = "priority"
            elif self.inventory_sort_mode == "priority":
                self.inventory_sort_mode = "deadline"
            else:
                self.inventory_sort_mode = "normal"
            self.show_notification(f"📋 Ordenando por: {self.inventory_sort_mode}")
            return

        if key == arcade.key.L and modifiers & arcade.key.MOD_CTRL:
            self._load_initial_jobs()
            self.show_notification("🔄 Pedidos recargados")
            return

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

        if key == arcade.key.Z and (modifiers & arcade.key.MOD_CTRL):
            if self.game_manager and hasattr(self.game_manager, 'undo_last_action'):
                if self.game_manager.undo_last_action():
                    self.show_notification("Última acción deshecha")
            return

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

        self._apply_facing()

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
            payout = self._get_job_payout(job_data)
            weight = job_data.get("weight", 0)
            message = f"📦 NUEVO PEDIDO\n{job_id}\nPago: ${payout}\nPeso: {weight}kg\n(A) Aceptar  (R) Rechazar"
            self.show_notification(message)
            self._pending_offer = (on_accept, on_reject)
            self._offer_job_id = job_id
        except Exception as e:
            print(f"Error mostrando oferta: {e}")
            self._pending_offer = None
