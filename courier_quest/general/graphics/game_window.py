import time
import re
import arcade
from arcade import View, Text
from typing import List, Any

from ..run_api.api_client import ApiClient
from .map_manager import GameMap, FLIP_Y
from ..game.player_manager import Player
from ..game.player_stats import PlayerStats
from ..game.weather_markov import WeatherMarkov
from .weather_renderer import WeatherRenderer
from .inventory_ui import InventoryUI
from .notification_manager import NotificationManager
from .jobs_logic import JobsLogic
# from .time_panel_ui import TimePanelUI  # Removed: functionality moved to HUD card
from .money_utils import MoneyUtils
from .weather_coordinator import WeatherCoordinator
# from .stats_panel_ui import StatsPanelUI  # Removed: functionality moved to HUD card
from .coords_utils import CoordsUtils
from .payout_utils import PayoutUtils

from .active_jobs_ui import ActiveJobsUI
from .endgame_manager import EndgameManager
from .save_manager import SaveManager
from .undo_manager import UndoManager
from .game_state_manager import GameStateManager
from .input_handler import InputHandler
from .ui_manager import UIManager
from .update_manager import UpdateManager
from .drawing_utils import _draw_rect_lrbt_filled, _draw_rect_lrbt_outline

from ..game.game_manager import GameManager
from ..game.jobs_manager import JobManager

# Intento de import (para partidas nuevas) — no falla si no existe
try:
    from game.inventory import Inventory
except Exception:
    Inventory = None

