# courier_quest/general/ia/cpu_easy.py
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple, Any

Vec2I = Tuple[int, int]


# ============================ Config & State ============================

@dataclass
class CpuConfig:
    """Parámetros de comportamiento del CPU en modo fácil."""
    step_period_sec: float = 0.18          # Cada cuánto intenta moverse
    retarget_timeout_sec: float = 8.0      # Reasigna pedido si tarda demasiado
    random_repick_prob: float = 0.10       # Probabilidad de reroll “caprichoso”
    max_carry: int = 1                     # Capacidad de carga simple


@dataclass
class CpuState:
    """Estado interno del CPU."""
    grid_pos: Vec2I
    stamina: float
    reputation: float
    carrying: List[str] = field(default_factory=list)   # ids de pedidos
    current_job_id: Optional[str] = None
    time_since_last_step: float = 0.0
    time_since_job_pick: float = 0.0


# ============================ Adaptadores ============================

class JobsAPI:
    """
    Adaptador mínimo para interactuar con tu JobsManager real.
    Debes mapear estas funciones a tu implementación existente.
    """

    class _Job:
        def __init__(self, job_id: str) -> None:
            self.id = job_id

    def pick_random_available(self, rng: random.Random) -> Optional[str]:
        """Devuelve el id de un job disponible al azar o None."""
        raise NotImplementedError

    def get_pickups_at(self, cell: Vec2I) -> List["_Job"]:
        """Jobs que se pueden recoger en la celda específica."""
        raise NotImplementedError

    def is_dropoff_here(self, job_id: str, cell: Vec2I) -> bool:
        """True si el job se entrega en esta celda."""
        raise NotImplementedError

    def pickup(self, job_id: str) -> bool:
        """Intenta marcar el job como recogido por este jugador CPU."""
        raise NotImplementedError

    def dropoff(self, job_id: str) -> Optional[float]:
        """Intenta entregar el job. Devuelve payout si tuvo éxito."""
        raise NotImplementedError


class WorldAPI:
    """
    Adaptador mínimo para costos/beneficios del mundo (clima, reputación, etc.).
    En modo fácil, usamos costos fijos sencillos.
    """

    def base_move_cost(self) -> float:
        """Costo de stamina por paso (fijo en modo fácil)."""
        return 1.0

    def reputation_gain_on_delivery(self) -> float:
        """Ganancia de reputación por entrega."""
        return 1.0


# ============================ CPU Fácil ============================

