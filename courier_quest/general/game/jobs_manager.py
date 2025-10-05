# jobs_manager.py - SISTEMA CORREGIDO
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
        return f"Job({self.id}, pickup:{self.pickup}, dropoff:{self.dropoff}, release:{self.release_time}s, payout:${self.payout})"


class JobManager:
    """
    Sistema de gestión de trabajos con prioridad y control de release_time.
    """

    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._heap: List[Tuple[int, float, int, str]] = []  # (-priority, release_time, counter, job_id)
        self._counter = itertools.count()
        self._accepted_ids = set()
        self._rejected_ids = set()
        print(f"[JOB_MANAGER] ✅ Sistema inicializado")

    def _safe_tuple_xy(self, maybe_seq) -> Tuple[int, int]:
        """Convierte [x,y] o (x,y) o 'x,y' a tupla de ints; fallback (0,0)."""
        try:
            if maybe_seq is None:
                return (0, 0)
            if isinstance(maybe_seq, (list, tuple)) and len(maybe_seq) >= 2:
                return (int(maybe_seq[0]), int(maybe_seq[1]))
            # soportar strings "x,y"
            if isinstance(maybe_seq, str) and ',' in maybe_seq:
                a, b = maybe_seq.split(',', 1)
                return (int(a.strip()), int(b.strip()))
            # si es un único número, devolverlo en x y 0 en y
            if isinstance(maybe_seq, (int, float)):
                return (int(maybe_seq), 0)
        except Exception:
            pass
        return (0, 0)

    def add_job_from_raw(self, raw: Dict[str, Any], pickup_override: Tuple[int, int] = None) -> Optional[Job]:
        """
        Crea/añade un Job desde el JSON 'raw'.
        - Si pickup_override es None -> usa pickup del JSON.
        - Si pickup_override no es None -> usa explícitamente esa posición (USE CON CUIDADO).
        Retorna el Job (existente o recién creado) o None en error.
        """
        try:
            jid = str(raw.get("id") or f"job_{next(_counter)}")

            # Parsear pickup/dropoff de forma robusta
            raw_pickup = raw.get("pickup")
            raw_dropoff = raw.get("dropoff")
            parsed_pickup = self._safe_tuple_xy(raw_pickup)
            parsed_dropoff = self._safe_tuple_xy(raw_dropoff)

            # Preferir override sólo si viene explícitamente (None = usar raw)
            if pickup_override is not None:
                parsed_pickup = (int(pickup_override[0]), int(pickup_override[1]))

            priority = int(raw.get("priority", 0) or 0)
            weight = float(raw.get("weight", raw.get("peso", 1.0) or 1.0))
            payout = float(raw.get("payout", raw.get("reward", 0.0) or 0.0))
            release_time = float(raw.get("release_time", 0.0) or 0.0)

            # Si ya existe el job, actualizar su raw y campos mutables
            if jid in self._jobs:
                job = self._jobs[jid]
                job.raw = raw
                job.pickup = parsed_pickup
                job.dropoff = parsed_dropoff
                job.priority = priority
                job.weight = weight
                job.payout = payout
                job.release_time = release_time
                return job

            job = Job(
                id=jid,
                raw=raw,
                pickup=parsed_pickup,
                dropoff=parsed_dropoff,
                priority=priority,
                weight=weight,
                payout=payout,
                release_time=release_time
            )

            self._jobs[jid] = job
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

    def peek_next_eligible(self, now: float = 0.0) -> Optional[Job]:
        """Encuentra el siguiente trabajo elegible (sin quitarlo del heap) respetando release_time."""
        temp = []
        result = None
        try:
            while self._heap:
                neg_prio, rel_time, counter, jid = heapq.heappop(self._heap)
                job = self._jobs.get(jid)
                # descartar jobs inválidos
                if job is None or job.accepted or job.rejected or job.completed:
                    continue
                temp.append((neg_prio, rel_time, counter, jid))
                # eligibilidad: release_time <= now y no visible aún
                if rel_time <= now and not job.visible_pickup:
                    result = job
                    break
            # reinserto
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
        """Devuelve lista de jobs disponibles en este instante (respetando release_time)."""
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

    def mark_accepted(self, job_id: str) -> bool:
        return self.accept_job(job_id)

    def mark_rejected(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job:
            job.rejected = True
            self._rejected_ids.add(job_id)
            return True
        return False

    def get_active_jobs(self) -> List[Job]:
        return [job for job in self._jobs.values() if job.accepted and not job.completed]
