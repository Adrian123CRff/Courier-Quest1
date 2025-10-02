# jobs_manager.py
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

    # runtime flags:
    accepted: bool = False
    rejected: bool = False
    picked_up: bool = False
    completed: bool = False
    visible_pickup: bool = False
    dropoff_visible: bool = False


class JobManager:
    """
    JobManager:
     - mantiene dict id->Job
     - mantiene un heap para decidir next notification: key = (-priority, release_time, counter, job_id)
     - peek_next_eligible(now) devuelve la primera job elegible sin quitarla del heap.
    """

    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._heap: List[Tuple[int, float, int, str]] = []  # (-priority, release_time, counter, job_id)
        self._counter = _counter
        self._accepted_ids = set()
        self._rejected_ids = set()

    def add_job_from_raw(self, raw: Dict[str, Any]):
        jid = str(raw.get("id") or raw.get("job_id") or raw.get("jid") or f"job_{next(self._counter)}")
        if jid in self._jobs:
            # actualizar contenido en caso de re-envío
            job = self._jobs[jid]
            job.raw = raw
            # actualizar campos relevantes si quieres
            job.priority = int(raw.get("priority", job.priority))
            job.weight = float(raw.get("weight", raw.get("peso", job.weight)))
            job.payout = float(raw.get("payout", raw.get("reward", job.payout)))
            job.release_time = float(raw.get("release_time", job.release_time))
            return job

        pickup = tuple(raw.get("pickup", (0, 0)))
        dropoff = tuple(raw.get("dropoff", (0, 0)))
        priority = int(raw.get("priority", 0))
        weight = float(raw.get("weight", raw.get("peso", 1.0)))
        payout = float(raw.get("payout", raw.get("reward", 0.0)))
        release_time = float(raw.get("release_time", 0.0))

        job = Job(id=jid, raw=raw, pickup=pickup, dropoff=dropoff,
                  priority=priority, weight=weight, payout=payout,
                  release_time=release_time)
        self._jobs[jid] = job

        # push to heap
        counter = next(self._counter)
        heapq.heappush(self._heap, (-priority, release_time, counter, jid))
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def all_jobs(self) -> List[Job]:
        return list(self._jobs.values())

    def peek_next_eligible(self, now: float):
        """
        Devuelve el primer job elegible (release_time <= now) sin quitarlo permanentemente del heap.
        Reinserta todo lo extraído para no mutar la estructura.
        """
        if not self._heap:
            return None

        temp = []
        candidate = None

        try:
            while self._heap:
                neg_prio, rel_time, counter, jid = heapq.heappop(self._heap)
                job = self._jobs.get(jid)

                # Filtrar trabajos no válidos (no existen, ya aceptados, rechazados o completados)
                if job is None or job.accepted or job.rejected or job.completed:
                    continue

                # Si el trabajo es elegible por tiempo, lo seleccionamos como candidato
                if rel_time <= now:
                    candidate = job
                    # Guardamos este trabajo en temp para reinsertarlo después
                    temp.append((neg_prio, rel_time, counter, jid))
                    break

                # Si no es elegible, lo guardamos para reinsertarlo
                temp.append((neg_prio, rel_time, counter, jid))
        finally:
            # Reinsertar todo lo extraído para no mutar el heap
            for entry in temp:
                heapq.heappush(self._heap, entry)

        return candidate

    def get_next_notification(self, now: float = 0.0) -> Optional[Job]:
        """Conveniencia: alias para peek_next_eligible."""
        return self.peek_next_eligible(now)

    def accept_job(self, job_id: str) -> bool:
        """Marca un trabajo como aceptado."""
        job = self.get_job(job_id)
        if not job or job.accepted or job.rejected or job.completed:
            return False

        job.accepted = True
        self._accepted_ids.add(job_id)
        return True

    def reject_job(self, job_id: str) -> bool:
        """Marca un trabajo como rechazado."""
        job = self.get_job(job_id)
        if not job or job.accepted or job.rejected or job.completed:
            return False

        job.rejected = True
        self._rejected_ids.add(job_id)
        return True

    def mark_job_picked_up(self, job_id: str) -> bool:
        """Marca un trabajo como recogido."""
        job = self.get_job(job_id)
        if not job or not job.accepted or job.rejected or job.completed:
            return False

        job.picked_up = True
        job.dropoff_visible = True
        return True

    def complete_job(self, job_id: str) -> bool:
        """Marca un trabajo como completado."""
        job = self.get_job(job_id)
        if not job or not job.accepted or job.rejected or job.completed or not job.picked_up:
            return False

        job.completed = True
        return True

    def get_active_jobs(self) -> List[Job]:
        """Retorna todos los trabajos activos (aceptados pero no completados)."""
        return [job for job in self._jobs.values()
                if job.accepted and not job.completed and not job.rejected]

    def get_completed_jobs(self) -> List[Job]:
        """Retorna todos los trabajos completados."""
        return [job for job in self._jobs.values() if job.completed]

    def get_available_jobs(self, now: float = 0.0) -> List[Job]:
        """
        Obtiene los trabajos disponibles en el tiempo actual.
        """
        # Crear una lista temporal para ordenar por prioridad
        available_jobs = []

        for job in self._jobs.values():
            # Verificar si el trabajo está disponible
            if (job.release_time <= now and
                    not job.accepted and
                    not job.rejected and
                    not job.completed):
                available_jobs.append(job)

        # Ordenar por prioridad (mayor primero)
        available_jobs.sort(key=lambda j: (-j.priority, j.release_time))

        return available_jobs

    # Método obsoleto - usar accept_job en su lugar
    def mark_accepted(self, job_id: str) -> bool:
        """Alias obsoleto para accept_job."""
        return self.accept_job(job_id)

    # Método obsoleto - usar reject_job en su lugar
    def mark_rejected(self, job_id: str) -> bool:
        """Alias obsoleto para reject_job."""
        return self.reject_job(job_id)

    def remove_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            del self._jobs[job_id]
            # note: heap entries remain until popped; pop logic ignores absent ids
            self._accepted_ids.discard(job_id)
            self._rejected_ids.discard(job_id)
            return True
        return False

    def reinject_rejected(self):
        """
        Reinyecta jobs rechazados (si quieres darles otra oportunidad).
        Convención: reinsertarlos con release_time = now + small_delay.
        """
        import time
        now = time.time()
        to_reinject = list(self._rejected_ids)
        self._rejected_ids.clear()
        for jid in to_reinject:
            job = self._jobs.get(jid)
            if not job:
                continue
            job.rejected = False
            counter = next(self._counter)
            heapq.heappush(self._heap, (-job.priority, now + 1.0, counter, jid))

    def peek_next(self):
        """
        Returns the next job and its priority, or None if no jobs.
        """
        if not self._jobs:
            return None
        # If you want highest priority, use max(..., key=...) instead
        next_job = min(self._jobs.values(), key=lambda job: getattr(job, "priority", 0))
        priority = getattr(next_job, "priority", None)
        return next_job, priority

    def accepted_unpicked_weight(self):
        """
        Returns the total weight of jobs that are accepted but not yet picked up.
        """
        total = 0.0
        for job in self._jobs.values():
            if getattr(job, "accepted", False) and not getattr(job, "picked_up", False):
                total += float(getattr(job, "weight", 1.0))
        return total