SCREEN_WIDTH = 1150
SCREEN_HEIGHT = 800
MAP_WIDTH = 730
TILE_SIZE = 24





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
        # jobs_title y jobs_text removidos - ahora ActiveJobsUI se dibuja completamente por sí mismo
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
        self.apply_emergency_fixes()
        # expose some constants for helper modules
        self.TILE_SIZE = TILE_SIZE
        self.SCREEN_WIDTH = SCREEN_WIDTH

        # helper modules
        self.inventory_ui = InventoryUI(self)
        self.notifications = NotificationManager(self)
        self.jobs_logic = JobsLogic(self)
        # self.time_panel = TimePanelUI(self)  # Removed: functionality moved to HUD card
        self.money = MoneyUtils(self)
        self.weather = WeatherCoordinator(self)
        # self.stats_panel = StatsPanelUI(self)  # Removed: functionality moved to HUD card
        self.coords = CoordsUtils(self)
        self.payouts = PayoutUtils(self)
        # self.right_panel = RightPanelUI(self)  # Removed: replaced by HUD card
        self.active_jobs_ui = ActiveJobsUI(self)
        self.endgame = EndgameManager(self)
        
        # New component managers for refactored MapPlayerView
        self.game_state_manager = GameStateManager(self)
        self.input_handler = InputHandler(self)
        self.ui_manager = UIManager(self)
        self.update_manager = UpdateManager(self)

        
        self.save_manager = SaveManager(self)
        self.undo = UndoManager(self)
        
        # Inventario con navegación
        self.inventory_view_index = 0
        self.inventory_left_button_rect = None
        self.inventory_right_button_rect = None
        
        # Botón de deshacer
        self.undo_button_rect = None
        self.undo_button_visible = True
        
        # Overlay de fin de juego
        self._show_lose_overlay = False
        self._lose_reason = ""

        # bind legacy money helpers to new utils (backward compatibility)
        self._parse_money = self.money.parse_money
        self._get_state_money = self.money.get_state_money
        self._set_state_money = self.money.set_state_money
        self._add_money = self.money.add_money
        self._split_xy_str = self.coords.split_xy_str
        self._coerce_xy = self.coords.coerce_xy
        self._get_job_payout = self.payouts.get_job_payout

    # ---------- Inventario para partidas nuevas y cargadas ----------
    def _ensure_inventory(self):
        try:
            if isinstance(self.state, dict):
                inv = self.state.get("inventory", None)
                if inv is None and Inventory is not None:
                    self.state["inventory"] = Inventory()
                # Asegurar que también esté disponible como atributo directo
                if inv is not None:
                    self.inventory = inv
                elif hasattr(self, "inventory") and self.inventory is None:
                    self.inventory = self.state["inventory"]
            else:
                inv = getattr(self.state, "inventory", None)
                if inv is None and Inventory is not None:
                    setattr(self.state, "inventory", Inventory())
                # Asegurar que también esté disponible como atributo directo
                if inv is not None:
                    self.inventory = inv
                elif hasattr(self, "inventory") and self.inventory is None:
                    self.inventory = getattr(self.state, "inventory", None)
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
            # Evitar inicializaciones duplicadas
            if not hasattr(self, 'game_manager') or self.game_manager is None:
                self.game_manager = GameManager()
            if not hasattr(self, 'job_manager') or self.job_manager is None:
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
                    # First try to load from 'player' dict (new format)
                    player_data = self.state.get("player") if isinstance(self.state, dict) else getattr(self.state, "player", None)
                    if player_data and isinstance(player_data, dict):
                        px = player_data.get("cell_x")
                        py = player_data.get("cell_y")
                        if px is not None and py is not None:
                            self.player.cell_x = int(px)
                            self.player.cell_y = int(py)
                            self.player.pixel_x, self.player.pixel_y = self.player.cell_to_pixel(self.player.cell_x, self.player.cell_y)
                            self.player.target_pixel_x, self.player.target_pixel_y = self.player.pixel_x, self.player.pixel_y
                            self.player.moving = player_data.get("moving", False)
                            self.player.target_surface_weight = player_data.get("target_surface_weight", 1.0)
                            self.player.base_cells_per_sec = player_data.get("base_cells_per_sec", self.player.base_cells_per_sec)
                    else:
                        # Fallback to old format
                        px = self.state.get("player_x") if isinstance(self.state, dict) else getattr(self.state, "player_x", None)
                        py = self.state.get("player_y") if isinstance(self.state, dict) else getattr(self.state, "player_y", None)
                        if px is not None and py is not None:
                            self.player.cell_x = int(px)
                            self.player.cell_y = int(py)
                            self.player.pixel_x, self.player.pixel_y = self.player.cell_to_pixel(self.player.cell_x, self.player.cell_y)
                            self.player.target_pixel_x, self.player.target_pixel_y = self.player.pixel_x, self.player.pixel_y
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

        # 5) Limpiar inventario: remover trabajos completados y recalcular peso
        try:
            inv = self.state.get("inventory") if isinstance(self.state, dict) else getattr(self.state, "inventory", None)
            if inv and hasattr(inv, 'deque') and inv.deque:
                # Remover trabajos completados
                inv.deque = [job for job in inv.deque if not getattr(job, 'completed', False)]
                # Recalcular peso actual
                inv.current_weight = sum(float(getattr(job, 'weight', 0.0)) for job in inv.deque)
                print(f"[INVENTORY] Limpiado: {len(inv.deque)} items restantes, peso total {inv.current_weight:.1f}")
        except Exception as e:
            print(f"[LOAD] Error limpiando inventario: {e}")

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

    # ------------------ Notificaciones / Jobs ------------------

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

    # Job notification drawing now handled by NotificationManager

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
        self.ui_manager.on_draw()

    def _draw_panel(self):
        # self.right_panel.draw_frame()  # Removed: replaced by HUD card

        # --- Inventario con navegación ---
        self._draw_inventory_panel()

        # --- Pedidos activos ---
        self.active_jobs_ui.draw()

        # --- Botón de deshacer ---
        self._draw_undo_button()

    def _draw_hud_card(self):
        # Medidas responsivas - ahora en el lado derecho
        w = getattr(self, 'SCREEN_WIDTH', self.width)
        h = getattr(self, 'SCREEN_HEIGHT', self.height)
        map_width = getattr(self, 'MAP_WIDTH', 730)
        card_w = int(min(350, (w - map_width) * 0.9))
        card_h = 180  # Reducido para que quepa todo
        left = map_width + 10
        top = h - 10
        bottom = top - card_h
        right = left + card_w
        _draw_rect_lrbt_filled(left, right, bottom, top, (25, 30, 45))
        _draw_rect_lrbt_outline(left, right, bottom, top, (70, 85, 110), 2)

        # Función para dibujar barras de progreso más pequeñas
        def draw_progress_bar(x, y, width, height, value01, fill_color, bg_color=(40, 45, 60)):
            _draw_rect_lrbt_filled(x, x + width, y - height, y, bg_color)
            _draw_rect_lrbt_outline(x, x + width, y - height, y, (60, 70, 90), 1)
            fill_width = int(max(0, min(1, value01)) * width)
            if fill_width > 0:
                _draw_rect_lrbt_filled(x, x + fill_width, y - height, y, fill_color)

        # Tiempo - más compacto
        try:
            gm = self.game_manager
            rem = gm.get_time_remaining() if gm else 0
            m = int(rem // 60); s = int(rem % 60)
            Text("⏰ Tiempo", left + 12, top - 20, (200, 210, 220), 10).draw()
            Text(f"{m:02d}:{s:02d}", left + 12, top - 32, (240, 246, 255), 14, bold=True).draw()
        except Exception:
            Text("⏰ Tiempo", left + 12, top - 20, (200, 210, 220), 10).draw()
            Text("15:00", left + 12, top - 32, (240, 246, 255), 14, bold=True).draw()

        # Ingresos / Meta - más compacto
        try:
            goal = 1500  # Valor por defecto
            try:
                # Intentar obtener la meta del estado del juego primero
                if hasattr(self.state, "income_goal"):
                    goal = int(self.state.income_goal)
                elif isinstance(self.state, dict) and "income_goal" in self.state:
                    goal = int(self.state["income_goal"])
                else:
                    # Fallback al map_data
                    _m = self.state.get("map_data", {}) if isinstance(self.state, dict) else getattr(self.state, "map_data", {})
                    goal = int((_m or {}).get("goal", 1500))
            except Exception:
                pass
            money = self._get_state_money()
            Text("$ Ingresos / Meta", left + 12, top - 50, (120, 220, 160), 10).draw()
            Text(f"${int(money)} / ${goal}", left + 12, top - 62, (240, 246, 255), 14, bold=True).draw()
        except Exception:
            pass

        # Resistencia con barra - más compacto
        try:
            Text("🔋 Resistencia", left + 12, top - 80, (200, 210, 220), 10).draw()
            stamina = getattr(self.player_stats, "stamina", 100)
            draw_progress_bar(left + 12, top - 90, card_w - 24, 8, stamina / 100.0, (80, 200, 255))
        except Exception:
            pass

        # Reputación con barra - más compacto
        try:
            Text("⭐ Reputación", left + 12, top - 105, (200, 210, 220), 10).draw()
            rep = getattr(self.player_stats, "reputation", 70)
            draw_progress_bar(left + 12, top - 115, card_w - 24, 8, rep / 100.0, (255, 220, 120))
        except Exception:
            pass

        # Peso con barra - más compacto
        try:
            inv = self.state.get("inventory") if isinstance(self.state, dict) else getattr(self.state, "inventory", None)
            weight = float(getattr(inv, "current_weight", 0.0) or 0.0)
            max_weight = 10.0
            Text("📦 Peso", left + 12, top - 130, (200, 210, 220), 10).draw()
            Text(f"{weight:.1f} / {max_weight:.0f} kg", left + 12, top - 142, (230, 236, 245), 10).draw()
            draw_progress_bar(left + 12, top - 150, card_w - 24, 8, weight / max_weight, (255, 180, 100))
        except Exception:
            pass

        # Clima - integrado en la misma ventana, más compacto
        try:
            cond = self.weather.get_current_condition_name()
            # Mapear nombres de clima a español
            clima_map = {
                "clear": "Despejado",
                "clouds": "Nublado", 
                "rain": "Lluvia",
                "storm": "Tormenta",
                "fog": "Niebla",
                "wind": "Viento",
                "heat": "Calor",
                "cold": "Frío"
            }
            clima_text = clima_map.get(cond, cond)
            Text("☁ Clima", left + 12, top - 165, (200, 210, 220), 10).draw()
            Text(clima_text, left + 12, top - 177, (230, 236, 245), 10).draw()
        except Exception:
            Text("☁ Clima", left + 12, top - 165, (200, 210, 220), 10).draw()
            Text("Despejado", left + 12, top - 177, (230, 236, 245), 10).draw()

    def _draw_inventory_panel(self):
        """Dibuja el panel de inventario con navegación izquierda/derecha"""
        w = getattr(self, 'SCREEN_WIDTH', self.width)
        h = getattr(self, 'SCREEN_HEIGHT', self.height)
        map_width = getattr(self, 'MAP_WIDTH', 730)
        
        # Panel de inventario debajo del HUD - más compacto
        panel_w = int(min(350, (w - map_width) * 0.9))
        panel_h = 250  # Reducido
        left = map_width + 10
        top = h - 200  # Más cerca del HUD
        bottom = top - panel_h
        right = left + panel_w
        
        # Fondo del panel
        _draw_rect_lrbt_filled(left, right, bottom, top, (25, 30, 45))
        _draw_rect_lrbt_outline(left, right, bottom, top, (70, 85, 110), 2)
        
        # Título más pequeño
        Text("📦 INVENTARIO", left + 12, top - 20, (255, 220, 120), 12, bold=True).draw()
        
        # Obtener inventario
        try:
            inv = self.state.get("inventory") if isinstance(self.state, dict) else getattr(self.state, "inventory", None)
            if inv is None:
                Text("No hay inventario disponible", left + 15, top - 50, (200, 200, 200), 12).draw()
                return
                
            # Obtener lista de items
            items = []
            if hasattr(inv, 'deque') and inv.deque:
                items = list(inv.deque)
            elif hasattr(inv, 'items') and inv.items:
                items = list(inv.items)
            elif hasattr(inv, '__iter__'):
                items = list(inv)
                
            if not items:
                Text("Inventario vacío", left + 12, top - 45, (200, 200, 200), 10).draw()
                return
                
            # Navegación
            total_items = len(items)
            if total_items > 0:
                current_item = items[self.inventory_view_index % total_items]
                
                # Información del item actual - más compacta
                item_id = getattr(current_item, 'id', 'Unknown')
                item_payout = getattr(current_item, 'payout', 0)
                item_weight = getattr(current_item, 'weight', 0)
                item_pickup = getattr(current_item, 'pickup', [0, 0])
                item_dropoff = getattr(current_item, 'dropoff', [0, 0])
                
                # Mostrar información del item - más compacta
                Text(f"ID: {item_id}", left + 12, top - 40, (240, 246, 255), 10).draw()
                Text(f"Pago: ${item_payout}", left + 12, top - 55, (120, 220, 160), 10).draw()
                Text(f"Peso: {item_weight}kg", left + 12, top - 70, (255, 180, 100), 10).draw()
                Text(f"Recogida: ({item_pickup[0]}, {item_pickup[1]})", left + 12, top - 85, (200, 200, 200), 9).draw()
                Text(f"Entrega: ({item_dropoff[0]}, {item_dropoff[1]})", left + 12, top - 100, (200, 200, 200), 9).draw()
                
                # Contador de items - más compacto
                Text(f"Item {self.inventory_view_index + 1} de {total_items}", left + 12, top - 120, (180, 196, 220), 10).draw()
                
                # Botones de navegación - más pequeños
                if total_items > 1:
                    # Botón izquierda
                    btn_w = 50
                    btn_h = 25
                    btn_left = left + 12
                    btn_right = left + 12 + btn_w
                    btn_bottom = top - 160
                    btn_top = btn_bottom + btn_h
                    
                    # Guardar coordenadas para detección de clics
                    self.inventory_left_button_rect = (btn_left, btn_bottom, btn_right, btn_top)
                    
                    _draw_rect_lrbt_filled(btn_left, btn_right, btn_bottom, btn_top, (60, 70, 90))
                    _draw_rect_lrbt_outline(btn_left, btn_right, btn_bottom, btn_top, (100, 120, 140), 1)
                    Text("◀", btn_left + btn_w//2, btn_bottom + btn_h//2, (240, 246, 255), 12, 
                         anchor_x="center", anchor_y="center").draw()
                    
                    # Botón derecha
                    btn_left = left + 70
                    btn_right = btn_left + btn_w
                    
                    # Guardar coordenadas para detección de clics
                    self.inventory_right_button_rect = (btn_left, btn_bottom, btn_right, btn_top)
                    
                    _draw_rect_lrbt_filled(btn_left, btn_right, btn_bottom, btn_top, (60, 70, 90))
                    _draw_rect_lrbt_outline(btn_left, btn_right, btn_bottom, btn_top, (100, 120, 140), 1)
                    Text("▶", btn_left + btn_w//2, btn_bottom + btn_h//2, (240, 246, 255), 12, 
                         anchor_x="center", anchor_y="center").draw()
                    
                    # Instrucciones - más pequeñas
                    Text("Usa A/D para navegar", left + 12, top - 200, (180, 196, 220), 9).draw()
                    
        except Exception as e:
            Text(f"Error cargando inventario: {str(e)[:30]}", left + 12, top - 50, (255, 120, 120), 10).draw()

    def _draw_undo_button(self):
        """Dibuja el botón de deshacer en la mitad derecha de la pantalla"""
        if not self.undo_button_visible:
            return
            
        w = getattr(self, 'SCREEN_WIDTH', self.width)
        h = getattr(self, 'SCREEN_HEIGHT', self.height)
        
        # Posición del botón en la mitad derecha de la pantalla
        btn_w = 100
        btn_h = 35
        btn_left = w - btn_w - 10  # Mismo margen que el botón de menú
        btn_top = h // 2 + btn_h // 2  # Mitad de la pantalla
        btn_right = btn_left + btn_w
        btn_bottom = btn_top - btn_h
        
        # Guardar rectángulo para detección de clics
        self.undo_button_rect = (btn_left, btn_bottom, btn_right, btn_top)
        
        # Fondo del botón (blanco con bordes redondeados simulados)
        _draw_rect_lrbt_filled(btn_left, btn_right, btn_bottom, btn_top, (255, 255, 255))
        _draw_rect_lrbt_outline(btn_left, btn_right, btn_bottom, btn_top, (200, 200, 200), 1)
        
        # Sombra sutil en la parte inferior
        _draw_rect_lrbt_filled(btn_left, btn_right, btn_bottom - 2, btn_bottom, (180, 180, 180))
        
        # Icono de deshacer (flecha circular)
        icon_x = btn_left + 12
        icon_y = btn_bottom + btn_h // 2
        
        # Dibujar flecha circular simple
        arcade.draw_circle_outline(icon_x, icon_y, 6, (0, 0, 0), 2)
        # Flecha apuntando hacia la izquierda
        arcade.draw_line(icon_x - 3, icon_y, icon_x + 1, icon_y - 2, (0, 0, 0), 2)
        arcade.draw_line(icon_x - 3, icon_y, icon_x + 1, icon_y + 2, (0, 0, 0), 2)
        
        # Texto "Deshacer" más pequeño
        Text("Deshacer", btn_left + 25, btn_bottom + btn_h // 2, (0, 0, 0), 10, bold=True, 
             anchor_x="left", anchor_y="center").draw()

    def _draw_lose_overlay(self):
        w = getattr(self, 'SCREEN_WIDTH', self.width)
        h = getattr(self, 'SCREEN_HEIGHT', self.height)
        # fondo semitransparente
        try:
            arcade.draw_lrbt_rectangle_filled(0, w, 0, h, (0, 0, 0, 180))
        except Exception:
            _draw_rect_lrbt_filled(0, w, 0, h, (10, 10, 14))
        # tarjeta central
        card_w = int(min(520, w * 0.7))
        card_h = 240
        cx = w // 2; cy = h // 2
        left = cx - card_w//2; right = cx + card_w//2
        bottom = cy - card_h//2; top = cy + card_h//2
        _draw_rect_lrbt_filled(left, right, bottom, top, (25, 28, 45))
        _draw_rect_lrbt_outline(left, right, bottom, top, (120, 100, 220), 3)
        Text("❌ Derrota", left + 24, top - 40, (255, 120, 120), 24, bold=True).draw()
        Text(self._lose_reason or "", left + 24, top - 70, (230, 236, 245), 14).draw()
        Text("Presiona cualquier tecla para volver al menú", left + 24, bottom + 28, (200, 210, 220), 12).draw()

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

    # Money sync now handled by JobsLogic

    # Inventory adjustments now handled by JobsLogic

    # ------------------ Update ------------------
    def on_update(self, dt: float) -> None:
        self.update_manager.on_update(dt)

    # Delivery notification now handled by JobsLogic

    # Pickup/Delivery fallbacks now handled by JobsLogic

    # ------------------ Input ------------------
    def on_key_press(self, key: int, modifiers: int) -> None:
        self._last_input_time = time.time()

        if self._show_lose_overlay:
            # cualquier tecla: volver al menú
            try:
                from .ui_view_gui import GameMenuView
                self.window.show_view(GameMenuView())
            except Exception:
                pass
            return

        # snapshot for undo on any significant key
        try:
            if key in (arcade.key.UP, arcade.key.DOWN, arcade.key.LEFT, arcade.key.RIGHT, 
                      arcade.key.W, arcade.key.A, arcade.key.S, arcade.key.D, 
                      arcade.key.P, arcade.key.E):
                self.undo.snapshot()
        except Exception:
            pass

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
                                # on_time = True si no hay deadline o si aún hay tiempo restante
                                on_time = (rem == float("inf")) or (rem >= 0)
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
                self.notifications.accept_current()
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
            # Navegación del inventario - ir al item anterior
            try:
                inv = self.state.get("inventory") if isinstance(self.state, dict) else getattr(self.state, "inventory", None)
                if inv:
                    items = []
                    if hasattr(inv, 'deque') and inv.deque:
                        items = list(inv.deque)
                    elif hasattr(inv, 'items') and inv.items:
                        items = list(inv.items)
                    elif hasattr(inv, '__iter__'):
                        items = list(inv)
                    
                    if len(items) > 1:
                        self.inventory_view_index = (self.inventory_view_index - 1) % len(items)
                        self.show_notification(f"Item {self.inventory_view_index + 1} de {len(items)}")
                        return
            except Exception:
                pass
            if self.inventory_ui.handle_key_A():
                return

        if key == arcade.key.D:
            if self.job_notification_active and self.job_notification_data:
                return
            # Navegación del inventario - ir al item siguiente
            try:
                inv = self.state.get("inventory") if isinstance(self.state, dict) else getattr(self.state, "inventory", None)
                if inv:
                    items = []
                    if hasattr(inv, 'deque') and inv.deque:
                        items = list(inv.deque)
                    elif hasattr(inv, 'items') and inv.items:
                        items = list(inv.items)
                    elif hasattr(inv, '__iter__'):
                        items = list(inv)
                    
                    if len(items) > 1:
                        self.inventory_view_index = (self.inventory_view_index + 1) % len(items)
                        self.show_notification(f"Item {self.inventory_view_index + 1} de {len(items)}")
                        return
            except Exception:
                pass
            if self.inventory_ui.handle_key_D():
                        return

        if key == arcade.key.R:
            if self.job_notification_active and self.job_notification_data:
                self.notifications.reject_current()
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
            if self.inventory_ui.handle_key_S():
                return

        if key == arcade.key.L and modifiers & arcade.key.MOD_CTRL:
            self._load_initial_jobs()
            self.show_notification("🔄 Pedidos recargados")
            return

        # Ctrl+Shift+S: Guardar
        if key == arcade.key.S and (modifiers & arcade.key.MOD_CTRL) and (modifiers & arcade.key.MOD_SHIFT):
            # Add player position and elapsed time to state before saving
            try:
                self.state["player_x"] = self.player.cell_x
                self.state["player_y"] = self.player.cell_y
                if self.game_manager and hasattr(self.game_manager, "get_game_time"):
                    self.state["elapsed_seconds"] = self.game_manager.get_game_time()
            except Exception as e:
                print(f"[SAVE] Error adding player position: {e}")
            if self.save_manager.save():
                self.show_notification("💾 Partida guardada")
            else:
                self.show_notification("❌ Error al guardar")
            return

        # Ctrl+O: Cargar
        if key == arcade.key.O and (modifiers & arcade.key.MOD_CTRL):
            if self.save_manager.load():
                # re-inicializar sistemas con flag de reanudación
                try:
                    if isinstance(self.state, dict):
                        self.state["__resume_from_save__"] = True
                    else:
                        setattr(self.state, "__resume_from_save__", True)
                except Exception:
                    pass
                self._initialize_game_systems()
                self.show_notification("📂 Partida cargada")
            else:
                self.show_notification("❌ Error al cargar")
            return

        # Manejo de movimiento con WASD y flechas
        dx, dy = 0, 0
        if key == arcade.key.UP or key == arcade.key.W:
            dy = -1
            self.facing = "up"
        elif key == arcade.key.DOWN or key == arcade.key.S:
            dy = 1
            self.facing = "down"
        elif key == arcade.key.LEFT or key == arcade.key.A:
            dx = -1
            self.facing = "left"
        elif key == arcade.key.RIGHT or key == arcade.key.D:
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

    def _handle_undo(self):
        """Maneja la lógica de deshacer (usado tanto por teclado como por botón)"""
        undone = False
        if self.game_manager and hasattr(self.game_manager, 'undo_last_action'):
            try:
                undone = bool(self.game_manager.undo_last_action())
            except Exception:
                undone = False
        if not undone:
            if self.undo.restore():
                undone = True
        if undone:
            self.show_notification("Última acción deshecha")
        else:
            self.show_notification("No hay acciones para deshacer")

    def _navigate_inventory_left(self):
        """Navega hacia la izquierda en el inventario"""
        try:
            inv = self.state.get("inventory") if isinstance(self.state, dict) else getattr(self.state, "inventory", None)
            if inv:
                items = []
                if hasattr(inv, 'deque') and inv.deque:
                    items = list(inv.deque)
                elif hasattr(inv, 'items') and inv.items:
                    items = list(inv.items)
                elif hasattr(inv, '__iter__'):
                    items = list(inv)
                
                if len(items) > 1:
                    self.inventory_view_index = (self.inventory_view_index - 1) % len(items)
                    self.show_notification(f"Item {self.inventory_view_index + 1} de {len(items)}")
        except Exception:
            pass

    def _navigate_inventory_right(self):
        """Navega hacia la derecha en el inventario"""
        try:
            inv = self.state.get("inventory") if isinstance(self.state, dict) else getattr(self.state, "inventory", None)
            if inv:
                items = []
                if hasattr(inv, 'deque') and inv.deque:
                    items = list(inv.deque)
                elif hasattr(inv, 'items') and inv.items:
                    items = list(inv.items)
                elif hasattr(inv, '__iter__'):
                    items = list(inv)
                
                if len(items) > 1:
                    self.inventory_view_index = (self.inventory_view_index + 1) % len(items)
                    self.show_notification(f"Item {self.inventory_view_index + 1} de {len(items)}")
        except Exception:
            pass

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        """Maneja clics del mouse para botones de UI"""
        if button == arcade.MOUSE_BUTTON_LEFT:
            # Botón de deshacer
            if self.undo_button_rect:
                btn_left, btn_bottom, btn_right, btn_top = self.undo_button_rect
                if btn_left <= x <= btn_right and btn_bottom <= y <= btn_top:
                    self._handle_undo()
                    return
            
            # Botones del inventario
            if self.inventory_left_button_rect:
                btn_left, btn_bottom, btn_right, btn_top = self.inventory_left_button_rect
                if btn_left <= x <= btn_right and btn_bottom <= y <= btn_top:
                    self._navigate_inventory_left()
                    return
            
            if self.inventory_right_button_rect:
                btn_left, btn_bottom, btn_right, btn_top = self.inventory_right_button_rect
                if btn_left <= x <= btn_right and btn_bottom <= y <= btn_top:
                    self._navigate_inventory_right()
                    return

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

    # En MapPlayerView - AGREGAR estos métodos
    def _initialize_game_time_systems(self):
        """✅ NUEVO: Integración correcta de sistemas de tiempo"""
        try:
            # Obtener start_time del mapa
            map_data = self.state.get("map_data", {}) if isinstance(self.state, dict) else getattr(self.state,
                                                                                                   "map_data", {})
            start_time_str = map_data.get("start_time", "2025-09-01T12:00:00Z")

            # Configurar GameManager
            if self.game_manager:
                # Si GameManager tiene método para configurar tiempo, usarlo
                if hasattr(self.game_manager, 'set_game_start_time'):
                    self.game_manager.set_game_start_time(start_time_str)
                elif hasattr(self.game_manager, '_game_start_epoch'):
                    from datetime import datetime
                    start_dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                    self.game_manager._game_start_epoch = start_dt.timestamp()

            # Configurar JobManager
            if self.job_manager and hasattr(self.job_manager, '_game_start_epoch'):
                from datetime import datetime
                start_dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                self.job_manager._game_start_epoch = start_dt.timestamp()
                print(f"✅ Tiempo configurado: {start_time_str}")

        except Exception as e:
            print(f"❌ Error configurando tiempo: {e}")

    def apply_emergency_fixes(self):
        """✅ NUEVO: Parches de emergencia para problemas críticos"""
        print("🔧 APLICANDO PARCHES DE EMERGENCIA")

        # 1. Configurar tiempo real
        self._initialize_game_time_systems()

        # 2. Verificar integración
        self._verify_systems_integration()

        # 3. Diagnosticar problemas
        self._diagnose_issues()

    def _verify_systems_integration(self):
        """Verifica que todos los sistemas estén conectados"""
        issues = []

        # Verificar GameManager
        if not self.game_manager:
            issues.append("❌ GameManager no inicializado")
        else:
            try:
                current_time = self.game_manager.get_game_time()
                print(f"✅ GameManager tiempo: {current_time:.1f}s")
            except Exception as e:
                issues.append(f"❌ GameManager error: {e}")

        # Verificar JobManager
        if not self.job_manager:
            issues.append("❌ JobManager no inicializado")
        elif not hasattr(self.job_manager, '_game_start_epoch'):
            issues.append("❌ JobManager sin _game_start_epoch")
        else:
            print(f"✅ JobManager configurado")

        # Verificar reputación
        if not hasattr(self, 'player_stats') or not self.player_stats:
            issues.append("❌ PlayerStats no inicializado")
        else:
            print(f"✅ PlayerStats: reputación={self.player_stats.reputation}")

        if issues:
            print("🔍 PROBLEMAS ENCONTRADOS:")
            for issue in issues:
                print(f"   {issue}")
        else:
            print("✅ Todos los sistemas integrados correctamente")

    def _diagnose_issues(self):
        """Diagnóstico detallado de problemas"""
        print("\n🔍 DIAGNÓSTICO DETALLADO:")

        # Verificar trabajos disponibles
        if self.game_manager and self.job_manager:
            try:
                current_time = self.game_manager.get_game_time()
                available_jobs = self.job_manager.get_available_jobs(current_time)
                print(f"📦 Trabajos disponibles: {len(available_jobs)}")

                for job in available_jobs:
                    release_time = getattr(job, 'release_time', 0)
                    status = "✅ DISPONIBLE" if release_time <= current_time else f"⏰ En {release_time - current_time:.0f}s"
                    print(f"   - {job.id}: {status}")

            except Exception as e:
                print(f"❌ Error diagnosticando trabajos: {e}")