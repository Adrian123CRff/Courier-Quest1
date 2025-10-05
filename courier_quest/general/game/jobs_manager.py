# jobs_manager.py - SISTEMA COMPLETO Y ROBUSTO
import heapq
import itertools
from dataclasses import dataclass
from typing import Dict, Optional, List, Any, Tuple

_counter = itertools.count()


@dataclass
class Job:
    id: str
    raw: Dict[str, Any]
    pickup: Tuple[int, int]
    dropoff: Tuple[int, int]
    priority: int = 0
    weight: float = 1.0
    payout: float = 0.0
    release_time: float = 0.0

    # Estados del trabajo
    accepted: bool = False
    rejected: bool = False
    picked_up: bool = False
    completed: bool = False
    visible_pickup: bool = False
    dropoff_visible: bool = False

    def __str__(self):
        return f"Job({self.id}, release:{self.release_time}s, payout:${self.payout})"


class JobManager:
    """
    Sistema completo de gestión de trabajos con prioridades
    """

    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._heap: List[Tuple[int, float, int, str]] = []  # (-priority, release_time, counter, job_id)
        self._counter = itertools.count()
        self._accepted_ids = set()
        self._rejected_ids = set()
        print(f"[JOB_MANAGER] ✅ Sistema inicializado")

    def add_job_from_raw(self, raw: Dict[str, Any], pickup_override: Tuple[int, int] = None) -> Optional[Job]:
        """Añade un trabajo desde datos JSON.
        pickup_override: si se proporciona, sobrescribe la posición de pickup
        en el Job creado (útil cuando se genera la oferta en la posición actual).
        """
        try:
            jid = str(raw.get("id") or f"job_{next(self._counter)}")

            pickup = tuple(raw.get("pickup", (0.0)))
            dropoff = tuple(raw.get("dropoff", (0.0)))
            priority = int(raw.get("priority", 0))
            weight = float(raw.get("weight", 1.0))
            payout = float(raw.get("payout", 0.0))
            release_time = float(raw.get("release_time", 0.0))
            job = Job(
                id=jid, raw=raw, pickup=pickup, dropoff=dropoff,
                priority=priority, weight=weight, payout=payout,
                release_time=release_time
            )

            if jid in self._jobs:
                job = self._jobs[jid]
                job.raw = raw
                # si se da override, actualizar la pickup en el job ya existente
                if pickup_override is not None:
                    job.pickup = tuple(pickup_override)
                return job

            # pickup/dropoff: preferir override
            pickup = tuple(pickup_override) if pickup_override is not None else tuple(raw.get("pickup", (0, 0)))
            dropoff = tuple(raw.get("dropoff", (0, 0)))
            priority = int(raw.get("priority", 0))
            weight = float(raw.get("weight", raw.get("peso", 1.0)))
            payout = float(raw.get("payout", raw.get("reward", 0.0)))
            release_time = float(raw.get("release_time", 0.0))

            job = Job(
                id=jid, raw=raw, pickup=pickup, dropoff=dropoff,
                priority=priority, weight=weight, payout=payout,
                release_time=release_time
            )
            self._jobs[jid] = job

            # Añadir al heap de prioridades
            counter = next(self._counter)
            heapq.heappush(self._heap, (-priority, release_time, counter, jid))
            print(f"[JOB_MANAGER] ✅ Job añadido: {job}")
            return job

        except Exception as e:
            print(f"[JOB_MANAGER] ❌ Error añadiendo job: {e}")
            return None

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def all_jobs(self) -> List[Job]:
        return list(self._jobs.values())

        # jobs_manager.py - MODIFICAR peek_next_eligible para usar release_time correctamente

    def peek_next_eligible(self, now: float = 0.0) -> Optional[Job]:
        """Encuentra el próximo trabajo elegible sin removerlo del heap, respetando release_time"""
        temp = []
        result = None

        try:
            while self._heap:
                neg_prio, rel_time, counter, jid = heapq.heappop(self._heap)
                job = self._jobs.get(jid)

                # Filtrar jobs inválidos (no los reinsertamos)
                if job is None or job.accepted or job.rejected or job.completed:
                    continue

                # Guardar temporalmente para reinsertar más tarde
                temp.append((neg_prio, rel_time, counter, jid))

                # Verificar si es elegible por tiempo y no ha sido mostrado
                # release_time está en segundos desde el inicio del mapa
                if rel_time <= now and not job.visible_pickup:
                    result = job
                    break

            # Reinsertar todos los jobs temporales
            for entry in temp:
                heapq.heappush(self._heap, entry)

        except Exception as e:
            print(f"[JOB_MANAGER] ❌ Error en peek_next_eligible: {e}")
            for entry in temp:
                try:
                    heapq.heappush(self._heap, entry)
                except Exception:
                    pass

        return result

    def get_available_jobs(self, now: float = 0.0) -> List[Job]:
        """Obtiene todos los trabajos disponibles"""
        available = []
        temp = []

        try:
            while self._heap:
                neg_prio, rel_time, counter, jid = heapq.heappop(self._heap)
                job = self._jobs.get(jid)
                temp.append((neg_prio, rel_time, counter, jid))

                if job and not job.accepted and not job.rejected and not job.completed and rel_time <= now:
                    available.append(job)

            for entry in temp:
                heapq.heappush(self._heap, entry)

        except Exception as e:
            print(f"[JOB_MANAGER] ❌ Error en get_available_jobs: {e}")
            for entry in temp:
                try:
                    heapq.heappush(self._heap, entry)
                except Exception:
                    pass

        return available

    def accept_job(self, job_id: str) -> bool:
        """Acepta un trabajo (API pública)."""
        job = self._jobs.get(job_id)
        if not job:
            print(f"[JOB_MANAGER] ❌ Job {job_id} no encontrado")
            return False

        if job.accepted:
            return True

        if job.rejected or job.completed:
            return False

        job.accepted = True
        self._accepted_ids.add(job_id)
        return True

    # kept alias for compatibility
    def mark_accepted(self, job_id: str) -> bool:
        return self.accept_job(job_id)

    def mark_rejected(self, job_id: str) -> bool:
        """Rechaza un trabajo"""
        job = self._jobs.get(job_id)
        if job:
            job.rejected = True
            self._rejected_ids.add(job_id)
            return True
        return False

    def get_active_jobs(self) -> List[Job]:
        """Obtiene trabajos activos"""
        return [job for job in self._jobs.values() if job.accepted and not job.completed]
