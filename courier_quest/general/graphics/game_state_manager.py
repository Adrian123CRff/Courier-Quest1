#game_state_manager.py
"""
Game State Manager - Handles game state initialization and management
"""

import time
from typing import Any


from ..game.game_manager import GameManager
from ..game.jobs_manager import JobManager


class GameStateManager:
    """Manages game state initialization, managers, and save/load operations."""

    def __init__(self, parent_view):
        self.parent = parent_view
        self.game_manager: Any = None
        self.job_manager: Any = None
        self.score_system: Any = None

    def initialize_game_systems(self):
        """Initialize all game systems and managers."""
        try:
            # Evitar inicializaciones duplicadas
            if not hasattr(self, 'game_manager') or self.game_manager is None:
                self.game_manager = GameManager()
            if not hasattr(self, 'job_manager') or self.job_manager is None:
                self.job_manager = JobManager()

            # garantizar inventario también aquí
            self.parent._ensure_inventory()

            # datos desde state
            if isinstance(self.parent.state, dict):
                map_data = self.parent.state.get("map_data") or self.parent.state.get("city_map", {})
                jobs_data = self.parent.state.get("jobs_data") or self.parent.state.get("orders", [])
                weather_data = self.parent.state.get("weather_data") or self.parent.state.get("weather_state", {})
            else:
                map_data = getattr(self.parent.state, "map_data", None) or getattr(self.parent.state, "city_map", {})
                jobs_data = getattr(self.parent.state, "jobs_data", None) or getattr(self.parent.state, "orders", [])
                weather_data = getattr(self.parent.state, "weather_data", None) or getattr(self.parent.state, "weather_state", {})

            try:
                self.game_manager.initialize_game(map_data, jobs_data, weather_data)
            except Exception:
                pass

            try:
                if self.game_manager:
                    self.game_manager.set_game_map(self.parent.game_map)
            except Exception:
                pass

            # reanudación: tiempo, clima, posición
            if self.parent._resume_mode:
                self._fast_forward_elapsed()
                try:
                    ws = self.parent.state.get("weather_state") if isinstance(self.parent.state, dict) else getattr(
                        self.parent.state, "weather_state", {}
                    )
                    if not ws:
                        ws = self.parent.state.get("weather_data") if isinstance(self.parent.state, dict) else getattr(
                            self.parent.state, "weather_data", {}
                        )
                    self.parent._resume_weather_state = ws or {}
                    if hasattr(self.parent.weather_markov, "apply_external_state"):
                        self.parent.weather_markov.apply_external_state(self.parent._resume_weather_state)
                except Exception as e:
                    print(f"[RESUME] No se pudo fijar clima: {e}")

                try:
                    # First try to load from 'player' dict (new format)
                    player_data = self.parent.state.get("player") if isinstance(self.parent.state, dict) else getattr(self.parent.state, "player", None)
                    if player_data and isinstance(player_data, dict):
                        px = player_data.get("cell_x")
                        py = player_data.get("cell_y")
                        if px is not None and py is not None:
                            self.parent.player.cell_x = int(px)
                            self.parent.player.cell_y = int(py)
                            self.parent.player.pixel_x, self.parent.player.pixel_y = self.parent.player.cell_to_pixel(self.parent.player.cell_x, self.parent.player.cell_y)
                            self.parent.player.target_pixel_x, self.parent.player.target_pixel_y = self.parent.player.pixel_x, self.parent.player.pixel_y
                            self.parent.player.moving = player_data.get("moving", False)
                            self.parent.player.target_surface_weight = player_data.get("target_surface_weight", 1.0)
                            self.parent.player.base_cells_per_sec = player_data.get("base_cells_per_sec", self.parent.player.base_cells_per_sec)
                    else:
                        # Fallback to old format
                        px = self.parent.state.get("player_x") if isinstance(self.parent.state, dict) else getattr(self.parent.state, "player_x", None)
                        py = self.parent.state.get("player_y") if isinstance(self.parent.state, dict) else getattr(self.parent.state, "player_y", None)
                        if px is not None and py is not None:
                            self.parent.player.cell_x = int(px)
                            self.parent.player.cell_y = int(py)
                            self.parent.player.pixel_x, self.parent.player.pixel_y = self.parent.player.cell_to_pixel(self.parent.player.cell_x, self.parent.player.cell_y)
                            self.parent.player.target_pixel_x, self.parent.player.target_pixel_y = self.parent.player.pixel_x, self.parent.player.pixel_y
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
            if isinstance(self.parent.state, dict):
                elapsed = self.parent.state.get("elapsed_seconds")
            else:
                elapsed = getattr(self.parent.state, "elapsed_seconds", None)
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
        """Set the game and job managers."""
        self.game_manager = game_manager
        self.job_manager = job_manager
        self.score_system = getattr(game_manager, 'score_system', None)
        if game_manager:
            try:
                game_manager.player_manager = self.parent.player
            except Exception:
                pass
        self._load_initial_jobs()

    def _load_initial_jobs(self):
        """Load initial jobs from save state."""
        # 1) leer lista del save
        if isinstance(self.parent.state, dict):
            orders = self.parent.state.get("orders") or self.parent.state.get("jobs_data", [])
        else:
            orders = getattr(self.parent.state, "orders", None) or getattr(self.parent.state, "jobs_data", [])
        orders = list(orders or [])

        self.parent.incoming_raw_jobs = []
        self.parent.rejected_raw_jobs = []
        self.parent.accepted_raw_jobs = []

        # 2) separar aceptados vs pendientes
        for r in orders:
            if r and r.get("accepted"):
                self.parent.accepted_raw_jobs.append(r)
            else:
                self.parent.incoming_raw_jobs.append(r)

        # 3) sembrar los aceptados usando coordenadas guardadas
        if self.job_manager:
            for raw in self.parent.accepted_raw_jobs:
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
                                setattr(job, "payout", self.parent._get_job_payout(job))
                        except Exception:
                            pass

                        job.accepted = bool(raw.get("accepted", True))
                        job.picked_up = bool(raw.get("picked_up", False))
                        job.completed = bool(raw.get("completed", False))

                        # si ya estaba completado en el save, NO volver a pagar
                        if job.completed:
                            self.parent._counted_deliveries.add(jid)

                        # si estaba recogido, añadir al inventario
                        inv = self.parent.state.get("inventory") if isinstance(self.parent.state, dict) else getattr(self.parent.state, "inventory", None)
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
        accepted_ids = {(r.get("id") or r.get("job_id")) for r in self.parent.accepted_raw_jobs}
        self.parent.incoming_raw_jobs = [r for r in self.parent.incoming_raw_jobs if (r.get("id") or r.get("job_id")) not in accepted_ids]
        print(f"[JOBS] Cargados {len(self.parent.incoming_raw_jobs)} pendientes, {len(self.parent.accepted_raw_jobs)} aceptados")

        # 5) Limpiar inventario: remover trabajos completados y recalcular peso
        try:
            inv = self.parent.state.get("inventory") if isinstance(self.parent.state, dict) else getattr(self.parent.state, "inventory", None)
            if inv and hasattr(inv, 'deque') and inv.deque:
                # Remover trabajos completados
                inv.deque = [job for job in inv.deque if not getattr(job, 'completed', False)]
                # Recalcular peso actual
                inv.current_weight = sum(float(getattr(job, 'weight', 0.0)) for job in inv.deque)
                print(f"[INVENTORY] Limpiado: {len(inv.deque)} items restantes, peso total {inv.current_weight:.1f}")
        except Exception as e:
            print(f"[LOAD] Error limpiando inventario: {e}")

    def _raw_job_id(self, raw: dict) -> str:
        """Get job ID from raw job data."""
        return raw.get("id") or raw.get("job_id") or raw.get("req") or str(raw)