class EasyCPUCourier:
    """
    IA nivel fácil para Courier Quest:
    - Elige un pedido disponible al azar.
    - Se mueve aleatoriamente por calles (evita celdas no caminables).
    - Entrega si por casualidad pasa por pickup/dropoff.
    - Ocasionalmente “se arrepiente” y rerollea pedido.
    """

    def __init__(
        self,
        is_walkable: Callable[[int, int], bool],
        jobs_api: JobsAPI,
        world_api: WorldAPI,
        rng: Optional[random.Random] = None,
        config: Optional[CpuConfig] = None,
        initial_grid_pos: Vec2I = (0, 0),
        initial_stamina: float = 100.0,
        initial_reputation: float = 0.0,
    ) -> None:
        """
        Args:
            is_walkable: función (x, y) -> bool que indica si una celda es transitable.
            jobs_api: adaptador para interactuar con los pedidos.
            world_api: adaptador para interactuar con el mundo (pickup/drop, costos, etc.).
            rng: generador aleatorio (inyectable para tests).
            config: configuración del comportamiento.
            initial_grid_pos: posición inicial en grilla.
        """
        self.is_walkable = is_walkable
        self.jobs = jobs_api
        self.world = world_api
        self.rng = rng or random.Random()
        self.cfg = config or CpuConfig()
        self.s = CpuState(
            grid_pos=initial_grid_pos,
            stamina=initial_stamina,
            reputation=initial_reputation,
        )

    # ——————————————— API pública ———————————————

    @property
    def grid_pos(self) -> Vec2I:
        return self.s.grid_pos

    @property
    def stamina(self) -> float:
        return self.s.stamina

    @property
    def reputation(self) -> float:
        return self.s.reputation

    def update(self, dt: float) -> None:
        """
        Se llama cada frame/tick. Maneja:
        - (re)selección de pedido
        - movimiento aleatorio
        - pickup / dropoff oportunista
        """
        # Timers
        self.s.time_since_last_step += dt
        self.s.time_since_job_pick += dt

        # 1) Asegurar que tenga un objetivo (pedido actual)
        self._ensure_job_target()

        # 2) Intentar movernos cada cierto período
        if self.s.time_since_last_step >= self.cfg.step_period_sec:
            self._random_step()
            self.s.time_since_last_step = 0.0

        # 3) Interacciones: pickup o dropoff si estamos encima
        self._opportunistic_actions()

    # ——————————————— Lógica interna ———————————————

    def _ensure_job_target(self) -> None:
        """Elige pedido aleatorio si no tiene, o rerollea por timeout/azar."""
        # Si carga algo, mantener objetivo (entregar lo que lleva)
        if self.s.carrying:
            return

        need_new = False

        if self.s.current_job_id is None:
            need_new = True
        else:
            # ¿Timeout o capricho de reroll?
            if self.s.time_since_job_pick >= self.cfg.retarget_timeout_sec:
                need_new = True
            elif self.rng.random() < self.cfg.random_repick_prob:
                need_new = True

        if need_new:
            job_id = self.jobs.pick_random_available(self.rng)
            if job_id is not None:
                self.s.current_job_id = job_id
                self.s.time_since_job_pick = 0.0

    def _random_step(self) -> None:
        """Da un paso aleatorio a una celda caminable vecina (4-neighbors)."""
        x, y = self.s.grid_pos
        neighbors: List[Vec2I] = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        walkable = [p for p in neighbors if self.is_walkable(p[0], p[1])]
        if not walkable:
            return  # encajonado; quedarse quieto

        next_pos = self.rng.choice(walkable)
        # Consumo básico de stamina (constante; en fácil ignoramos clima/superficie)
        stamina_cost = self.world.base_move_cost()
        if self.s.stamina >= stamina_cost:
            self.s.grid_pos = next_pos
            self.s.stamina -= stamina_cost

    def _opportunistic_actions(self) -> None:
        """
        Si está sobre una celda de pickup/drop que le sirve, ejecuta acción.
        Mantiene la simplicidad: un slot de carga.
        """
        cell = self.s.grid_pos

        # 1) Intentar PICKUP si no lleva nada:
        if not self.s.carrying:
            # si no tiene job, igual chance de levantar cualquier pedido de la celda
            job_id = self.s.current_job_id
            pickup_here = self.jobs.get_pickups_at(cell)

            # prioridad al job objetivo; si no, cualquiera disponible en la celda
            candidate = None
            if job_id and any(j.id == job_id for j in pickup_here):
                candidate = job_id
            elif pickup_here:
                candidate = pickup_here[0].id

            if candidate and len(self.s.carrying) < self.cfg.max_carry:
                ok = self.jobs.pickup(candidate)
                if ok:
                    self.s.carrying.append(candidate)
                    # Una vez recoge, “objetivo” implícito es entregar
                    # mantenemos current_job_id para intentar soltarlo luego

        # 2) Intentar DROPOFF si lleva algo:
        if self.s.carrying:
            to_drop = list(self.s.carrying)  # copiar por si modifica
            for jid in to_drop:
                if self.jobs.is_dropoff_here(jid, cell):
                    payout = self.jobs.dropoff(jid)
                    if payout is not None:
                        self.s.carrying.remove(jid)
                        self.s.reputation += self.world.reputation_gain_on_delivery()
                        # Si entregó su objetivo, liberar current_job_id
                        if self.s.current_job_id == jid:
                            self.s.current_job_id = None

    # ——————————————— Render opcional ———————————————

    def draw_debug(self, draw_fn: Callable[[Vec2I, str], None]) -> None:
        """
        Dibuja texto debug sobre la celda actual (si tu motor lo permite).
        Args:
            draw_fn: función (grid_pos, text) -> None para renderizar debug.
        """
        text = f"CPU(F): st={self.s.stamina:.0f} rep={self.s.reputation:.0f}"
        draw_fn(self.s.grid_pos, text)
