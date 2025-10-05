# game_window.py - INTERFAZ COMPLETA CON SISTEMA DE PEDIDOS (CORREGIDO)
import time
import arcade
from arcade import View, Text
from run_api.api_client import ApiClient
from .map_manager import GameMap, FLIP_Y
from game.player_manager import Player
from game.player_stats import PlayerStats
from game.weather_markov import WeatherMarkov
from graphics.weather_renderer import WeatherRenderer
from typing import List

# Importaciones para sistemas de juego
from game.game_manager import GameManager
from game.jobs_manager import JobManager

# Configuración
SCREEN_WIDTH = 1150
SCREEN_HEIGHT = 800
MAP_WIDTH = 730
PANEL_WIDTH = 300
TILE_SIZE = 24


# Helper functions
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

        # Sistemas de juego
        self.game_manager = None
        self.job_manager = None
        self.score_system = None

        # Inicializar player_stats
        if isinstance(self.state, dict):
            if "player_stats" not in self.state or self.state.get("player_stats") is None:
                self.state["player_stats"] = PlayerStats()
            self.player_stats = self.state["player_stats"]
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

        # Bind stats
        try:
            self.player.bind_stats(self.player_stats)
        except Exception:
            self.player.bound_stats = self.player_stats

        # Ajustar escala del sprite
        try:
            tex = getattr(self.player, "texture", None)
            spr = getattr(self.player, "sprite", None)
            if tex is not None and spr is not None:
                max_dim = max(tex.width or 1, tex.height or 1)
                scale = (TILE_SIZE * 0.9) / max_dim
                spr.scale = scale
                self.player._sprite_base_scale = scale
        except Exception:
            pass

        self.base_scale = getattr(self.player, "_sprite_base_scale", 1.0)
        self.facing = "up"

        # Sistema de trabajos (MEJORADO)
        self.incoming_raw_jobs: List[dict] = []
        self.rejected_raw_jobs: List[dict] = []
        self.accepted_job_ids = set()
        self.notification_active = False
        self.notification_job_raw = None
        self.notification_timer = 0.0
        self.next_spawn_timer = 0.0
        self.NOTIF_ACCEPT_SECONDS = 10.0  # Aumentado a 10 segundos
        self.NEXT_SPAWN_AFTER_ACCEPT = 10.0  # 10 segundos entre pedidos

        # Elementos de UI (MEJORADOS - usando Text objects)
        self.panel_title = Text("COURIER QUEST", MAP_WIDTH + 10, SCREEN_HEIGHT - 30, arcade.color.GOLD, 16, bold=True)
        self.stats_text = Text("", MAP_WIDTH + 10, SCREEN_HEIGHT - 60, arcade.color.WHITE, 12)
        self.weather_text = Text("", MAP_WIDTH + 10, SCREEN_HEIGHT - 85, arcade.color.LIGHT_BLUE, 12)
        self.inventory_title = Text("INVENTARIO /n", MAP_WIDTH + 10, SCREEN_HEIGHT - 120, arcade.color.CYAN, 14, bold=True)
        self.inventory_text = Text("", MAP_WIDTH + 10, SCREEN_HEIGHT - 140, arcade.color.WHITE, 11)
        self.jobs_title = Text("PEDIDOS ACTIVOS /n", MAP_WIDTH + 10, SCREEN_HEIGHT - 200, arcade.color.ORANGE, 14,
                               bold=True)
        self.jobs_text = Text("", MAP_WIDTH + 10, SCREEN_HEIGHT - 220, arcade.color.WHITE, 11)
        self.score_title = Text("ESTADÍSTICAS /n", MAP_WIDTH + 10, SCREEN_HEIGHT - 280, arcade.color.GREEN, 14, bold=True)
        self.score_text = Text("", MAP_WIDTH + 10, SCREEN_HEIGHT - 300, arcade.color.WHITE, 11)
        self.timer_text = Text("", MAP_WIDTH + 10, SCREEN_HEIGHT - 340, arcade.color.RED, 14,
                               bold=True)  # NUEVO: Cronómetro
        self.notification_text = Text("", SCREEN_WIDTH - 350, 200, arcade.color.YELLOW,
                                      12)  # MOVIDO: Esquina inferior derecha
        self.stamina_text = Text("", MAP_WIDTH + 150, 50, arcade.color.WHITE, 12)

        # Notificación de trabajo (NUEVO - diseño mejorado)
        self.job_notification_active = False
        self.job_notification_data = None
        self.job_notification_timer = 0.0

        # Clima
        self.weather_markov = WeatherMarkov(api=ApiClient())
        self.weather_renderer = WeatherRenderer(self)

        self._last_input_time = 0.0
        self.INPUT_ACTIVE_WINDOW = 0.25

        # Sistema de notificaciones
        self.active_notification = None
        self.NOTIFICATION_DURATION = 5.0
        self._pending_offer = None
        self._offer_job_id = None

        # Inicializar sistemas de juego
        self._initialize_game_systems()

    # ========== MÉTODOS FALTANTES AÑADIDOS ==========

    def _initialize_game_systems(self):
        """Inicializa GameManager y JobManager con los datos del estado"""
        try:
            # Crear instancias de los managers
            self.game_manager = GameManager()
            self.job_manager = JobManager()

            # Obtener datos del estado
            if isinstance(self.state, dict):
                map_data = self.state.get("map_data", {})
                jobs_data = self.state.get("orders", [])
                weather_data = self.state.get("weather_data", {})
            else:
                map_data = getattr(self.state, "map_data", {})
                jobs_data = getattr(self.state, "orders", [])
                weather_data = getattr(self.state, "weather_data", {})

            # Inicializar el juego
            self.game_manager.initialize_game(map_data, jobs_data, weather_data)
            self.game_manager.set_game_map(self.game_map)  # NUEVO: Pasar referencia al mapa

            # Conectar sistemas con la vista
            self.set_game_systems(self.game_manager, self.job_manager)

            print(f"🎮 SISTEMAS DE JUEGO INICIALIZADOS: {len(jobs_data)} pedidos cargados")

        except Exception as e:
            print(f"❌ Error inicializando sistemas de juego: {e}")

    def set_game_systems(self, game_manager, job_manager):
        """Conecta los sistemas de juego"""
        self.game_manager = game_manager
        self.job_manager = job_manager
        self.score_system = getattr(game_manager, 'score_system', None)
        if game_manager:
            game_manager.player_manager = self.player

        # INICIALIZAR SISTEMA DE TRABAJOS
        self._load_initial_jobs()

        print(f"[GAME_WINDOW] ✅ Sistemas conectados - {len(self.incoming_raw_jobs)} trabajos pendientes")

    def _load_initial_jobs(self):
        """Carga los trabajos iniciales del estado"""
        # Cargar trabajos desde el estado
        if isinstance(self.state, dict):
            orders = self.state.get("orders", [])
        else:
            orders = getattr(self.state, "orders", [])

        self.incoming_raw_jobs = list(orders or [])
        self.rejected_raw_jobs = []
        self.accepted_job_ids = set()

        # Si hay trabajos en el job_manager, marcarlos como aceptados
        if self.job_manager:
            for job in self.job_manager.all_jobs():
                self.accepted_job_ids.add(job.id)

        # Filtrar trabajos ya aceptados
        self.incoming_raw_jobs = [r for r in self.incoming_raw_jobs if self._raw_job_id(r) not in self.accepted_job_ids]

        print(f"[JOBS] Cargados {len(self.incoming_raw_jobs)} trabajos pendientes")


    def _raw_job_id(self, raw: dict) -> str:
        """Obtiene el ID de un trabajo de forma robusta"""
        return raw.get("id") or raw.get("job_id") or raw.get("req") or str(raw)

    def _maybe_start_notification(self):
        """Intenta iniciar una nueva notificación"""
        if self.job_notification_active:
            return

        # Si hay un timer de spawn activo, esperar
        if self.next_spawn_timer > 0.0:
            return

        # Limpiar trabajos ya aceptados
        self.incoming_raw_jobs = [r for r in self.incoming_raw_jobs if self._raw_job_id(r) not in self.accepted_job_ids]

        if self.incoming_raw_jobs:
            self._spawn_next_notification_immediate()

    def _spawn_next_notification_immediate(self):
        """Muestra la siguiente notificación inmediatamente con diseño mejorado"""
        if self.incoming_raw_jobs:
            raw = self.incoming_raw_jobs.pop(0)
            self.job_notification_active = True  # Usar el nuevo sistema de notificaciones
            self.job_notification_data = raw
            self.job_notification_timer = self.NOTIF_ACCEPT_SECONDS

            # Usar el sistema mejorado de notificaciones
            job_id = self._raw_job_id(raw)
            payout = raw.get("payout", 0)
            weight = raw.get("weight", 0)
            priority = raw.get("priority", 1)
            description = raw.get("description", "Sin descripción")

            message = f"📦 NUEVO PEDIDO DISPONIBLE\n\nID: {job_id}\nPago: ${payout}\nPeso: {weight}kg\nPrioridad: {priority}\nDescripción: {description}\n\n(A) Aceptar  (R) Rechazar\nTiempo: {int(self.NOTIF_ACCEPT_SECONDS)}s"
            self.show_notification(message)

            print(f"[NOTIF] Nuevo trabajo {job_id} - {self.NOTIF_ACCEPT_SECONDS}s para aceptar")

    def show_notification(self, message: str):
        """Muestra una notificación temporal"""
        self.active_notification = message
        self.notification_timer = self.NOTIFICATION_DURATION
        print(f"[NOTIFICATION] {message}")

    def _accept_notification(self):
        """Acepta el trabajo de la notificación activa (MEJORADO)"""
        if not self.job_notification_data:
            return

        raw = self.job_notification_data
        jid = self._raw_job_id(raw)

        # Verificar capacidad
        new_weight = float(raw.get("weight", 1.0))
        inventory = self.state.get("inventory") if isinstance(self.state, dict) else getattr(self.state, "inventory",
                                                                                             None)

        if inventory and (inventory.current_weight + new_weight > inventory.max_weight):
            self.show_notification("❌ Capacidad insuficiente")
            self.rejected_raw_jobs.append(raw)
            self.job_notification_active = False
            self.job_notification_data = None
            return

        # Añadir al job_manager
        if self.job_manager:
            try:
                self.job_manager.add_job_from_raw(raw, (self.player.cell_x, self.player.cell_y))
                job = self.job_manager.get_job(jid)
                if job:
                    job.accepted = True
                    job.picked_up = False
                    job.visible_pickup = True
                    job.dropoff_visible = False
                    job.completed = False
                    print(f"[ACCEPT] Trabajo {jid} añadido al manager")
            except Exception as e:
                print(f"[ERROR] No se pudo añadir trabajo al manager: {e}")

        self.accepted_job_ids.add(jid)
        self.job_notification_active = False
        self.job_notification_data = None
        self.next_spawn_timer = self.NEXT_SPAWN_AFTER_ACCEPT
        self.show_notification(f"✅ Pedido {jid} aceptado")

    def _reject_notification(self):
        """Rechaza el trabajo de la notificación activa (MEJORADO)"""
        if self.job_notification_data:
            jid = self._raw_job_id(self.job_notification_data)
            self.rejected_raw_jobs.append(self.job_notification_data)
            print(f"[REJECT] Trabajo {jid} rechazado")

        self.job_notification_active = False
        self.job_notification_data = None
        self.show_notification("❌ Pedido rechazado")

    def _draw_job_markers(self):
        """Dibuja los marcadores de pickup y dropoff en el mapa"""
        if not self.job_manager:
            return

        try:
            for job in self.job_manager.all_jobs():
                # Solo mostrar pickup si el trabajo está aceptado pero no recogido
                if getattr(job, "accepted", False) and not getattr(job, "picked_up", False):
                    # Usar las coordenadas del JSON, no la posición del jugador
                    pickup_x, pickup_y = job.pickup
                    px, py = self._cell_to_pixel(pickup_x, pickup_y)

                    # Marcador de pickup (círculo dorado)
                    arcade.draw_circle_filled(px, py, TILE_SIZE * 0.4, arcade.color.GOLD)
                    arcade.draw_circle_outline(px, py, TILE_SIZE * 0.4, arcade.color.BLACK, 2)
                    arcade.draw_text("PICKUP", px - 20, py + 15, arcade.color.BLACK, 8)

                # Mostrar dropoff solo si el paquete fue recogido pero no entregado
                if getattr(job, "picked_up", False) and not getattr(job, "completed", False):
                    # Usar las coordenadas del JSON para dropoff
                    dropoff_x, dropoff_y = job.dropoff
                    dx, dy = self._cell_to_pixel(dropoff_x, dropoff_y)

                    # Marcador de dropoff (rectángulo rojo)
                    left = dx - TILE_SIZE * 0.3
                    right = dx + TILE_SIZE * 0.3
                    top = dy + TILE_SIZE * 0.3
                    bottom = dy - TILE_SIZE * 0.3
                    arcade.draw_rectangle_filled(dx, dy, TILE_SIZE * 0.6, TILE_SIZE * 0.6, arcade.color.RED)
                    arcade.draw_rectangle_outline(dx, dy, TILE_SIZE * 0.6, TILE_SIZE * 0.6, arcade.color.BLACK, 2)
                    arcade.draw_text("DROPOFF", dx - 25, dy + 15, arcade.color.WHITE, 8)
        except Exception as e:
            print(f"[ERROR] Dibujando marcadores: {e}")

    def _cell_to_pixel(self, cx, cy):
        """Convierte coordenadas de celda a píxeles"""
        x = cx * TILE_SIZE + TILE_SIZE // 2
        y = (len(self.game_map.grid) - 1 - cy) * TILE_SIZE + TILE_SIZE // 2
        return x, y

    def _draw_job_notification(self):
        """Dibuja la notificación de trabajo en la esquina inferior derecha"""
        if not self.job_notification_active or not self.job_notification_data:
            return

        raw = self.job_notification_data
        job_id = self._raw_job_id(raw)
        payout = raw.get("payout", 0)
        weight = raw.get("weight", 0)
        priority = raw.get("priority", 1)
        description = raw.get("description", "Sin descripción")

        # Panel de notificación
        panel_width = 400
        panel_height = 230
        left = SCREEN_WIDTH - panel_width - 20
        bottom = 100
        right = left + panel_width
        top = bottom + panel_height

        # Fondo del panel
        _draw_rect_lrbt_filled(left, right, bottom, top, arcade.color.DARK_BLUE)
        _draw_rect_lrbt_outline(left, right, bottom, top, arcade.color.GOLD, 3)

        # Título
        title_text = Text("📦 NUEVO PEDIDO", left + 10, top - 25, arcade.color.GOLD, 16, bold=True)
        title_text.draw()

        # Información del trabajo
        info_y = top - 50
        Text(f"ID: {job_id}", left + 15, info_y, arcade.color.WHITE, 12).draw()
        Text(f"Pago: ${payout}", left + 15, info_y - 20, arcade.color.GREEN, 12).draw()
        Text(f"Peso: {weight}kg", left + 15, info_y - 40, arcade.color.CYAN, 12).draw()
        Text(f"Prioridad: {priority}", left + 15, info_y - 60, arcade.color.ORANGE, 12).draw()

        # Descripción (truncada si es muy larga)
        desc = description[:50] + "..." if len(description) > 50 else description
        Text(f"Desc: {desc}", left + 15, info_y - 80, arcade.color.LIGHT_GRAY, 10).draw()

        # Controles y temporizador
        controls_y = bottom + 30
        Text("(A) Aceptar  (R) Rechazar", left + 15, controls_y, arcade.color.YELLOW, 12).draw()

        time_left = int(self.job_notification_timer)
        Text(f"Tiempo: {time_left}s", left + 15, controls_y - 20, arcade.color.RED, 12).draw()

    def _spawn_debug_notification(self, job):
        """Spawn una notificación de debug para testing"""
        raw_data = {
            "id": getattr(job, "id", "debug_job"),
            "payout": getattr(job, "payout", 100),
            "weight": getattr(job, "weight", 2.0),
            "priority": getattr(job, "priority", 1),
            "description": "Pedido de prueba generado por debug"
        }

        self.job_notification_active = True
        self.job_notification_data = raw_data
        self.job_notification_timer = self.NOTIF_ACCEPT_SECONDS

        job_id = self._raw_job_id(raw_data)
        payout = raw_data.get("payout", 0)
        weight = raw_data.get("weight", 0)

        message = f"🐛 DEBUG PEDIDO\n\nID: {job_id}\nPago: ${payout}\nPeso: {weight}kg\nPrioridad: {raw_data.get('priority', 1)}\nDescripción: {raw_data.get('description', '')}\n\n(A) Aceptar  (R) Rechazar\nTiempo: {int(self.NOTIF_ACCEPT_SECONDS)}s"
        self.show_notification(message)

        print(f"[DEBUG] Notificación forzada: {job_id}")

    # ========== MÉTODOS DE ARCADE ==========

    def on_show(self) -> None:
        arcade.set_background_color(arcade.color.DARK_SLATE_GRAY)

    def on_draw(self) -> None:
        self.clear()
        self.game_map.draw_debug(tile_size=TILE_SIZE, draw_grid_lines=True)

        # DIBUJAR MARCADORES DE TRABAJOS
        self._draw_job_markers()

        self.player.draw()
        self._draw_panel()
        self.weather_renderer.draw()

        # Dibujar notificación de trabajo (si está activa)
        self._draw_job_notification()

    def _draw_panel(self):
        """Dibuja el panel lateral con cronómetro"""
        # Fondo del panel
        _draw_rect_lrbt_filled(MAP_WIDTH, SCREEN_WIDTH, 0, SCREEN_HEIGHT, arcade.color.DARK_SLATE_BLUE)
        _draw_rect_lrbt_outline(MAP_WIDTH, SCREEN_WIDTH, 0, SCREEN_HEIGHT, arcade.color.BLUE, 2)

        # Título
        self.panel_title.draw()

        # Estadísticas
        money = getattr(self.state, "money", 0) if not isinstance(self.state, dict) else self.state.get("money", 0)
        reputation = getattr(self.player_stats, "reputation", 70)
        goal = getattr(self.state, "map_data", {}).get("goal", 3000) if not isinstance(self.state,
                                                                                       dict) else self.state.get(
            "map_data", {}).get("goal", 3000)

        self.stats_text.text = f"Dinero: ${money:.0f}\nMeta: ${goal}\nReputación: {reputation}/100"
        self.stats_text.draw()

        # Clima
        ws = self.state.get("weather_state", {}) if isinstance(self.state, dict) else getattr(self.state,
                                                                                              "weather_state", {})
        cond = ws.get("condition", "?")
        intensity = ws.get("intensity", "?")
        multiplier = ws.get("multiplier", 1.0)
        self.weather_text.text = f"Clima: {cond}\nIntensidad: {intensity}\nVelocidad: {multiplier:.0%}"
        self.weather_text.draw()

        # Inventario - CORREGIDO: usar método público en lugar de protegido
        self.inventory_title.draw()
        inventory = self.state.get("inventory", None) if isinstance(self.state, dict) else getattr(self.state,
                                                                                                   "inventory", None)
        if inventory:
            weight = getattr(inventory, "current_weight", 0)
            max_weight = getattr(inventory, "max_weight", 10)
            items = []
            try:
                # Usar método público para obtener valores del deque
                if hasattr(inventory, 'get_deque_values'):
                    inventory_items = inventory.get_deque_values()
                else:
                    # Fallback: intentar acceder al deque directamente
                    inventory_items = []
                    if hasattr(inventory, 'deque'):
                        for item in inventory.deque:
                            if hasattr(item, 'val'):
                                inventory_items.append(item.val)
                            else:
                                inventory_items.append(item)

                for job in inventory_items:
                    if hasattr(job, 'id'):
                        job_id = getattr(job, "id", "Unknown")
                    elif isinstance(job, dict):
                        job_id = job.get("id", "Unknown")
                    else:
                        job_id = str(job)
                    items.append(f"- {job_id}")
            except Exception as e:
                print(f"Error cargando inventario: {e}")
                items = ["- Error cargando"]

            inventory_info = f"Peso: {weight}/{max_weight}kg\n" + "\n".join(items[:4])
        else:
            inventory_info = "Peso: 0/10kg\n- Vacío"

        self.inventory_text.text = inventory_info
        self.inventory_text.draw()

        # Pedidos activos - CORREGIDO: usar método público
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
                        job_text += f" → 🎯"
                    else:
                        job_text += f" (${payout})"

                    jobs_info.append(job_text)

                if not jobs_info:
                    jobs_info = ["- No hay pedidos activos"]
                    available = self.job_manager.get_available_jobs(self.game_manager.get_game_time())
                    if available:
                        jobs_info.append(f"- {len(available)} disponibles")

                self.jobs_text.text = "\n".join(jobs_info)
            except Exception as e:
                self.jobs_text.text = f"- Error: {str(e)[:30]}..."
        else:
            self.jobs_text.text = "- Sistemas cargando..."
        self.jobs_text.draw()

        # Cronómetro (NUEVO)
        if self.game_manager and hasattr(self.game_manager, 'get_time_remaining'):
            time_remaining = self.game_manager.get_time_remaining()
            minutes = int(time_remaining // 60)
            seconds = int(time_remaining % 60)
            self.timer_text.text = f"⏰ {minutes:02d}:{seconds:02d}"

            # Cambiar color según el tiempo restante
            if time_remaining < 300:  # Menos de 5 minutos
                self.timer_text.color = arcade.color.RED
            elif time_remaining < 600:  # Menos de 10 minutos
                self.timer_text.color = arcade.color.ORANGE
            else:
                self.timer_text.color = arcade.color.GREEN
        else:
            self.timer_text.text = "⏰ 15:00"
        self.timer_text.draw()

        # Estadísticas de puntuación
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

        # Notificación general (activa por show_notification)
        if self.active_notification and self.notification_timer > 0:
            self.notification_text.text = self.active_notification
            self.notification_text.draw()

        # Barra de stamina
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
        self.stamina_text.position = (left + bar_w / 2, bottom + 5)
        self.stamina_text.text = f"RESISTENCIA: {int(stamina_val)}%"
        self.stamina_text.draw()

    def on_update(self, dt: float) -> None:
        # ACTUALIZAR GAME_MANAGER
        if self.game_manager:
            try:
                self.game_manager.update(dt)
            except Exception as e:
                print(f"Error en game_manager.update: {e}")

        # SISTEMA DE NOTIFICACIONES DE TRABAJOS (MEJORADO)
        if self.job_notification_active and self.job_notification_timer > 0:
            self.job_notification_timer -= dt
            if self.job_notification_timer <= 0:
                self._reject_notification()

        if self.next_spawn_timer > 0.0:
            self.next_spawn_timer -= dt

        if not self.job_notification_active:
            self._maybe_start_notification()

        # Temporizador de notificación existente
        if self.active_notification and self.notification_timer > 0:
            self.notification_timer -= dt
            if self.notification_timer <= 0:
                self.active_notification = None

        # Movimiento del jugador
        input_active = (time.time() - self._last_input_time) < self.INPUT_ACTIVE_WINDOW
        inventory = self.state.get("inventory", None) if isinstance(self.state, dict) else getattr(self.state,
                                                                                                   "inventory", None)
        was_moving = bool(self.player.moving)

        try:
            self.player.update(dt, player_state=self.state, game_map=self.game_map)
        except TypeError:
            try:
                self.player.update(dt, player_stats=self.player_stats, weather_system=self.weather_markov,
                                   inventory=inventory)
            except Exception:
                self.player.update(dt)

        # Entregas al completar movimiento
        if was_moving and not self.player.moving:
            if self.game_manager and hasattr(self.game_manager, 'try_deliver_at'):
                try:
                    result = self.game_manager.try_deliver_at(self.player.cell_x, self.player.cell_y)
                    if result:
                        self.show_notification(f"¡Pedido {result['job_id']} entregado!\n+${result['pay']:.0f}")
                except Exception as e:
                    print(f"Error en entrega: {e}")

        # Actualizar stats del jugador
        try:
            current_weather = "clear"
            if hasattr(self.weather_markov, 'current_condition'):
                current_weather = self.weather_markov.current_condition

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

        # Actualizar clima
        try:
            self.weather_markov.update(dt)
            self.weather_markov.apply_to_game_state(self.state)
            ws = self.state.get("weather_state", {}) if isinstance(self.state, dict) else getattr(self.state,
                                                                                                  "weather_state", {})
            self.weather_renderer.update(dt, ws)
        except Exception as e:
            print(f"Error actualizando clima: {e}")
            # Entregas y recogidas al completar movimiento
            if was_moving and not self.player.moving:
                # Intentar recoger paquete
                if self.game_manager and hasattr(self.game_manager, 'try_pickup_at'):
                    picked_up = self.game_manager.try_pickup_at(self.player.cell_x, self.player.cell_y)
                    if picked_up:
                        self.show_notification("¡Paquete recogido! Ve al punto de entrega.")

                # Intentar entregar pedido
                if self.game_manager and hasattr(self.game_manager, 'try_deliver_at'):
                    result = self.game_manager.try_deliver_at(self.player.cell_x, self.player.cell_y)
                    if result:
                        self.show_notification(f"¡Pedido {result['job_id']} entregado!\n+${result['pay']:.0f}")


    def on_key_press(self, key: int, modifiers: int) -> None:
        self._last_input_time = time.time()

        # ACEPTAR/RECHAZAR NOTIFICACIONES (MEJORADO)
        if key == arcade.key.A:
            if self.job_notification_active and self.job_notification_data:
                self._accept_notification()
                return
            elif hasattr(self, '_pending_offer') and self._pending_offer:
                try:
                    on_accept, on_reject = self._pending_offer
                    if on_accept:
                        on_accept(None)
                    self._pending_offer = None
                    self._offer_job_id = None
                except Exception as e:
                    print(f"Error aceptando oferta: {e}")
                return

        if key == arcade.key.R:
            if self.job_notification_active and self.job_notification_data:
                self._reject_notification()
                return
            elif hasattr(self, '_pending_offer') and self._pending_offer:
                try:
                    on_accept, on_reject = self._pending_offer
                    if on_reject:
                        on_reject(None)
                    self._pending_offer = None
                    self._offer_job_id = None
                except Exception as e:
                    print(f"Error rechazando oferta: {e}")
                return

        # DEBUG: Recargar trabajos
        if key == arcade.key.L and modifiers & arcade.key.MOD_CTRL:
            self._load_initial_jobs()
            self.show_notification("🔄 Pedidos recargados")
            return

        # DEBUG: Forzar nuevo pedido
        if key == arcade.key.N and modifiers & arcade.key.MOD_CTRL:
            if self.job_manager and self.game_manager:
                current_time = self.game_manager.get_game_time()
                job = self.job_manager.peek_next_eligible(current_time)
                if job:
                    self._spawn_debug_notification(job)
                else:
                    self.show_notification("❌ No hay pedidos disponibles")
            return

        # Deshacer (Ctrl+Z)
        if key == arcade.key.Z and (modifiers & arcade.key.MOD_CTRL):
            if self.game_manager and hasattr(self.game_manager, 'undo_last_action'):
                if self.game_manager.undo_last_action():
                    self.show_notification("Última acción deshecha")
            return

        # Movimiento
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

        if self.game_manager and hasattr(self.game_manager, 'handle_Player_movement'):
            try:
                self.game_manager.handle_Player_movement(dx,dy)
            except Exception as e:
                print(f"Error en movimiento: {e}")
        else:
            moved = self.player.move_by(dx,dy,self.game_map)
            if not moved:
                self.show_notification("Movimiento bloqueado")

    def show_job_offer(self, job_data, on_accept, on_reject):
        """Muestra una oferta de trabajo - LLAMADO POR EL GAME_MANAGER"""
        try:
            job_id = job_data.get("id", "Unknown")
            payout = job_data.get("payout", 0)
            weight = job_data.get("weight", 0)

            message = f"📦 NUEVO PEDIDO\n{job_id}\nPago: ${payout}\nPeso: {weight}kg\n(A) Aceptar  (R) Rechazar"
            self.show_notification(message)

            # Guardar callbacks
            self._pending_offer = (on_accept, on_reject)
            self._offer_job_id = job_id

            print(f"🎯 OFERTA MOSTRADA: {job_id}")

        except Exception as e:
            print(f"❌ Error mostrando oferta: {e}")
            self._pending_offer = None

    def on_key_release(self, key: int, modifiers: int):
        """Maneja teclas para aceptar/rechazar ofertas"""
        if not hasattr(self, '_pending_offer') or self._pending_offer is None:
            return

        try:
            on_accept, on_reject = self._pending_offer

            if key == arcade.key.A:
                print("🎹 ACEPTAR oferta")
                if on_accept:
                    on_accept(None)
                self._pending_offer = None
                self._offer_job_id = None

            elif key == arcade.key.R:
                print("🎹 RECHAZAR oferta")
                if on_reject:
                    on_reject(None)
                self._pending_offer = None
                self._offer_job_id = None

        except Exception as e:
            print(f"❌ Error procesando oferta: {e}")
            self._pending_offer = None

    def _apply_facing(self):
        """Ajusta la rotación del sprite"""
        if not hasattr(self.player, "sprite"):
            return
        spr = self.player.sprite
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

    # game_window.py - AÑADIR ESTOS MÉTODOS NUEVOS A LA CLASE MapPlayerView

    def _draw_time_panel(self):
        """Dibuja el panel de información de tiempo"""
        if not self.game_manager:
            return

        # Panel de tiempo en la esquina superior izquierda del mapa
        panel_x = 10
        panel_y = SCREEN_HEIGHT - 100
        panel_width = 300
        panel_height = 90

        # Fondo del panel
        _draw_rect_lrbt_filled(panel_x, panel_x + panel_width, panel_y - panel_height, panel_y,
                               arcade.color.DARK_SLATE_GRAY)
        _draw_rect_lrbt_outline(panel_x, panel_x + panel_width, panel_y - panel_height, panel_y, arcade.color.BLUE, 2)

        # Título
        arcade.draw_text("⏰ TIEMPO DE SIMULACIÓN", panel_x + 10, panel_y - 20, arcade.color.GOLD, 12, bold=True)

        # Tiempo actual de simulación
        current_time = self.game_manager.get_game_time()
        minutes = int(current_time // 60)
        seconds = int(current_time % 60)

        # Tiempo restante
        time_remaining = self.game_manager.get_time_remaining()
        rem_minutes = int(time_remaining // 60)
        rem_seconds = int(time_remaining % 60)

        # Fecha/hora simulada
        current_map_time = self.game_manager.get_current_map_time()
        time_str = current_map_time.strftime("%H:%M:%S")
        date_str = current_map_time.strftime("%Y-%m-%d")

        # Dibujar información
        arcade.draw_text(f"Hora: {time_str}", panel_x + 15, panel_y - 40, arcade.color.WHITE, 11)
        arcade.draw_text(f"Fecha: {date_str}", panel_x + 15, panel_y - 55, arcade.color.WHITE, 11)
        arcade.draw_text(f"Transcurrido: {minutes:02d}:{seconds:02d}", panel_x + 15, panel_y - 70, arcade.color.CYAN,
                         11)

        # Color del tiempo restante según urgencia
        time_color = arcade.color.GREEN
        if time_remaining < 300:  # Menos de 5 minutos
            time_color = arcade.color.RED
        elif time_remaining < 600:  # Menos de 10 minutos
            time_color = arcade.color.ORANGE

        arcade.draw_text(f"Restante: {rem_minutes:02d}:{rem_seconds:02d}", panel_x + 15, panel_y - 85, time_color, 11,
                         bold=True)

    def _draw_job_time_info(self, job_data, x: int, y: int) -> int:
        """Dibuja la información de tiempo de un trabajo y retorna la nueva posición Y"""
        if not self.game_manager:
            return y

        job_id = self._raw_job_id(job_data)
        time_remaining = self.game_manager.get_job_time_remaining(job_data)

        if time_remaining == float('inf'):
            return y  # No hay deadline

        minutes = int(time_remaining // 60)
        seconds = int(time_remaining % 60)

        # Color según urgencia
        time_color = arcade.color.GREEN
        if time_remaining < 60:  # Menos de 1 minuto
            time_color = arcade.color.RED
        elif time_remaining < 300:  # Menos de 5 minutos
            time_color = arcade.color.ORANGE

        arcade.draw_text(f"⏱ {minutes:02d}:{seconds:02d}", x, y, time_color, 10)
        return y - 15

    # MODIFICAR _draw_job_notification para incluir información de tiempo
    def _draw_job_notification(self):
        """Dibuja la notificación de trabajo en la esquina inferior derecha con información de tiempo"""
        if not self.job_notification_active or not self.job_notification_data:
            return

        raw = self.job_notification_data
        job_id = self._raw_job_id(raw)
        payout = raw.get("payout", 0)
        weight = raw.get("weight", 0)
        priority = raw.get("priority", 1)
        description = raw.get("description", "Sin descripción")

        # Panel de notificación
        panel_width = 400
        panel_height = 250  # Aumentado para incluir tiempo
        left = SCREEN_WIDTH - panel_width - 20
        bottom = 100
        right = left + panel_width
        top = bottom + panel_height

        # Fondo del panel
        _draw_rect_lrbt_filled(left, right, bottom, top, arcade.color.DARK_BLUE)
        _draw_rect_lrbt_outline(left, right, bottom, top, arcade.color.GOLD, 3)

        # Título
        title_text = Text("📦 NUEVO PEDIDO", left + 10, top - 25, arcade.color.GOLD, 16, bold=True)
        title_text.draw()

        # Información del trabajo
        info_y = top - 50
        Text(f"ID: {job_id}", left + 15, info_y, arcade.color.WHITE, 12).draw()
        Text(f"Pago: ${payout}", left + 15, info_y - 20, arcade.color.GREEN, 12).draw()
        Text(f"Peso: {weight}kg", left + 15, info_y - 40, arcade.color.CYAN, 12).draw()
        Text(f"Prioridad: {priority}", left + 15, info_y - 60, arcade.color.ORANGE, 12).draw()

        # Información de tiempo si está disponible
        time_y = info_y - 80
        if self.game_manager:
            time_remaining = self.game_manager.get_job_time_remaining(raw)
            if time_remaining != float('inf'):
                minutes = int(time_remaining // 60)
                seconds = int(time_remaining % 60)
                time_color = arcade.color.GREEN if time_remaining > 300 else arcade.color.ORANGE if time_remaining > 60 else arcade.color.RED
                Text(f"Tiempo límite: {minutes:02d}:{seconds:02d}", left + 15, time_y, time_color, 12).draw()
                time_y -= 20

            # Fecha de entrega si está disponible
            deadline_str = raw.get("deadline")
            if deadline_str:
                # Formatear la fecha para que sea más legible
                try:
                    deadline_dt = self.game_manager._parse_iso_time(deadline_str)
                    deadline_formatted = deadline_dt.strftime("%H:%M")
                    Text(f"Entregar antes de: {deadline_formatted}", left + 15, time_y, arcade.color.YELLOW, 11).draw()
                    time_y -= 20
                except:
                    pass

        # Descripción (truncada si es muy larga)
        desc = description[:50] + "..." if len(description) > 50 else description
        Text(f"Desc: {desc}", left + 15, time_y, arcade.color.LIGHT_GRAY, 10).draw()

        # Controles y temporizador de aceptación
        controls_y = bottom + 30
        Text("(A) Aceptar  (R) Rechazar", left + 15, controls_y, arcade.color.YELLOW, 12).draw()

        time_left = int(self.job_notification_timer)
        Text(f"Decidir en: {time_left}s", left + 15, controls_y - 20, arcade.color.RED, 12).draw()

    # MODIFICAR on_draw para incluir el panel de tiempo
    def on_draw(self) -> None:
        self.clear()
        self.game_map.draw_debug(tile_size=TILE_SIZE, draw_grid_lines=True)

        # DIBUJAR MARCADORES DE TRABAJOS
        self._draw_job_markers()

        self.player.draw()
        self._draw_panel()
        self._draw_time_panel()  # NUEVO: Panel de tiempo
        self.weather_renderer.draw()

        # Dibujar notificación de trabajo (si está activa)
        self._draw_job_notification()