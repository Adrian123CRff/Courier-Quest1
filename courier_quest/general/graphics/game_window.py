# game/game_window.py
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

# Sistemas de alto nivel (tu proyecto)
from game.game_manager import GameManager
from game.jobs_manager import JobManager

# Configuración
SCREEN_WIDTH = 1150
SCREEN_HEIGHT = 800
MAP_WIDTH = 730
PANEL_WIDTH = 300
TILE_SIZE = 24


# Helper functions (compatibles con arcade 3.3.2)
def _draw_rect_lrbt_filled(left: float, right: float, bottom: float, top: float, color):
    pts = [(left, bottom), (right, bottom), (right, top), (left, top)]
    arcade.draw_polygon_filled(pts, color)


def _draw_rect_lrbt_outline(left: float, right: float, bottom: float, top: float, color, border_width=2):
    pts = [(left, bottom), (right, bottom), (right, top), (left, top)]
    arcade.draw_polygon_outline(pts, color, border_width)


class MapPlayerView(View):
    def __init__(self, state) -> None:
        super().__init__()
        # state puede ser dict (desde UI) o PlayerState (desde GameManager)
        self.state = state or {}

        # Sistemas de juego
        self.game_manager: Any = None
        self.job_manager: Any = None
        self.score_system: Any = None

        # Inicializar player_stats - compatibilidad con dict o player_state
        if isinstance(self.state, dict):
            if "player_stats" not in self.state or self.state.get("player_stats") is None:
                self.state["player_stats"] = PlayerStats()
            self.player_stats: PlayerStats = self.state["player_stats"]
        else:
            self.player_stats = getattr(self.state, "player_stats", None) or PlayerStats()

        # Mapa y jugador
        cm = self.state["city_map"] if isinstance(self.state, dict) else getattr(self.state, "city_map", {})
        self.game_map = GameMap(cm)

        rows = len(self.game_map.grid)
        cols = len(self.game_map.grid[0]) if rows > 0 else 0

        start_cx = cols // 2
        start_cy = rows // 2
        self.player: Player = Player((start_cx, start_cy), TILE_SIZE, rows, flip_y=FLIP_Y)

        # Bind de stats (player_manager usa bound_stats para checks/consumo)
        try:
            self.player.bind_stats(self.player_stats)
        except Exception:
            self.player.bound_stats = self.player_stats

        # Ajustar escala del sprite para que quepa 1 celda
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

        # Jobs / UI / notificaciones
        self.incoming_raw_jobs: List[dict] = []
        self.rejected_raw_jobs: List[dict] = []
        self.accepted_job_ids = set()
        self.notification_active = False
        self.notification_timer = 0.0
        self.next_spawn_timer = 0.0
        self.NOTIF_ACCEPT_SECONDS = 10.0
        self.NEXT_SPAWN_AFTER_ACCEPT = 10.0

        # Text objects (Arcade 3.3.2)
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
        # Centrado en la barra de stamina
        self.stamina_text = Text(
            "",
            MAP_WIDTH + 150,
            50,
            arcade.color.WHITE,
            12,
            anchor_x="center",
            anchor_y="center"
        )

        # Notificación de trabajo (mejorada)
        self.job_notification_active = False
        self.job_notification_data = None
        self.job_notification_timer = 0.0

        # Clima
        self.weather_markov = WeatherMarkov(api=ApiClient())
        self.weather_renderer = WeatherRenderer(self)

        # Input tracking para "input_active"
        self._last_input_time = 0.0
        self.INPUT_ACTIVE_WINDOW = 0.25

        # Notificaciones y ofertas
        self.active_notification = None
        self.NOTIFICATION_DURATION = 5.0
        self._pending_offer = None
        self._offer_job_id = None

        # Inicializar managers (ahora preferimos el job_manager creado POR GameManager)
        self._initialize_game_systems()

    # --------------- Helpers gráficos seguros ---------------
    @staticmethod
    def _draw_rect_lrbt_filled(left: float, right: float, bottom: float, top: float, color):
        pts = [(left, bottom), (right, bottom), (right, top), (left, top)]
        arcade.draw_polygon_filled(pts, color)

    @staticmethod
    def _draw_rect_lrbt_outline(left: float, right: float, bottom: float, top: float, color, border_width=2):
        pts = [(left, bottom), (right, bottom), (right, top), (left, top)]
        arcade.draw_polygon_outline(pts, color, border_width)

    @staticmethod
    def _draw_centered_rect_filled(cx: float, cy: float, width: float, height: float, color):
        half_w = width / 2.0
        half_h = height / 2.0
        pts = [(cx - half_w, cy - half_h), (cx + half_w, cy - half_h), (cx + half_w, cy + half_h), (cx - half_w, cy + half_h)]
        arcade.draw_polygon_filled(pts, color)

    @staticmethod
    def _draw_centered_rect_outline(cx: float, cy: float, width: float, height: float, color, border_width=2):
        half_w = width / 2.0
        half_h = height / 2.0
        pts = [(cx - half_w, cy - half_h), (cx + half_w, cy - half_h), (cx + half_w, cy + half_h), (cx - half_w, cy + half_h)]
        arcade.draw_polygon_outline(pts, color, border_width)

    # ------------------ Inicialización sistemas ------------------
    def _initialize_game_systems(self):
        """
        Inicializa GameManager. Importante: usamos el JobManager que crea GameManager
        para evitar desincronías entre managers (jobs que existen en uno y no en otro).
        """
        try:
            # Crear e inicializar GameManager (éste crea su propio JobManager y PlayerState)
            self.game_manager = GameManager()

            # Extraer datos del state (si vienen)
            if isinstance(self.state, dict):
                map_data = self.state.get("map_data", {})
                jobs_data = self.state.get("orders", [])
                weather_data = self.state.get("weather_data", {})
            else:
                map_data = getattr(self.state, "map_data", {})
                jobs_data = getattr(self.state, "orders", [])
                weather_data = getattr(self.state, "weather_data", {})

            # Inicializar el game manager (tolerante si la firma varía)
            try:
                self.game_manager.initialize_game(map_data, jobs_data, weather_data)
            except Exception:
                # si initialize_game no existe o falla, seguir con fallback
                pass

            # Preferir el job_manager que creó el GameManager (si existe)
            try:
                if hasattr(self.game_manager, "job_manager") and getattr(self.game_manager, "job_manager") is not None:
                    self.job_manager = self.game_manager.job_manager
                else:
                    # fallback local
                    self.job_manager = JobManager()
            except Exception:
                self.job_manager = JobManager()

            # Si GameManager tiene player_state, usarlo como self.state (unificar acceso)
            try:
                if hasattr(self.game_manager, "player_state") and getattr(self.game_manager, "player_state") is not None:
                    # sustituimos el state local por el PlayerState del GameManager para coherencia
                    self.state = self.game_manager.player_state
                    # rehacer player_stats binding
                    self.player_stats = self.state.player_stats
                    try:
                        self.player.bind_stats(self.player_stats)
                    except Exception:
                        self.player.bound_stats = self.player_stats
            except Exception:
                # si no existe player_state, seguimos con el state original
                pass

            # Pasar referencia del mapa al game_manager si tiene el método
            try:
                if hasattr(self.game_manager, "set_game_map"):
                    self.game_manager.set_game_map(self.game_map)
            except Exception:
                pass

            # Conectar systems
            self.set_game_systems(self.game_manager, self.job_manager)

            print(f"🎮 SISTEMAS DE JUEGO INICIALIZADOS (jobs en job_manager: {len(self.job_manager.all_jobs())})")
        except Exception as e:
            print(f"Error inicializando sistemas de juego: {e}")

    def set_game_systems(self, game_manager, job_manager):
        """Conecta los sistemas de juego con la vista."""
        self.game_manager = game_manager
        self.job_manager = job_manager
        self.score_system = getattr(game_manager, 'score_system', None)
        if game_manager:
            try:
                # Pasar referencia del player manager para callbacks (ej: show_job_offer)
                game_manager.player_manager = self.player
            except Exception:
                pass

        # Cargar trabajos iniciales desde el estado (si se quiere usar la cola local)
        self._load_initial_jobs()

    def _load_initial_jobs(self):
        """Carga los trabajos iniciales desde self.state si vienen (esto sólo alimenta la cola local de notificaciones)."""
        if isinstance(self.state, dict):
            orders = self.state.get("orders", [])
        else:
            # si self.state es PlayerState, intentar leer jobs_data
            orders = getattr(self.state, "jobs_data", [])

        # Hacemos una copia para la cola de notificaciones local (no duplicar jobs del job_manager)
        self.incoming_raw_jobs = list(orders or [])
        self.rejected_raw_jobs = []
        self.accepted_job_ids = set()

        # Si job_manager ya tiene trabajos, sincronizamos accepted ids
        if self.job_manager:
            try:
                for job in self.job_manager.all_jobs():
                    if getattr(job, "accepted", False):
                        self.accepted_job_ids.add(job.id)
            except Exception:
                pass

        # Filtrar trabajos ya aceptados
        self.incoming_raw_jobs = [r for r in self.incoming_raw_jobs if self._raw_job_id(r) not in self.accepted_job_ids]
        print(f"[JOBS] Cargados {len(self.incoming_raw_jobs)} trabajos pendientes (cola local)")

    def _raw_job_id(self, raw: dict) -> str:
        return raw.get("id") or raw.get("job_id") or raw.get("req") or str(raw)

    # ------------------ Notificaciones / Jobs ------------------
    def _maybe_start_notification(self):
        if self.job_notification_active:
            return
        if self.next_spawn_timer > 0.0:
            return

        # refrescar incoming desde state si corresponde
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
        msg = f"📦 NUEVO PEDIDO\nID:{jid} Pago:${payout} Peso:{weight}kg\n(A) Aceptar (R) Rechazar"
        self.show_notification(msg)
        print(f"[NOTIF] Nuevo trabajo {jid}")

    def show_notification(self, message: str):
        self.active_notification = message
        self.notification_timer = self.NOTIFICATION_DURATION
        print(f"[NOTIFICATION] {message}")

    def _accept_notification(self):
        """
        Acepta la notificación actual.
        - Delegamos preferentemente a GameManager._accept_job si está disponible
          (gestiona inventario y flags visuales).
        """
        if not self.job_notification_data:
            return

        raw = self.job_notification_data
        try:
            jid = str(raw.get("id") or "")
        except Exception:
            jid = ""

        # Opción preferida: GameManager._accept_job (usa player_state.inventory internamente)
        if self.game_manager and hasattr(self.game_manager, "_accept_job"):
            try:
                # Si el job aún no existe en job_manager del game_manager, añadirlo desde raw
                if not self.job_manager.get_job(jid):
                    self.job_manager.add_job_from_raw(raw)
                ok = self.game_manager._accept_job(jid)
                if ok:
                    self.accepted_job_ids.add(jid)
                    self.show_notification(f"✅ Pedido {jid} aceptado")
                else:
                    self.show_notification("❌ No se pudo aceptar el pedido (capacidad/expirado/otro)")
            except Exception as e:
                print(f"[ACCEPT_NOTIF] Error delegando a GameManager._accept_job: {e}")
                self.show_notification("❌ Error aceptando pedido (ver consola)")
            finally:
                self.job_notification_active = False
                self.job_notification_data = None
                self.next_spawn_timer = self.NEXT_SPAWN_AFTER_ACCEPT
            return

        # Fallback (sin GameManager): intentar con job_manager local + inventory en self.state
        try:
            if not self.job_manager:
                self.show_notification("❌ Error interno: job_manager no inicializado")
                self.job_notification_active = False
                self.job_notification_data = None
                return

            job = self.job_manager.add_job_from_raw(raw)
            if not job:
                self.show_notification("❌ No se pudo crear el pedido")
                self.job_notification_active = False
                self.job_notification_data = None
                return

            jid = job.id

            accepted = self.job_manager.accept_job(jid)
            if not accepted:
                self.show_notification("❌ El job no pudo ser aceptado (server / estado)")
                self.job_notification_active = False
                self.job_notification_data = None
                return

            # Añadir al inventario (si la vista tiene acceso a inventory)
            inventory = self.state.get("inventory") if isinstance(self.state, dict) else getattr(self.state, "inventory", None)
            added = False
            try:
                if inventory and hasattr(inventory, "add"):
                    added = inventory.add(self.job_manager.get_job(jid))
            except Exception as e:
                print(f"[ACCEPT_NOTIF] Error añadiendo al inventario fallback: {e}")
                added = False

            if not added:
                try:
                    self.job_manager.mark_rejected(jid)
                except Exception:
                    pass
                self.show_notification("❌ No hay capacidad en el inventario, pedido rechazado")
            else:
                # marcar visibilidad del pickup para que se dibuje
                try:
                    job.visible_pickup = True
                    job.picked_up = False
                    job.dropoff_visible = False
                except Exception:
                    pass
                self.accepted_job_ids.add(jid)
                self.show_notification(f"✅ Pedido {jid} aceptado (fallback)")
        except Exception as e:
            print(f"[ACCEPT_NOTIF] Error aceptando notificación (fallback): {e}")
            self.show_notification("❌ Error al aceptar pedido (ver consola)")
        finally:
            self.job_notification_active = False
            self.job_notification_data = None
            self.next_spawn_timer = self.NEXT_SPAWN_AFTER_ACCEPT

    def _reject_notification(self):
        if self.job_notification_data:
            jid = self._raw_job_id(self.job_notification_data)
            self.rejected_raw_jobs.append(self.job_notification_data)
            print(f"[REJECT] Trabajo {jid} rechazado")
        self.job_notification_active = False
        self.job_notification_data = None
        self.show_notification("❌ Pedido rechazado")

    # ------------------ Draw helpers (jobs markers, notification panel) ------------------
    def _draw_job_markers(self):
        if not self.job_manager:
            return
        try:
            for job in self.job_manager.all_jobs():
                # Dibujar pickup si aceptado y no recogido
                if getattr(job, "accepted", False) and not getattr(job, "picked_up", False):
                    # pickup puede venir en job.pickup o en job.raw['pickup']
                    px_c, py_c = None, None
                    try:
                        px_c, py_c = tuple(job.pickup)
                    except Exception:
                        try:
                            raw = getattr(job, "raw", {}) or {}
                            px_c, py_c = tuple(raw.get("pickup", (None, None)))
                        except Exception:
                            px_c, py_c = None, None

                    if px_c is not None and py_c is not None:
                        px, py = self._cell_to_pixel(int(px_c), int(py_c))
                        # marcador de pickup: círculo dorado
                        arcade.draw_circle_filled(px, py, TILE_SIZE * 0.4, arcade.color.GOLD)
                        arcade.draw_circle_outline(px, py, TILE_SIZE * 0.4, arcade.color.BLACK, 2)
                        # mostrar el id real del pedido
                        job_label = getattr(job, "id", None) or (getattr(job, "raw", {}) or {}).get("id", "PICKUP")
                        Text(f"{job_label}", px - 18, py + 15, arcade.color.BLACK, 8).draw()

                # Dibujar dropoff si recogido pero no entregado
                if getattr(job, "picked_up", False) and not getattr(job, "completed", False):
                    dx_c, dy_c = None, None
                    try:
                        dx_c, dy_c = tuple(job.dropoff)
                    except Exception:
                        try:
                            raw = getattr(job, "raw", {}) or {}
                            dx_c, dy_c = tuple(raw.get("dropoff", (None, None)))
                        except Exception:
                            dx_c, dy_c = None, None

                    if dx_c is not None and dy_c is not None:
                        dx, dy = self._cell_to_pixel(int(dx_c), int(dy_c))
                        # usar helper centrado para evitar dependencias en draw_rectangle_filled
                        self._draw_centered_rect_filled(dx, dy, TILE_SIZE * 0.6, TILE_SIZE * 0.6, arcade.color.RED)
                        self._draw_centered_rect_outline(dx, dy, TILE_SIZE * 0.6, TILE_SIZE * 0.6, arcade.color.BLACK, 2)
                        drop_label = getattr(job, "id", None) or (getattr(job, "raw", {}) or {}).get("id", "DROPOFF")
                        Text(f"{drop_label}", dx - 25, dy + 15, arcade.color.WHITE, 8).draw()
        except Exception as e:
            print(f"[ERROR] Dibujando marcadores: {e}")

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

        self._draw_rect_lrbt_filled(left, right, bottom, top, arcade.color.DARK_BLUE)
        self._draw_rect_lrbt_outline(left, right, bottom, top, arcade.color.GOLD, 3)

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

    # ------------------ ARCADE callbacks ------------------
    def on_show(self) -> None:
        arcade.set_background_color(arcade.color.DARK_SLATE_GRAY)

    def on_draw(self) -> None:
        # Limpio y pinto todo
        self.clear()
        self.game_map.draw_debug(tile_size=TILE_SIZE, draw_grid_lines=True)

        # Markers y jugador
        self._draw_job_markers()
        self.player.draw()

        # Panel lateral y HUD
        self._draw_panel()
        self._draw_time_panel()

        # Weather renderer overlay
        try:
            self.weather_renderer.draw()
        except Exception:
            pass

        # Notificación
        self._draw_job_notification()

    def _draw_panel(self):
        # Panel lateral (fondo)
        self._draw_rect_lrbt_filled(MAP_WIDTH, SCREEN_WIDTH, 0, SCREEN_HEIGHT, arcade.color.DARK_SLATE_BLUE)
        self._draw_rect_lrbt_outline(MAP_WIDTH, SCREEN_WIDTH, 0, SCREEN_HEIGHT, arcade.color.BLUE, 2)

        # Títulos y stats
        self.panel_title.draw()

        money = getattr(self.state, "money", 0) if not isinstance(self.state, dict) else self.state.get("money", 0)
        reputation = getattr(self.player_stats, "reputation", 70)
        goal = (getattr(self.state, "map_data", {}) or {}).get("goal", 3000) if not isinstance(self.state, dict) else (self.state.get("map_data", {}) or {}).get("goal", 3000)

        self.stats_text.text = f"Dinero: ${money:.0f}\nMeta: ${goal}\nReputación: {reputation}/100"
        self.stats_text.draw()

        # Weather text
        ws = None
        if isinstance(self.state, dict):
            ws = self.state.get("weather_state", {})
        else:
            ws = getattr(self.state, "weather_state", {}) or getattr(self.state, "weather_system", {}).get_state() if hasattr(self.state, "weather_system") else {}
        cond = ws.get("condition", "?") if isinstance(ws, dict) else "?"
        intensity = ws.get("intensity", "?") if isinstance(ws, dict) else "?"
        multiplier = ws.get("multiplier", 1.0) if isinstance(ws, dict) else 1.0
        self.weather_text.text = f"Clima: {cond}\nIntensidad: {intensity}\nVelocidad: {multiplier:.0%}"
        self.weather_text.draw()

        # Inventory
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
                for job in inventory_items:
                    job_id = getattr(job, "id", job.get("id") if isinstance(job, dict) else str(job))
                    items.append(f"- {job_id}")
            except Exception:
                items = ["- Error cargando"]
            inventory_info = f"Peso: {weight}/{max_weight}kg\n" + "\n".join(items[:4])
        else:
            inventory_info = "Peso: 0/10kg\n- Vacío"
        self.inventory_text.text = inventory_info
        self.inventory_text.draw()

        # Jobs list
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
                    if getattr(job, "picked_up", False):
                        job_text += " → 🎯"
                    else:
                        job_text += f" (${payout})"
                    jobs_info.append(job_text)
                if not jobs_info:
                    jobs_info = ["- No hay pedidos activos"]
                    available = []
                    try:
                        available = self.job_manager.get_available_jobs(self.game_manager.get_game_time())
                    except Exception:
                        pass
                    if available:
                        jobs_info.append(f"- {len(available)} disponibles")
                self.jobs_text.text = "\n".join(jobs_info)
            except Exception as e:
                self.jobs_text.text = f"- Error: {str(e)[:30]}..."
        else:
            self.jobs_text.text = "- Sistemas cargando..."
        self.jobs_text.draw()

        # Cronómetro (panel)
        if self.game_manager and hasattr(self.game_manager, 'get_time_remaining'):
            time_remaining = self.game_manager.get_time_remaining()
            minutes = int(time_remaining // 60)
            seconds = int(time_remaining % 60)
            self.timer_text.text = f"⏰ {minutes:02d}:{seconds:02d}"
            if time_remaining < 300:
                self.timer_text.color = arcade.color.RED
            elif time_remaining < 600:
                self.timer_text.color = arcade.color.ORANGE
            else:
                self.timer_text.color = arcade.color.GREEN
        else:
            self.timer_text.text = "⏰ 15:00"
        self.timer_text.draw()

        # Score stats
        self.score_title.draw()
        if self.score_system:
            try:
                stats = self.score_system.get_current_stats()
                time_remaining = stats.get('time_remaining', 0)
                minutes = int(time_remaining // 60)
                seconds = int(time_remaining % 60)
                self.score_text.text = (
                    f"Entregas: {stats['deliveries_completed']}\n"
                    f"A tiempo: {stats['on_time_deliveries']}\n"
                    f"Dinero: ${stats['total_money']:.0f}\n"
                    f"Tiempo: {minutes:02d}:{seconds:02d}"
                )
            except Exception as e:
                self.score_text.text = f"Error: {e}"
        else:
            self.score_text.text = "Cargando..."
        self.score_text.draw()

        # Notification
        if self.active_notification and self.notification_timer > 0:
            self.notification_text.text = self.active_notification
            self.notification_text.draw()

        # Stamina bar
        stamina_val = getattr(self.player_stats, "stamina", 100.0)
        bar_w, bar_h = 200, 20
        left = MAP_WIDTH + 50
        bottom = 30
        right = left + bar_w
        top = bottom + bar_h

        self._draw_rect_lrbt_filled(left, right, bottom, top, arcade.color.DARK_SLATE_GRAY)
        pct = max(0.0, min(1.0, stamina_val / 100.0))
        if pct > 0.0:
            fill_right = left + (bar_w * pct)
            color = arcade.color.GREEN if pct > 0.3 else arcade.color.ORANGE if pct > 0.1 else arcade.color.RED
            self._draw_rect_lrbt_filled(left, fill_right, bottom, top, color)
        self._draw_rect_lrbt_outline(left, right, bottom, top, arcade.color.BLACK, 2)
        # Centrar texto dentro de la barra
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
        self._draw_rect_lrbt_filled(panel_x, panel_x + panel_width, panel_y - panel_height, panel_y, arcade.color.DARK_SLATE_GRAY)
        self._draw_rect_lrbt_outline(panel_x, panel_x + panel_width, panel_y - panel_height, panel_y, arcade.color.BLUE, 2)
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
            time_color = arcade.color.GREEN
            if time_remaining < 300:
                time_color = arcade.color.RED
            elif time_remaining < 600:
                time_color = arcade.color.ORANGE
            Text(f"Restante: {rem_minutes:02d}:{rem_seconds:02d}", panel_x + 15, panel_y - 85, time_color, 11, bold=True).draw()
        except Exception:
            pass

    def on_update(self, dt: float) -> None:
        # Actualizar game manager (que internamente chequea nuevas ofertas)
        if self.game_manager:
            try:
                self.game_manager.update(dt)
            except Exception as e:
                print(f"Error en game_manager.update: {e}")

        # Gestion notificaciones de jobs (cola local)
        if self.job_notification_active:
            self.job_notification_timer -= dt
            if self.job_notification_timer <= 0:
                self._reject_notification()

        if self.next_spawn_timer > 0.0:
            self.next_spawn_timer -= dt

        if not self.job_notification_active:
            self._maybe_start_notification()

        # Temporal general
        if self.active_notification and self.notification_timer > 0:
            self.notification_timer -= dt
            if self.notification_timer <= 0:
                self.active_notification = None

        # Movimiento del jugador
        input_active = (time.time() - self._last_input_time) < self.INPUT_ACTIVE_WINDOW
        inventory = self.state.get("inventory", None) if isinstance(self.state, dict) else getattr(self.state, "inventory", None)
        was_moving = bool(self.player.moving)

        # Actualizar jugador -> pasar player_stats, weather_system y inventory
        try:
            self.player.update(dt, player_stats=self.player_stats, weather_system=self.weather_markov, inventory=inventory)
        except Exception:
            try:
                self.player.update(dt)
            except Exception:
                pass

        # Si acabó de llegar a una casilla: intentar pickup/deliver y notificar
        if was_moving and not self.player.moving:
            # intento de pickup exacto (GameManager)
            try:
                if self.game_manager and hasattr(self.game_manager, 'try_pickup_at'):
                    picked = self.game_manager.try_pickup_at(self.player.cell_x, self.player.cell_y)
                    if picked:
                        self.show_notification("¡Paquete recogido! Ve al punto de entrega.")
            except Exception as e:
                print(f"Error pickup: {e}")

            # intento de pickup nearby (si el pickup está en una casilla adyacente)
            try:
                if self._pickup_nearby():
                    self.show_notification("¡Paquete recogido! Ve al punto de entrega.")
            except Exception as e:
                print(f"Error pickup (nearby): {e}")

            # intento de entrega
            try:
                if self.game_manager and hasattr(self.game_manager, 'try_deliver_at'):
                    result = self.game_manager.try_deliver_at(self.player.cell_x, self.player.cell_y)
                    if result:
                        self.show_notification(f"¡Pedido {result['job_id']} entregado!\n+${result['pay']:.0f}")
            except Exception as e:
                print(f"Error deliver: {e}")

        # Actualizar player_stats: pasar is_moving + input_active
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

        # Actualizar clima Markov + renderer
        try:
            self.weather_markov.update(dt)
            self.weather_markov.apply_to_game_state(self.state)
            ws = self.state.get("weather_state", {}) if isinstance(self.state, dict) else getattr(self.state, "weather_state", {})
            self.weather_renderer.update(dt, ws)
        except Exception as e:
            print(f"Error actualizando clima: {e}")

    # ------------------ Input ------------------
    def on_key_press(self, key: int, modifiers: int) -> None:
        # registrar input
        self._last_input_time = time.time()

        # Tecla P: intentar recoger paquete cercano/manual
        if key == arcade.key.P:
            try:
                picked = False
                # Primero intentar con GameManager exacto (si está en la misma celda)
                if self.game_manager and hasattr(self.game_manager, 'try_pickup_at'):
                    picked = self.game_manager.try_pickup_at(self.player.cell_x, self.player.cell_y)
                # Si no recogió por exact match, intentar nearby (adyacente)
                if not picked:
                    if self._pickup_nearby():
                        picked = True
                if picked:
                    self.show_notification("¡Paquete recogido! Ve al punto de entrega.")
                else:
                    self.show_notification("No hay paquete para recoger aquí o adyacente.")
            except Exception as e:
                print(f"[INPUT] Error recogiendo paquete (P): {e}")
            return

        # A/R para notificaciones y ofertas
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

        # Apply facing (sprite orientation)
        self._apply_facing()

        # If game manager intercepts movement, use it
        if self.game_manager and hasattr(self.game_manager, 'handle_Player_movement'):
            try:
                # game_manager may save state and then call player_manager.move_by
                self.game_manager.handle_player_movement(dx, dy)
                return
            except Exception:
                pass

        moved = self.player.move_by(dx, dy, self.game_map)
        if not moved:
            # If can't move due to stamina exhausted or collision
            if self.player.bound_stats and hasattr(self.player.bound_stats, "can_move") and not self.player.bound_stats.can_move():
                self.show_notification("[INFO] No puedes moverte: resistencia agotada.")
            else:
                self.show_notification("Movimiento bloqueado")

    def on_key_release(self, key: int, modifiers: int):
        # manejar ofertas (A/R en release)
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
        """Ajusta la rotación del sprite (simple, sin flip)"""
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

        if self.facing == "up":
            spr.angle = 0
        elif self.facing == "right":
            spr.angle = 90
        elif self.facing == "down":
            spr.angle = 180
        elif self.facing == "left":
            spr.angle = -90

    # ------------------ Pickup nearby logic (vista) ------------------
    def _pickup_nearby(self) -> bool:
        """
        Recoge cualquier pedido aceptado y no recogido cuya posición de pickup
        esté en la misma casilla del jugador o en una adyacente (Manhattan <= 1).
        Retorna True si se recogió al menos uno.
        """
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

                # obtener coords de pickup robustamente
                try:
                    jpx, jpy = tuple(job.pickup)
                except Exception:
                    raw = getattr(job, "raw", {}) or {}
                    pickup_raw = raw.get("pickup", None)
                    if pickup_raw:
                        try:
                            jpx, jpy = tuple(pickup_raw)
                        except Exception:
                            continue
                    else:
                        continue

                # comparar distancia Manhattan
                if abs(int(jpx) - px) + abs(int(jpy) - py) <= 1:
                    # marcar como recogido
                    job.picked_up = True
                    job.dropoff_visible = True
                    picked_any = True
                    print(f"[GAME_WINDOW] Paquete {job.id} recogido (nearby) en {px},{py} (pickup en {jpx},{jpy})")

            return picked_any
        except Exception as e:
            print(f"[GAME_WINDOW] Error en _pickup_nearby: {e}")
            return False

    # ------------------ API for game manager ---------------
    def show_job_offer(self, job_data, on_accept, on_reject):
        """Método llamado por GameManager para mostrar oferta (callbacks)."""
        try:
            job_id = job_data.get("id", "Unknown")
            payout = job_data.get("payout", 0)
            weight = job_data.get("weight", 0)
            message = f"📦 NUEVO PEDIDO\n{job_id}\nPago: ${payout}\nPeso: {weight}kg\n(A) Aceptar  (R) Rechazar"
            self.show_notification(message)

            # Guardar callbacks para aceptar/rechazar desde UI
            self._pending_offer = (on_accept, on_reject)
            self._offer_job_id = job_id
        except Exception as e:
            print(f"Error mostrando oferta: {e}")
            self._pending_offer = None
