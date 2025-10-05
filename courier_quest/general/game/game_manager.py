# game_manager.py - SISTEMA DE TIEMPO CON FECHAS REALES
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from .score_system import ScoreSystem


class GameManager:
    def __init__(self):
        self.player_state = None
        self.job_manager = None
        self.score_system = ScoreSystem()
        self.is_running = False
        self.game_start_time = 0.0
        self.undo_system = None
        self.player_manager = None
        self._last_job_check = 0.0
        self.JOB_CHECK_INTERVAL = 1.0
        self.game_map = None

        # Nuevo: Sistema de tiempo con fechas reales
        self.map_start_time = None
        self.game_start_real_time = None
        self.max_game_duration = 900  # 15 minutos por defecto

    def initialize_game(self, map_data, jobs_data, weather_data):
        """Inicializa el juego con fechas reales del JSON"""
        from .player_state import PlayerState
        from .jobs_manager import JobManager
        from .undo_system import UndoSystem

        self.player_state = PlayerState()
        self.job_manager = JobManager()
        self.undo_system = UndoSystem(max_steps=30)

        # Configurar sistema de tiempo con fechas reales
        self._setup_real_time_system(map_data, jobs_data)

        # establecer tiempo de inicio real
        self.game_start_real_time = time.time()
        self.player_state.start_time_epoch = self.game_start_real_time

        # inicializar componentes
        self.player_state.initialize_game(map_data, jobs_data, weather_data)

        # cargar trabajos en job_manager con tiempos reales
        if jobs_data:
            for job_data in jobs_data:
                self.job_manager.add_job_from_raw(job_data)

        self.is_running = True

        # debug inicial
        current_time = self.get_game_time()
        available = self.job_manager.get_available_jobs(current_time)
        print(
            f"[GAME_MANAGER] inicializado: {len(self.job_manager.all_jobs())} jobs cargados, {len(available)} disponibles")
        print(f"[TIME] Tiempo de inicio del mapa: {self.map_start_time}")
        print(f"[TIME] Duración máxima: {self.max_game_duration}s")

    def _setup_real_time_system(self, map_data, jobs_data):
        """Configura el sistema de tiempo usando las fechas del JSON"""
        # Obtener start_time del mapa
        start_time_str = map_data.get("start_time", "2025-09-01T12:00:00Z")
        self.map_start_time = self._parse_iso_time(start_time_str)

        # Obtener max_time del mapa (en segundos)
        self.max_game_duration = map_data.get("max_time", 900)

        # Procesar deadlines de los trabajos
        self._process_job_deadlines(jobs_data)

    def _parse_iso_time(self, time_str: str) -> datetime:
        """Convierte string ISO a datetime object"""
        try:
            # Manejar formato con 'Z' (UTC)
            if time_str.endswith('Z'):
                time_str = time_str[:-1] + '+00:00'
            return datetime.fromisoformat(time_str)
        except Exception as e:
            print(f"Error parseando tiempo {time_str}: {e}")
            # Fallback: tiempo actual
            return datetime.now()

    def _process_job_deadlines(self, jobs_data):
        """Convierte deadlines de string a timestamp y calcula release_time si es necesario"""
        if not jobs_data:
            return

        for job_data in jobs_data:
            # Procesar deadline
            deadline_str = job_data.get("deadline")
            if deadline_str:
                deadline_dt = self._parse_iso_time(deadline_str)
                # Convertir a segundos desde el inicio del mapa
                time_since_start = (deadline_dt - self.map_start_time).total_seconds()
                job_data["deadline_timestamp"] = time_since_start
                print(
                    f"[TIME] Job {job_data.get('id')} - Deadline: {deadline_str} -> {time_since_start:.0f}s desde inicio")

            # Si release_time es 0, significa que está disponible inmediatamente
            # Si es mayor que 0, significa segundos desde el inicio del mapa
            release_time = job_data.get("release_time", 0)
            if release_time > 0:
                print(f"[TIME] Job {job_data.get('id')} - Release en {release_time}s desde inicio")

    def set_game_map(self, game_map):
        """Establece la referencia al mapa del juego"""
        self.game_map = game_map

    def get_game_time(self) -> float:
        """Tiempo de juego en segundos (desde inicio del mapa en tiempo simulado)."""
        if not self.game_start_real_time:
            return 0.0

        # Tiempo real transcurrido desde que empezó el juego
        real_time_elapsed = time.time() - self.game_start_real_time

        # Para simular el tiempo del mapa, usamos el tiempo real pero podríamos
        # acelerarlo o usar lógica más compleja si fuera necesario
        return min(real_time_elapsed, self.max_game_duration)

    def get_time_remaining(self) -> float:
        """Tiempo restante en segundos basado en max_time del mapa"""
        return max(0, self.max_game_duration - self.get_game_time())

    def get_current_map_time(self) -> datetime:
        """Retorna la fecha/hora actual en la simulación del mapa"""
        if not self.map_start_time:
            return datetime.now()

        current_simulated_time = self.map_start_time + timedelta(seconds=self.get_game_time())
        return current_simulated_time

    def is_job_expired(self, job_data: Dict[str, Any]) -> bool:
        """Verifica si un trabajo ha expirado basado en su deadline"""
        deadline_timestamp = job_data.get("deadline_timestamp")
        if not deadline_timestamp:
            return False

        current_time = self.get_game_time()
        return current_time > deadline_timestamp

    def get_job_time_remaining(self, job_data: Dict[str, Any]) -> float:
        """Tiempo restante para un trabajo antes de que expire"""
        deadline_timestamp = job_data.get("deadline_timestamp")
        if not deadline_timestamp:
            return float('inf')

        current_time = self.get_game_time()
        return max(0, deadline_timestamp - current_time)

    def update(self, dt: float):
        """Llamado desde el loop principal (Arcade on_update)."""
        if not self.is_running:
            return

        now = self.get_game_time()

        # Verificar si el juego ha terminado por tiempo
        if now >= self.max_game_duration:
            self._handle_game_timeout()
            return

        # chequeo periódico de nuevas ofertas
        if now - self._last_job_check >= self.JOB_CHECK_INTERVAL:
            self._last_job_check = now
            self._check_for_new_jobs(now)

    def _handle_game_timeout(self):
        """Maneja el fin del juego por tiempo"""
        self.is_running = False
        if self.player_state:
            goal = getattr(self.player_state, 'map_data', {}).get('goal', 3000)
            money = getattr(self.player_state, 'money', 0)
            if money >= goal:
                self.game_over("¡Victoria! Alcanzaste la meta de ingresos")
            else:
                self.game_over("Derrota: Tiempo agotado - No alcanzaste la meta")
        else:
            self.game_over("Derrota: Tiempo agotado")

    def _check_for_new_jobs(self, current_time: float):
        """Busca el siguiente job elegible y si existe lo muestra a player_manager."""
        if not self.job_manager or not self.player_manager:
            return

        try:
            job = self.job_manager.peek_next_eligible(current_time)
            if job and not getattr(job, "visible_pickup", False):
                # Verificar que el job no haya expirado
                if self.is_job_expired(job.raw):
                    print(f"[GAME_MANAGER] Job {job.id} ha expirado, marcando como rechazado")
                    self.job_manager.mark_rejected(job.id)
                    return

                # mostrar oferta usando player_manager.show_job_offer (si existe)
                if hasattr(self.player_manager, "show_job_offer"):
                    def on_accept(_):
                        self._accept_job(job.id)

                    def on_reject(_):
                        self.job_manager.mark_rejected(job.id)

                    # marcar visible antes de mostrar para evitar race conditions
                    job.visible_pickup = True
                    self.player_manager.show_job_offer(job.raw, on_accept, on_reject)
                    print(f"[GAME_MANAGER] oferta mostrada: {job.id}")
        except Exception as e:
            print(f"[GAME_MANAGER] error checking jobs: {e}")

    def _accept_job(self, job_id: str):
        """Aceptar via GameManager: marca, añade al inventario y registra en job_manager."""
        if not self.job_manager or not self.player_state:
            return False
        job = self.job_manager.get_job(job_id)
        if not job:
            print(f"[GAME_MANAGER] accept_job: job {job_id} no existe")
            return False

        # Verificar si el job ha expirado antes de aceptar
        if self.is_job_expired(job.raw):
            print(f"[GAME_MANAGER] accept_job: job {job_id} ha expirado")
            self.job_manager.mark_rejected(job_id)
            return False

        # comprobar inventario local
        inv = getattr(self.player_state, "inventory", None)
        if inv and not inv.can_add(job):
            print(f"[GAME_MANAGER] accept_job: no hay capacidad para {job_id}")
            # revertir visible flag para que vuelva a aparecer si corresponde
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
            # revertir aceptación/ marcar rechazado
            self.job_manager.mark_rejected(job_id)
            print(f"[GAME_MANAGER] accept_job: no se pudo añadir {job_id} al inventario (revertido)")
            return False

        # marcar flags visuales
        job.visible_pickup = True
        job.picked_up = False
        job.dropoff_visible = False
        job.completed = False

        print(f"[GAME_MANAGER] job {job_id} aceptado y añadido al inventario")
        return True

    def try_deliver_at(self, tile_x: int, tile_y: int):
        """Intentar completar una entrega en la celda actual. Retorna dict resumen o None."""
        if not self.player_state:
            return None

        inv = getattr(self.player_state, "inventory", None)
        if not inv:
            return None

        # recorrer inventario head -> tail
        node = getattr(inv.deque, "head", None)
        while node:
            job = node.val if hasattr(node, "val") else node
            try:
                if getattr(job, "picked_up", False) and not getattr(job, "completed", False):
                    raw = getattr(job, "raw", {}) or {}
                    drop = tuple(raw.get("dropoff", ()) or job.dropoff)
                    if drop == (tile_x, tile_y):
                        # Verificar si la entrega es a tiempo
                        current_time = self.get_game_time()
                        deadline = raw.get("deadline_timestamp")
                        on_time = True
                        time_bonus = 1.0

                        if deadline and current_time > deadline:
                            on_time = False
                            time_bonus = 0.5  # Penalización por entrega tardía
                            print(f"[DELIVERY] Entrega tardía para {job.id}")

                        # calcular pago con bonificación/penalización por tiempo
                        base = float(raw.get("payout", getattr(job, "payout", 0.0)))
                        pay_multiplier = getattr(self.player_state, "get_payment_multiplier", lambda: 1.0)()
                        pay = base * pay_multiplier * time_bonus

                        # aplicar dinero
                        try:
                            self.player_state.money += pay
                        except Exception:
                            pass

                        # marcar completado y remover
                        job.completed = True
                        try:
                            inv.remove(job.id)
                        except Exception:
                            # fallback: if remove fails, keep state but mark completed
                            pass

                        # aplicar reputación basada en puntualidad
                        rep_delta = 0
                        try:
                            if on_time:
                                rep_delta = self.player_state.update_reputation("delivery_on_time", {})
                                print(f"[REPUTATION] + {rep_delta} por entrega a tiempo")
                            else:
                                seconds_late = int(current_time - deadline)
                                rep_delta = self.player_state.update_reputation("delivery_late", {
                                    "seconds_late": seconds_late})
                                print(f"[REPUTATION] {rep_delta} por entrega tardía ({seconds_late}s)")
                        except Exception as e:
                            print(f"Error actualizando reputación: {e}")

                        result = {
                            "job_id": job.id,
                            "pay": pay,
                            "rep_delta": rep_delta,
                            "on_time": on_time
                        }
                        print(f"[GAME_MANAGER] Entregado {job.id} -> pay ${pay:.2f} (on_time: {on_time})")
                        return result
            except Exception:
                pass
            node = getattr(node, "next", None)
        return None

    # ... (resto de los métodos se mantienen igual: handle_player_movement, save_current_state, undo_last_action, game_over, get_active_jobs)
    def try_pickup_at(self, tile_x: int, tile_y: int) -> bool:
        """Intentar recoger un paquete en la celda actual. Retorna True si se recogió."""
        if not self.player_state:
            return False

        inv = getattr(self.player_state, "inventory", None)
        if not inv:
            return False

        # Buscar trabajos aceptados pero no recogidos
        for job in self.job_manager.get_active_jobs():
            if (getattr(job, "accepted", False) and
                    not getattr(job, "picked_up", False) and
                    not getattr(job, "completed", False)):

                # Verificar si estamos en la posición de pickup
                pickup_pos = tuple(job.pickup)
                if pickup_pos == (tile_x, tile_y):
                    # Marcar como recogido y mostrar dropoff
                    job.picked_up = True
                    job.dropoff_visible = True
                    print(f"[GAME_MANAGER] Paquete {job.id} recogido en {tile_x},{tile_y}")
                    return True

        return False

    def save_current_state(self):
        """Guarda el estado actual para deshacer."""
        if not self.undo_system or not self.player_state or not self.player_manager:
            return

        state_snapshot = self.undo_system.get_state_snapshot(
            self.player_state,
            self.player_state.inventory,
            self.player_state.weather_system,
            self.player_manager
        )
        self.undo_system.save_state(state_snapshot)

    def undo_last_action(self) -> bool:
        """Deshace la última acción."""
        if not self.undo_system or not self.undo_system.can_undo():
            return False

        try:
            previous_state = self.undo_system.undo()
            self.undo_system.restore_state(
                previous_state,
                self.player_state,
                self.player_state.inventory,
                self.player_state.weather_system,
                self.player_manager
            )
            print(f"[UNDO] Estado restaurado - Paso {self.undo_system.current_step}")
            return True
        except Exception as e:
            print(f"[UNDO] Error: {e}")
            return False

    def handle_player_movement(self, dx: int, dy: int):
        """Maneja el movimiento del jugador y guarda estado para undo."""
        # Guardar estado antes del movimiento
        self.save_current_state()

        # Lógica de movimiento existente...
        if self.player_manager:
            self.player_manager.move_by(dx, dy, self.game_map)