# game_manager.py - PARCHE COMPLETO Y LISTO
"""
GameManager: gestiona tiempo simulado, trabajos (via JobManager), inventario/entregas,
interacción con player_manager (vista/player), undo, y reglas de fin de juego.
Diseñado para ser tolerante a distintos formatos de datos del API / state.
"""
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from .score_system import ScoreSystem


class GameManager:
    def __init__(self):
        # subsistemas (se asignan en initialize_game)
        self.player_state = None
        self.job_manager = None
        self.score_system = ScoreSystem()
        self.is_running = False

        # tiempo real / simulado
        self.game_start_real_time: float = 0.0
        self.game_simulated_time: float = 0.0
        self.time_scale: float = 1.0

        # undo / player_manager (vista)
        self.undo_system = None
        self.player_manager = None

        # job checks
        self._last_job_check: float = 0.0
        self.JOB_CHECK_INTERVAL: float = 1.0

        # mapa / tiempo del mapa (API)
        self.game_map = None
        self.map_start_time: Optional[datetime] = None
        self.max_game_duration: Optional[float] = None  # segundos

    # ---------------- Inicialización ----------------
    def initialize_game(self, map_data: Dict[str, Any], jobs_data: Optional[list], weather_data: Optional[dict]):
        """
        Inicializa subsistemas y carga trabajos. map_data debe contener 'start_time' (ISO) y 'max_time' (segundos)
        cuando sea provisto por la API.
        """
        from .player_state import PlayerState
        from .jobs_manager import JobManager
        from .undo_system import UndoSystem

        # crear subsistemas básicos
        self.player_state = PlayerState()
        self.job_manager = JobManager()
        self.undo_system = UndoSystem(max_steps=30)

        # configurar tiempo desde map_data si está disponible
        try:
            self._setup_dynamic_time_system(map_data, jobs_data)
        except Exception as e:
            # no fatal: continuar con valores por defecto
            print(f"[GAME_MANAGER] Warning: fallo al configurar sistema de tiempo: {e}")
            if not self.map_start_time:
                self.map_start_time = datetime.now()
            if self.max_game_duration is None and map_data:
                try:
                    self.max_game_duration = float(map_data.get("max_time", 15 * 60))
                except Exception:
                    self.max_game_duration = 15 * 60

        # marcar inicio en tiempo real (epoch)
        self.game_start_real_time = time.time()
        # si JobManager soporta _game_start_epoch, informarlo (algunos parches lo usan)
        try:
            self.job_manager._game_start_epoch = float(self.game_start_real_time)
        except Exception:
            # si no existe, okay
            pass

        # pasar datos al player_state (varias firmas posibles)
        try:
            self.player_state.initialize_game(map_data, jobs_data, weather_data, self.max_game_duration)
        except TypeError:
            try:
                self.player_state.initialize_game(map_data, jobs_data, weather_data)
            except Exception:
                # si falla, ok
                pass
        except Exception:
            pass

        # cargar trabajos
        if jobs_data:
            for jd in jobs_data:
                try:
                    self.job_manager.add_job_from_raw(jd)
                except Exception as e:
                    print(f"[GAME_MANAGER] Error cargando job: {e}")

        self.is_running = True
        print("[GAME_MANAGER] Inicializado")
        print(f"  map_start_time: {self.map_start_time}")
        print(f"  max_game_duration: {self.max_game_duration}")
        print(f"  jobs cargados: {len(self.job_manager.all_jobs()) if self.job_manager else 0}")

    def _setup_dynamic_time_system(self, map_data: Dict[str, Any], jobs_data: Optional[list]):
        """Configuración robusta del sistema de tiempo usando datos del map_data (start_time ISO y max_time)."""
        if not map_data:
            raise ValueError("map_data requerido para configurar tiempo")

        start_time_str = map_data.get("start_time")
        if not start_time_str:
            raise ValueError("map_data debe contener 'start_time' (ISO)")

        self.map_start_time = self._parse_iso_time(start_time_str)

        max_time = map_data.get("max_time")
        if max_time is None:
            raise ValueError("map_data debe contener 'max_time' (segundos)")
        try:
            self.max_game_duration = float(max_time)
        except Exception:
            self.max_game_duration = max_time

        # convertir deadlines absolutos de jobs (ISO) a offsets desde map_start_time
        self._process_job_deadlines(jobs_data)

    def _parse_iso_time(self, time_str: str) -> datetime:
        """Parse simplificado: maneja trailing 'Z' y fallbacks."""
        try:
            if isinstance(time_str, str) and time_str.endswith("Z"):
                time_str = time_str[:-1] + "+00:00"
            return datetime.fromisoformat(time_str)
        except Exception as e:
            print(f"[GAME_MANAGER] Error parseando ISO time '{time_str}': {e}")
            return datetime.now()

    def _process_job_deadlines(self, jobs_data: Optional[list]):
        """Para cada job con 'deadline' en ISO, guarda job['deadline_timestamp'] = segundos desde map_start_time."""
        if not jobs_data or not self.map_start_time:
            return
        for job in jobs_data:
            try:
                dl = job.get("deadline")
                if not dl:
                    job["deadline_timestamp"] = None
                    continue
                dl_dt = self._parse_iso_time(dl)
                seconds_from_start = (dl_dt - self.map_start_time).total_seconds()
                job["deadline_timestamp"] = float(seconds_from_start)
                # debug
                rel_release = float(job.get("release_time", 0.0) or 0.0)
                available = seconds_from_start - rel_release
                print(f"[TIME] job {job.get('id')} deadline in +{seconds_from_start:.0f}s (available {available:.0f}s)")
            except Exception as e:
                print(f"[GAME_MANAGER] Warning procesando deadline job: {e}")
                job["deadline_timestamp"] = None

    # ---------------- Time helpers ----------------
    def set_game_map(self, game_map):
        self.game_map = game_map

    def get_game_time(self) -> float:
        """Retorna tiempo simulado (segundos), acotado por max_game_duration si está definido."""
        try:
            t = max(0.0, float(self.game_simulated_time))
        except Exception:
            t = 0.0
        if self.max_game_duration is None:
            return t
        try:
            return min(t, float(self.max_game_duration))
        except Exception:
            return t

    def get_time_remaining(self) -> float:
        if self.max_game_duration is None:
            return float("inf")
        try:
            return max(0.0, float(self.max_game_duration) - float(self.get_game_time()))
        except Exception:
            return float("inf")

    def get_current_map_time(self) -> datetime:
        if not self.map_start_time:
            return datetime.now()
        return self.map_start_time + timedelta(seconds=self.get_game_time())

    # ---------------- Job expiry helpers ----------------
    def is_job_expired(self, job_data: Dict[str, Any]) -> bool:
        if not job_data:
            return False
        deadline_ts = job_data.get("deadline_timestamp")
        if deadline_ts is None:
            return False
        try:
            now = float(self.get_game_time())
            return now > float(deadline_ts)
        except Exception:
            return False

    def get_job_time_remaining(self, job_data: Dict[str, Any]) -> float:
        if not job_data:
            return float("inf")
        deadline_ts = job_data.get("deadline_timestamp")
        if deadline_ts is None:
            return float("inf")
        try:
            return max(0.0, float(deadline_ts) - float(self.get_game_time()))
        except Exception:
            return float("inf")

    # ---------------- Main update ----------------
    def update(self, dt: float):
        """
        Avanza la simulación. dt debe ser segundos (float).
        Protecciones contra None/valores erróneos.
        """
        if not self.is_running:
            return

        if dt is None:
            return

        try:
            self.game_simulated_time += float(dt) * float(self.time_scale)
        except Exception:
            try:
                self.game_simulated_time += float(dt)
            except Exception:
                pass

        # timeout solo si max_game_duration está definido
        if self.max_game_duration is not None:
            try:
                if self.get_game_time() >= float(self.max_game_duration):
                    self._handle_game_timeout()
                    return
            except Exception:
                pass

        # chequear nuevos trabajos periódicamente
        try:
            now = self.get_game_time()
            if now - self._last_job_check >= self.JOB_CHECK_INTERVAL:
                self._last_job_check = now
                self._check_for_new_jobs(now)
        except Exception as e:
            print(f"[GAME_MANAGER] Error en update job check: {e}")

    def _handle_game_timeout(self):
        self.is_running = False
        try:
            if self.player_state:
                goal = getattr(self.player_state, "map_data", {}).get("goal", None)
                money = getattr(self.player_state, "money", 0.0)
                if goal is not None and money >= goal:
                    self.game_over("¡Victoria! Alcanzaste la meta")
                else:
                    self.game_over("Derrota: Tiempo agotado")
            else:
                self.game_over("Derrota: Tiempo agotado")
        except Exception:
            self.game_over("Derrota: Tiempo agotado (error interno)")

    # ---------------- Job flow: mostrar ofertas ----------------
    def _check_for_new_jobs(self, current_time: float):
        """Busca siguiente trabajo elegible y lo muestra al player_manager (si corresponde)."""
        if not self.job_manager or not self.player_manager:
            return

        try:
            job = self.job_manager.peek_next_eligible(current_time)
            if not job:
                return

            # ignorar si ya visible
            if getattr(job, "visible_pickup", False):
                return

            # comprobar expiración
            if self.is_job_expired(getattr(job, "raw", {}) or {}):
                try:
                    self.job_manager.mark_rejected(job.id)
                except Exception:
                    job.rejected = True
                print(f"[GAME_MANAGER] Job {job.id} expirado al presentarlo")
                return

            # mostrar oferta
            if hasattr(self.player_manager, "show_job_offer"):
                # marcar visible (evitar race)
                job.visible_pickup = True

                def on_accept(_):
                    try:
                        self._accept_job(job.id)
                    except Exception as e:
                        print(f"[GAME_MANAGER] on_accept error: {e}")

                def on_reject(_):
                    try:
                        self.job_manager.mark_rejected(job.id)
                    except Exception:
                        job.rejected = True

                try:
                    self.player_manager.show_job_offer(job.raw or {}, on_accept, on_reject)
                    print(f"[GAME_MANAGER] Oferta mostrada: {job.id}")
                except Exception as e:
                    # revertir visible si falla mostrar
                    job.visible_pickup = False
                    print(f"[GAME_MANAGER] Error mostrando oferta: {e}")

        except Exception as e:
            print(f"[GAME_MANAGER] Error al chequear nuevos jobs: {e}")

    def _accept_job(self, job_id: str) -> bool:
        """Aceptar Job: marcar en JobManager y añadir al inventario del player_state."""
        if not self.job_manager or not self.player_state:
            return False

        job = self.job_manager.get_job(job_id)
        if not job:
            print(f"[GAME_MANAGER] accept_job: job {job_id} no existe")
            return False

        # comprobar expiración
        if self.is_job_expired(job.raw or {}):
            print(f"[GAME_MANAGER] accept_job: job {job_id} ya expirado")
            try:
                self.job_manager.mark_rejected(job_id)
            except Exception:
                job.rejected = True
            return False

        # inventario
        inv = getattr(self.player_state, "inventory", None)
        if inv and not inv.can_add(job):
            print(f"[GAME_MANAGER] accept_job: capacidad insuficiente para {job_id}")
            job.visible_pickup = False
            return False

        ok = self.job_manager.accept_job(job_id)
        if not ok:
            print(f"[GAME_MANAGER] accept_job: job_manager rechazó aceptar {job_id}")
            return False

        added = False
        try:
            if inv and hasattr(inv, "add"):
                added = inv.add(job)
        except Exception as e:
            print(f"[GAME_MANAGER] accept_job: error añadiendo a inventario: {e}")
            added = False

        if not added:
            try:
                self.job_manager.mark_rejected(job_id)
            except Exception:
                job.rejected = True
            print(f"[GAME_MANAGER] accept_job: no se pudo añadir {job_id} al inventario (revertido)")
            return False

        # flags visuales
        job.visible_pickup = True
        job.picked_up = False
        job.dropoff_visible = False
        job.completed = False

        print(f"[GAME_MANAGER] Job {job_id} aceptado y añadido al inventario")
        return True

    # ---------------- Entregas y pickups ----------------
    def try_deliver_at(self, tile_x: int, tile_y: int) -> Optional[Dict[str, Any]]:
        """Intentar entregar paquetes en la celda actual. Retorna resumen si se completó."""
        if not self.player_state:
            return None

        inv = getattr(self.player_state, "inventory", None)
        if not inv:
            return None

        node = getattr(inv.deque, "head", None)
        while node:
            job = node.val if hasattr(node, "val") else node
            try:
                if not getattr(job, "picked_up", False) or getattr(job, "completed", False):
                    node = getattr(node, "next", None)
                    continue

                raw = getattr(job, "raw", {}) or {}
                drop = tuple(raw.get("dropoff") or getattr(job, "dropoff", ()))
                if not isinstance(drop, tuple):
                    try:
                        drop = tuple(drop)
                    except Exception:
                        drop = tuple(getattr(job, "dropoff", ()))

                if drop == (tile_x, tile_y):
                    current = self.get_game_time()
                    deadline = raw.get("deadline_timestamp", None)
                    on_time = True
                    seconds_late = 0.0
                    time_bonus = 1.0

                    if deadline is not None:
                        try:
                            if float(current) > float(deadline):
                                on_time = False
                                seconds_late = float(current) - float(deadline)
                                time_bonus = 0.5
                        except Exception:
                            pass

                    base_payout = float(raw.get("payout", getattr(job, "payout", 0.0) or 0.0))

                    # multiplicador desde player_state o player_stats
                    pay_mult = 1.0
                    try:
                        if hasattr(self.player_state, "get_payment_multiplier"):
                            pay_mult = float(self.player_state.get_payment_multiplier())
                        elif hasattr(self.player_state, "player_stats") and hasattr(self.player_state.player_stats, "get_payment_multiplier"):
                            pay_mult = float(self.player_state.player_stats.get_payment_multiplier())
                    except Exception:
                        pay_mult = 1.0

                    final_pay = base_payout * pay_mult * time_bonus
                    try:
                        self.player_state.money = float(getattr(self.player_state, "money", 0.0)) + final_pay
                    except Exception:
                        pass

                    # reputación
                    rep_delta = 0
                    try:
                        if on_time:
                            rep_delta = self.player_state.update_reputation("delivery_on_time", {})
                        else:
                            rep_delta = self.player_state.update_reputation("delivery_late", {"seconds_late": seconds_late})
                    except Exception:
                        pass

                    # marcar completado y remover del inventario
                    job.completed = True
                    try:
                        inv.remove(getattr(job, "id", None))
                    except Exception:
                        try:
                            inv.remove(job.id)
                        except Exception:
                            pass

                    print(f"[GAME_MANAGER] Entregado {job.id} pay={final_pay:.2f} on_time={on_time}")
                    return {
                        "job_id": getattr(job, "id", None),
                        "pay": final_pay,
                        "rep_delta": rep_delta,
                        "on_time": on_time,
                        "seconds_late": seconds_late if not on_time else 0.0
                    }
            except Exception:
                # proteger bucle
                pass
            node = getattr(node, "next", None)
        return None

    def try_pickup_at(self, tile_x: int, tile_y: int) -> bool:
        """
        Intentar recoger un paquete (si ya fue aceptado).
        Permite pickup si el jugador está en la celda exacta o en una celda adyacente (4-direcciones).
        """
        if not self.job_manager:
            return False

        try:
            for job in self.job_manager.get_active_jobs():
                if not getattr(job, "accepted", False):
                    continue
                if getattr(job, "picked_up", False) or getattr(job, "completed", False):
                    continue

                try:
                    pickup_pos = tuple(getattr(job, "pickup", ()))
                except Exception:
                    pickup_pos = tuple(job.pickup if hasattr(job, "pickup") else ())

                # chequeo exacto
                if pickup_pos == (tile_x, tile_y):
                    job.picked_up = True
                    job.dropoff_visible = True
                    print(f"[GAME_MANAGER] Paquete {job.id} recogido (exact) en {tile_x},{tile_y}")
                    return True

                # chequeo adyacente (4-direcciones)
                try:
                    px, py = pickup_pos
                    neighbors = [(px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)]
                    if (tile_x, tile_y) in neighbors:
                        job.picked_up = True
                        job.dropoff_visible = True
                        print(f"[GAME_MANAGER] Paquete {job.id} recogido (adjacent) en {tile_x},{tile_y} cerca de {pickup_pos}")
                        return True
                except Exception:
                    # pickup_pos no iterable o inválido -> ignorar
                    pass
        except Exception as e:
            print(f"[GAME_MANAGER] Error en try_pickup_at: {e}")
        return False

    # ---------------- Undo / state save ----------------
    def save_current_state(self):
        if not self.undo_system or not self.player_state:
            return
        try:
            state_snapshot = self.undo_system.get_state_snapshot(
                self.player_state,
                self.player_state.inventory,
                self.player_state.weather_system,
                self.player_manager
            )
            self.undo_system.save_state(state_snapshot)
        except Exception as e:
            print(f"[GAME_MANAGER] Error saving state: {e}")

    def undo_last_action(self) -> bool:
        if not self.undo_system or not self.undo_system.can_undo():
            return False
        try:
            prev = self.undo_system.undo()
            self.undo_system.restore_state(
                prev,
                self.player_state,
                self.player_state.inventory,
                self.player_state.weather_system,
                self.player_manager
            )
            print("[GAME_MANAGER] Undo aplicado")
            return True
        except Exception as e:
            print(f"[GAME_MANAGER] Error en undo: {e}")
            return False

    def handle_player_movement(self, dx: int, dy: int):
        """Guardar estado y delegar movimiento al player_manager (si existe)."""
        self.save_current_state()
        if self.player_manager and hasattr(self.player_manager, "move_by"):
            try:
                self.player_manager.move_by(dx, dy, self.game_map)
            except Exception as e:
                print(f"[GAME_MANAGER] Error moviendo player_manager: {e}")

    # ---------------- Game over ----------------
    def game_over(self, message: str):
        print(f"[GAME_MANAGER] GAME OVER: {message}")
        self.is_running = False
