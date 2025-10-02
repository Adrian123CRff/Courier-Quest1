# job_flow.py
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

# Comentar imports problemáticos
# from run_api.save_manager import save_game
# from game.jobs_manager import JobManager
# from game.player_state import PlayerState

# Helper: convierte deadline (ISO str o numeric) a epoch seconds
def resolve_deadline_epoch(job_raw: Dict[str, Any], player_state) -> float:
    dl = job_raw.get("deadline")
    if dl is None:
        # fallback: if numeric release_time+some default window
        release = float(job_raw.get("release_time", 0))
        return getattr(player_state, "start_time_epoch", time.time()) + release + 300  # +5min as fallback
    if isinstance(dl, (int, float)):
        # If numeric, interpret as offset seconds from game start
        return getattr(player_state, "start_time_epoch", time.time()) + float(dl)
    # assume ISO string
    try:
        # fromisoformat accepts "YYYY-MM-DDTHH:MM:SS"
        dt = datetime.fromisoformat(dl)
        # if no timezone, assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        # fallback: now + 300s
        return time.time() + 300

# Mostramos oferta si es elegible y no se mostró antes
def show_offer_if_eligible(job_manager, player_state, notification_manager, now: float):
    """
    Llama a notification_manager.show_job_offer(...) cuando exista un job eligible (release_time <= now)
    y que no haya sido aceptado o rechazado.
    """
    job = job_manager.peek_next_eligible(now)
    if not job:
        return None
    # evitar mostrarla si ya la mostramos (flag visible_pickup)
    if job.visible_pickup:
        return None
    # política: mostrar cuando el job sea elegible (release_time <= now)
    job.visible_pickup = True

    def on_accept(_):
        accept_job_flow(job_manager, player_state, job.id)

    def on_reject(_):
        job_manager.mark_rejected(job.id)
        # opcional: persistir
        # save_game(player_state_to_gamestate(player_state), "slot1.sav")

    notification_manager.show_job_offer(job.raw, on_accept, on_reject)
    return job

def player_state_to_gamestate(player_state):
    """Versión simplificada para evitar dependencias"""
    return {
        "player": {
            "money": getattr(player_state, "money", 0),
            "stamina": getattr(player_state, "stamina", 100),
            "reputation": getattr(player_state, "reputation", 70)
        },
        "inventory": [
            job.id for job in getattr(player_state.inventory, "get_all_jobs", lambda: [])()
        ],
        "weather_state": getattr(player_state, "weather_data", {}),
        "map_data": getattr(player_state, "map_data", {})
    }

# Flujo de aceptación de job
def accept_job_flow(job_manager, player_state, job_id: str) -> bool:
    job = job_manager.get_job(job_id)
    if not job:
        return False

    # 1) comprobar peso
    if not player_state.inventory.can_add(job):
        print(f"[JOB_FLOW] No puedes aceptar {job_id}: sobrepasas peso máximo.")
        return False

    # 2) marcar accepted
    ok = job_manager.mark_accepted(job_id)
    if not ok:
        print(f"[JOB_FLOW] mark_accepted devolvió False para {job_id}")
        return False

    # 3) añadir a inventario
    added = player_state.inventory.add(job)
    if not added:
        # revertir accepted
        job_manager.mark_rejected(job_id)
        print(f"[JOB_FLOW] No se pudo añadir al inventario: revertiendo aceptación {job_id}")
        return False

    # persistir partida
    # save_game(player_state_to_gamestate(player_state), "slot1.sav")
    return True

# Llamar desde el handler de movimiento / on_enter_tile
def on_player_enter_tile(_, player_state, tile_x: int, tile_y: int):
    """
    Si el jugador entra en una celda que contiene pickup de un job aceptado -> marcar picked_up
    """
    # revisa inventory jobs (aceptados, no picked_up) cuyo pickup coincide con la tile
    node = player_state.inventory.deque.head
    while node:
        job = node.val
        raw = getattr(job, "raw", job.raw if hasattr(job, "raw") else job)
        if getattr(job, "accepted", False) and not getattr(job, "picked_up", False):
            pickup = tuple(raw.get("pickup", ()))
            if pickup == (tile_x, tile_y):
                job.picked_up = True
                job.pickup_time_epoch = time.time()
                print(f"[JOB_FLOW] Job {job.id} recogido en {pickup}")
                # opcional: persistir
                # save_game(player_state_to_gamestate(player_state), "slot1.sav")
                # solo recoger uno por tile pass
                return True
        node = node.next
    return False

# Intentar entregar en tile actual
def try_deliver_at(_, player_state, tile_x: int, tile_y: int) -> Optional[Dict[str, Any]]:
    """
    Busca en inventario jobs aceptados y picked_up cuyo dropoff coincide con tile.
    Si encuentra uno, lo completa: calcula reputación y pago según el PDF.
    Devuelve dict con resumen si se entregó algo, o None.
    """
    node = player_state.inventory.deque.head
    while node:
        job = node.val
        raw = getattr(job, "raw", job.raw if hasattr(job, "raw") else job)
        if getattr(job, "picked_up", False) and not getattr(job, "completed", False):
            dropoff = tuple(raw.get("dropoff", ()))
            if dropoff == (tile_x, tile_y):
                # calcular temporalidad relativo al deadline
                deadline_epoch = resolve_deadline_epoch(raw, player_state)
                delivery_epoch = time.time()
                seconds_late = int(delivery_epoch - deadline_epoch)

                # determinar tipo de entrega y datos
                if seconds_late <= 0:
                    # on-time or early
                    # calcular ventana = deadline - release_time
                    release_offset = float(raw.get("release_time", 0.0))
                    release_epoch = getattr(player_state, "start_time_epoch", time.time()) + release_offset
                    window = max(1.0, deadline_epoch - release_epoch)
                    early_percent = ((deadline_epoch - delivery_epoch) / window) * 100
                    if early_percent >= 20:
                        event = "delivery_early"
                        data = {"early_percent": early_percent}
                    else:
                        event = "delivery_on_time"
                        data = {}
                else:
                    event = "delivery_late"
                    data = {"seconds_late": seconds_late}

                # aplicar reputación usando tu método
                rep_delta = player_state.update_reputation(event, data)

                # pago
                base = float(raw.get("payout", 0.0))
                pay = base * player_state.get_payment_multiplier()
                player_state.money += pay

                # marcar completado y remover del inventario
                job.completed = True
                # llamar inventory.remove con job.id
                player_state.inventory.remove(job.id)

                # persistir
                # save_game(player_state_to_gamestate(player_state), "slot1.sav")

                summary = {
                    "job_id": job.id,
                    "event": event,
                    "rep_delta": rep_delta,
                    "pay": pay,
                    "delivery_epoch": delivery_epoch
                }
                print(f"[JOB_FLOW] Entregado {job.id}: {summary}")
                return summary
        node = node.next
    return None

# Eliminar métodos duplicados accept_job y reject_job