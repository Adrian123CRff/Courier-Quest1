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
    - Soporta release_time como offset (segundos desde game_start) o epoch.
    - Si se detecta epoch y GameManager ha registrado _game_start_epoch, se convierte a offset.
    """

    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._heap: List[Tuple[int, float, int, str]] = []  # (-priority, release_time, counter, job_id)
        self._counter = itertools.count()
        self._accepted_ids = set()
        self._rejected_ids = set()
        # Si GameManager lo desea puede asignar aquí el epoch de inicio:
        # ej: job_manager._game_start_epoch = game_manager.game_start_time
        self._game_start_epoch: Optional[float] = None
        print(f"[JOB_MANAGER] ✅ Sistema inicializado")

    def add_job_from_raw(self, raw: Dict[str, Any], pickup_override: Tuple[int, int] = None) -> Optional[Job]:
        """Añade un trabajo desde datos JSON.
        pickup_override: si se proporciona, sobrescribe la posición depickup
        en el Job creado (útil cuando se genera la oferta en la posición actual).
        """
        try:
            jid = str(raw.get("id") or raw.get("job_id") or raw.get("jid") or f"job_{next(self._counter)}")

            if jid in self._jobs:
                job = self._jobs[jid]
                job.raw = raw
                if pickup_override is not None:
                    job.pickup = tuple(pickup_override)
                print(f"[JOB_MANAGER] (update) Job actualizado: {job}")
                return job

            # pickup/dropoff: preferir override. Evitar tuple(None).
            pickup_val = pickup_override if pickup_override is not None else (raw.get("pickup") or (0, 0))
            try:
                pickup = tuple(pickup_val)
            except Exception:
                pickup = (0, 0)

            dropoff_val = raw.get("dropoff") or (0, 0)
            try:
                dropoff = tuple(dropoff_val)
            except Exception:
                dropoff = (0, 0)

            # priority / weight / payout robustos frente a None/'' etc.
            try:
                priority = int(raw.get("priority") or 0)
            except Exception:
                priority = 0

            try:
                weight = float(raw.get("weight") or raw.get("peso") or 1.0)
            except Exception:
                weight = 1.0

            try:
                payout = float(raw.get("payout") or raw.get("reward") or 0.0)
            except Exception:
                payout = 0.0

            # release_time: puede venir como offset o epoch (>=1e9)
            raw_rel = raw.get("release_time", 0.0) or 0.0
            try:
                release_time = float(raw_rel)
            except Exception:
                release_time = 0.0

            # Normalizar release_time si viene en epoch y conocemos game_start_epoch
            if release_time > 1e9:
                if self._game_start_epoch is not None:   # distinguir 0.0 válido de None
                    try:
                        release_time = max(0.0, release_time - float(self._game_start_epoch))
                        print(f"[JOB_MANAGER] Converted epoch release_time -> offset for job {jid}: {release_time}s")
                    except Exception:
                        release_time = 0.0
                else:
                    print(f"[JOB_MANAGER] Detected epoch timestamp for job {jid} but no game_start_epoch set. Marking release_time=0 (immediate).")
                    release_time = 0.0

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

    def peek_next_eligible(self, now: float = 0.0) -> Optional[Job]:
        """Encuentra el próximo trabajo elegible sin removerlo del heap"""
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
                # Nota: rel_time puede ser float (offset). Aseguramos fallback si es None.
                try:
                    rel_time_cmp = float(rel_time)
                except Exception:
                    rel_time_cmp = 0.0

                if rel_time_cmp <= now and not job.visible_pickup:
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

                try:
                    rel_time_cmp = float(rel_time)
                except Exception:
                    rel_time_cmp = 0.0

                if job and not job.accepted and not job.rejected and not job.completed and rel_time_cmp <= now:
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
        print(f"[JOB_MANAGER] ✅ Job {job_id} marcado como aceptado")
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
            print(f"[JOB_MANAGER] ❌ Job {job_id} marcado como rechazado")
            return True
        return False

    def get_active_jobs(self) -> List[Job]:
        """Obtiene trabajos activos"""
        return [job for job in self._jobs.values() if job.accepted and not job.completed]
