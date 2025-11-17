# game_manager.py - VERSIÓN FUSIONADA FINAL (completa)
"""
GameManager: gestiona tiempo simulado, trabajos (via JobManager), inventario/entregas,
interacción con player_manager (vista/player), undo, y reglas de fin de juego.
Diseñado para ser tolerante a distintos formatos de datos del API / state.
"""
from __future__ import annotations
import time
import logging
import datetime
from typing import Dict, Any, Optional

from .score_system import ScoreSystem
from ..run_api.api_client import ApiClient


class GameManager:
    def __init__(self):
        self.logger = logging.getLogger('GameManager')

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
        self.map_start_time: Optional[datetime.datetime] = None
        self.max_game_duration: Optional[float] = None  # segundos

    # ---------------- Inicialización ----------------
    def initialize_game(self, map_data: Optional[Dict[str, Any]], jobs_data: Optional[list], weather_data: Optional[dict]):
        """
        Inicializa subsistemas y carga trabajos. map_data debe contener 'start_time' (ISO) y 'max_time' (segundos)
        cuando sea provisto por la API. Si datos faltan, se cargan desde API o /data/.
        """
        # Offline fallback: fetch missing data using ApiClient
        api = ApiClient()
        if map_data is None:
            map_data = api.get_city_map()
        if jobs_data is None:
            jobs_data = api.get_jobs()
        if weather_data is None:
            weather_data = api.get_weather()

        from .player_state import PlayerState
        from .jobs_manager import JobManager
        from .undo_system import UndoSystem

        self.player_state = PlayerState()
        self.job_manager = JobManager()
        self.undo_system = UndoSystem(max_steps=30)

        # configurar tiempo desde map_data si está disponible
        try:
            self._setup_dynamic_time_system(map_data, jobs_data)
        except Exception as e:
            print(f"[GAME_MANAGER] Warning: fallo al configurar sistema de tiempo: {e}")
            if not self.map_start_time:
                self.map_start_time = datetime.datetime.now()
            if self.max_game_duration is None and map_data:
                try:
                    self.max_game_duration = float(map_data.get("max_time", 15 * 60))
                except Exception:
                    self.max_game_duration = 15 * 60

        self.game_start_real_time = time.time()
        try:
            self.job_manager._game_start_epoch = float(self.game_start_real_time)
        except Exception:
            pass

        try:
            self.player_state.initialize_game(map_data, jobs_data, weather_data, self.max_game_duration)
        except TypeError:
            try:
                self.player_state.initialize_game(map_data, jobs_data, weather_data)
            except Exception:
                pass
        except Exception:
            pass

        if jobs_data:
            for jd in jobs_data:
                try:
                    self.job_manager.add_job_from_raw(jd)
                except Exception as e:
                    print(f"[GAME_MANAGER] Error cargando job: {e}")

        self.is_running = True
        self.logger.info("Game initialized")
        self.logger.info(f"Map start time: {self.map_start_time}, max duration: {self.max_game_duration}")
        self.logger.info(f"Jobs loaded: {len(self.job_manager.all_jobs()) if self.job_manager else 0}")

    # ---------------- Sistema de tiempo ----------------
    def _setup_dynamic_time_system(self, map_data: Dict[str, Any], jobs_data: Optional[list]):
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
        self._process_job_deadlines(jobs_data)

    def _parse_iso_time(self, time_str: Any) -> datetime.datetime:
        """Parsea tiempo ISO - VERSIÓN MEJORADA"""
        try:
            if isinstance(time_str, datetime.datetime):
                return time_str  # Ya es datetime, retornar directamente

            if not isinstance(time_str, str):
                print(f"[TIME] Warning: time_str no es string: {type(time_str)}")
                return datetime.datetime.now()

            # Limpiar y formatear la cadena
            time_str = time_str.strip()
            if time_str.endswith("Z"):
                time_str = time_str[:-1] + "+00:00"

            # Intentar parsear con diferentes formatos
            try:
                return datetime.datetime.fromisoformat(time_str)
            except ValueError:
                # Fallback para formatos ligeramente diferentes
                for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"]:
                    try:
                        return datetime.datetime.strptime(time_str, fmt)
                    except ValueError:
                        continue
                # Último fallback
                return datetime.datetime.now()
        except Exception as e:
            print(f"[TIME] Error crítico parseando tiempo '{time_str}': {e}")
            return datetime.datetime.now()

    def _process_job_deadlines(self, jobs_data: Optional[list]):
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
                rel_release = float(job.get("release_time", 0.0) or 0.0)
                available = seconds_from_start - rel_release
                print(f"[TIME] job {job.get('id')} deadline in +{seconds_from_start:.0f}s (available {available:.0f}s)")
            except Exception as e:
                print(f"[GAME_MANAGER] Warning procesando deadline job: {e}")
                job["deadline_timestamp"] = None

    # ---------------- Helpers de tiempo ----------------
    def set_game_map(self, game_map): self.game_map = game_map

    def get_game_time(self) -> float:
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

    def get_current_map_time(self) -> datetime.datetime:
        if not self.map_start_time:
            return datetime.datetime.now()
        return self.map_start_time + datetime.timedelta(seconds=self.get_game_time())

    # ---------------- Caducidad de trabajos ----------------
    def is_job_expired(self, job_data: Dict[str, Any]) -> bool:
        if not job_data:
            return False
        deadline_ts = job_data.get("deadline_timestamp")
        if deadline_ts is None:
            return False
        try:
            return float(self.get_game_time()) > float(deadline_ts)
        except Exception:
            return False

    def get_game_start_timestamp(self) -> float:
        """Obtiene el timestamp de inicio del juego - VERSIÓN CORREGIDA"""
        try:
            if hasattr(self, 'map_start_time') and self.map_start_time is not None:
                # map_start_time ya es un objeto datetime, usar directamente
                return self.map_start_time.timestamp()
            elif hasattr(self, '_game_start_epoch'):
                return self._game_start_epoch
            else:
                # Fallback al tiempo actual menos el tiempo transcurrido
                import time
                current_time = time.time()
                game_time = self.get_game_time()
                return current_time - game_time
        except Exception as e:
            print(f"[TIME] Error obteniendo start timestamp: {e}")
            import time
            return time.time()

    def get_job_time_remaining(self, job_data: dict) -> float:
        """Calcula el tiempo restante para un trabajo.
        Si existe `accepted_at` y `release_time > 0`, usa ventana desde la aceptación.
        En caso contrario, si hay `deadline`, usa tiempo hasta deadline.
        Si no hay deadline, retorna infinito.
        """
        try:
            # Ventana por release_time desde aceptación
            release_time = job_data.get("release_time", 0)
            accepted_at = job_data.get("accepted_at")
            try:
                release_time = float(release_time or 0.0)
            except (TypeError, ValueError):
                release_time = 0.0
            try:
                accepted_at = float(accepted_at) if accepted_at is not None else None
            except (TypeError, ValueError):
                accepted_at = None

            if release_time > 0.0 and accepted_at is not None:
                current_game_time = float(self.get_game_time())
                elapsed_since_accept = current_game_time - accepted_at
                return release_time - elapsed_since_accept

            # Fallback: tiempo hasta deadline
            deadline_str = job_data.get("deadline")
            if not deadline_str:
                return float("inf")
            game_start_ts = self.get_game_start_timestamp()
            deadline_dt = datetime.datetime.fromisoformat(deadline_str.replace('Z', '+00:00'))
            deadline_ts = deadline_dt.timestamp()
            current_ts = game_start_ts + float(self.get_game_time())
            return deadline_ts - current_ts

        except Exception as e:
            print(f"[TIME] Error calculando tiempo restante: {e}")
            return float("inf")

    def get_job_total_time(self, job_data: dict) -> float:
        """Calcula el tiempo total disponible para el trabajo.
        Si el pedido usa ventana por `release_time` y fue aceptado, el total es `release_time`.
        En caso contrario, usa (deadline - (game_start + release_time)).
        """
        try:
            release_time = job_data.get("release_time", 0)
            accepted_at = job_data.get("accepted_at")
            try:
                release_time = float(release_time or 0.0)
            except (TypeError, ValueError):
                release_time = 0.0
            if release_time > 0.0 and accepted_at is not None:
                return release_time

            deadline_str = job_data.get("deadline")
            if not deadline_str:
                return float("inf")

            game_start_ts = self.get_game_start_timestamp()
            deadline_dt = datetime.datetime.fromisoformat(deadline_str.replace('Z', '+00:00'))
            deadline_ts = deadline_dt.timestamp()
            total_time = deadline_ts - (game_start_ts + release_time)
            return max(0.0, total_time)

        except Exception as e:
            print(f"[TIME] Error calculando tiempo total: {e}")
            return float("inf")

    # ---------------- Actualización ----------------
    def update(self, dt: float):
        if not self.is_running or dt is None:
            return
        try:
            self.game_simulated_time += float(dt) * float(self.time_scale)
        except Exception:
            pass

        if self.max_game_duration is not None:
            try:
                if self.get_game_time() >= float(self.max_game_duration):
                    self._handle_game_timeout()
                    return
            except Exception:
                pass

        try:
            now = self.get_game_time()
            if now - self._last_job_check >= self.JOB_CHECK_INTERVAL:
                self._last_job_check = now
                self._check_for_new_jobs(now)
        except Exception as e:
            print(f"[GAME_MANAGER] Error en update job check: {e}")

    # ---------------- Timeout ----------------
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

    # ---------------- Ofertas ----------------
    def _check_for_new_jobs(self, current_time: float):
        if not self.job_manager or not self.player_manager:
            return
        try:
            job = self.job_manager.peek_next_eligible(current_time)
            if not job or getattr(job, "visible_pickup", False):
                return
            if self.is_job_expired(getattr(job, "raw", {}) or {}):
                try:
                    self.job_manager.mark_rejected(job.id)
                except Exception:
                    job.rejected = True
                print(f"[GAME_MANAGER] Job {job.id} expirado al presentarlo")
                return
            if hasattr(self.player_manager, "show_job_offer"):
                job.visible_pickup = True
                def on_accept(_):
                    try: self._accept_job(job.id)
                    except Exception as e: print(f"[GAME_MANAGER] on_accept error: {e}")
                def on_reject(_):
                    try: self.job_manager.mark_rejected(job.id)
                    except Exception: job.rejected = True
                try:
                    self.player_manager.show_job_offer(job.raw or {}, on_accept, on_reject)
                    print(f"[GAME_MANAGER] Oferta mostrada: {job.id}")
                except Exception as e:
                    job.visible_pickup = False
                    print(f"[GAME_MANAGER] Error mostrando oferta: {e}")
        except Exception as e:
            print(f"[GAME_MANAGER] Error al chequear nuevos jobs: {e}")

    # ---------------- Aceptar trabajos ----------------
    def _accept_job(self, job_id: str) -> bool:
        if not self.job_manager or not self.player_state:
            return False
        job = self.job_manager.get_job(job_id)
        if not job:
            print(f"[GAME_MANAGER] accept_job: job {job_id} no existe")
            return False
        if self.is_job_expired(job.raw or {}):
            print(f"[GAME_MANAGER] accept_job: job {job_id} ya expirado")
            try: self.job_manager.mark_rejected(job_id)
            except Exception: job.rejected = True
            return False
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
        if not added:
            try: self.job_manager.mark_rejected(job_id)
            except Exception: job.rejected = True
            print(f"[GAME_MANAGER] accept_job: no se pudo añadir {job_id}")
            return False
        job.visible_pickup, job.picked_up, job.dropoff_visible, job.completed = True, False, False, False
        self.logger.info(f"Job {job_id} accepted and added to inventory")
        return True

    # ---------------- Entregas ----------------
    def _get_job_dropoff_coords(self, job):
        try:
            return tuple(job.dropoff)
        except Exception:
            raw = getattr(job, "raw", {}) or {}
            dropoff_raw = raw.get("dropoff", None)
            if dropoff_raw:
                return tuple(dropoff_raw)
        return None, None

    def try_deliver_at(self, tile_x: int, tile_y: int) -> Optional[Dict[str, Any]]:
        if not self.player_state:
            return None
        inv = getattr(self.player_state, "inventory", None)
        if not inv:
            return None
        delivered_any, result = False, None
        jobs_to_check = []
        node = getattr(inv.deque, "head", None)
        while node:
            job = node.val if hasattr(node, "val") else node
            if getattr(job, "picked_up", False) and not getattr(job, "completed", False):
                jobs_to_check.append(job)
            node = getattr(node, "next", None)

        for job in jobs_to_check:
            try:
                dx, dy = self._get_job_dropoff_coords(job)
                if dx is None or dy is None:
                    continue
                if abs(int(dx) - tile_x) + abs(int(dy) - tile_y) <= 1:
                    current = self.get_game_time()
                    deadline = getattr(job, "raw", {}).get("deadline_timestamp", None)
                    on_time, seconds_late, time_bonus = True, 0.0, 1.0
                    if deadline is not None:
                        if float(current) > float(deadline):
                            on_time = False
                            seconds_late = float(current) - float(deadline)
                            time_bonus = 0.5
                    base_payout = float(getattr(job, "raw", {}).get("payout", getattr(job, "payout", 0.0) or 0.0))
                    pay_mult = 1.0
                    try:
                        if hasattr(self.player_state, "get_payment_multiplier"):
                            pay_mult = float(self.player_state.get_payment_multiplier())
                        elif hasattr(self.player_state, "player_stats") and hasattr(self.player_state.player_stats,
                                                                                    "get_payment_multiplier"):
                            pay_mult = float(self.player_state.player_stats.get_payment_multiplier())
                    except Exception:
                        pass
                    final_pay = base_payout * pay_mult * time_bonus
                    self.player_state.money = float(getattr(self.player_state, "money", 0.0)) + final_pay
                    rep_delta = 0
                    try:
                        if on_time:
                            rep_delta = self.player_state.update_reputation("delivery_on_time", {})
                        else:
                            rep_delta = self.player_state.update_reputation("delivery_late",
                                                                            {"seconds_late": seconds_late})
                    except Exception:
                        pass
                    job.completed = True
                    try:
                        inv.remove(getattr(job, "id", None))
                    except Exception:
                        try:
                            inv.remove(job.id)
                        except Exception:
                            for item in list(getattr(inv, 'deque', [])):
                                if getattr(item, "id", None) == job.id:
                                    inv.deque.remove(item)
                                    break
                    self.logger.info(f"Delivered job {job.id} at {tile_x},{tile_y} (dropoff {dx},{dy}) pay={final_pay:.2f}")
                    result = {
                        "job_id": getattr(job, "id", None),
                        "pay": final_pay,
                        "rep_delta": rep_delta,
                        "on_time": on_time,
                        "seconds_late": seconds_late if not on_time else 0.0
                    }
                    delivered_any = True
            except Exception as e:
                print(f"[GAME_MANAGER] Error procesando entrega: {e}")
        return result if delivered_any else None

    # ---------------- Pickups ----------------
    def try_pickup_at(self, tile_x: int, tile_y: int) -> bool:
        if not self.job_manager:
            return False
        try:
            for job in self.job_manager.get_active_jobs():
                if not getattr(job, "accepted", False) or getattr(job, "picked_up", False) or getattr(job, "completed", False):
                    continue
                try:
                    pickup_pos = tuple(getattr(job, "pickup", ()))
                except Exception:
                    pickup_pos = tuple(job.pickup if hasattr(job, "pickup") else ())
                if pickup_pos == (tile_x, tile_y):
                    job.picked_up, job.dropoff_visible = True, True
                    self.logger.info(f"Package {job.id} picked up at {tile_x},{tile_y}")
                    return True
                try:
                    px, py = pickup_pos
                    if (tile_x, tile_y) in [(px+1,py),(px-1,py),(px,py+1),(px,py-1)]:
                        job.picked_up, job.dropoff_visible = True, True
                        self.logger.info(f"Package {job.id} picked up adjacent to {pickup_pos}")
                        return True
                except Exception:
                    pass
        except Exception as e:
            print(f"[GAME_MANAGER] Error en try_pickup_at: {e}")
        return False

    # ---------------- Undo ----------------
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
            if prev is not None:
                self.undo_system.restore_state(
                    prev,
                    self.player_state,
                    self.player_state.inventory,
                    self.player_state.weather_system,
                    self.player_manager
                )
                self.logger.info("Undo applied")
                return True
            return False
        except Exception as e:
            print(f"[GAME_MANAGER] Error en undo: {e}")
            return False

    def undo_n_steps(self, n: int) -> bool:
        if not self.undo_system or not self.player_state or not self.player_state.inventory or not self.player_manager:
            return False
        try:
            last_state = None
            steps = 0
            for _ in range(max(0, int(n))):
                if not self.undo_system.can_undo():
                    break
                last_state = self.undo_system.undo()
                steps += 1
            if last_state is None:
                return False
            self.undo_system.restore_state(
                last_state,
                self.player_state,
                self.player_state.inventory,
                self.player_state.weather_system,
                self.player_manager
            )
            return True
        except Exception as e:
            print(f"[GAME_MANAGER] Error en undo_n_steps: {e}")
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
        self.logger.info(f"Game over: {message}")
        self.is_running = False
