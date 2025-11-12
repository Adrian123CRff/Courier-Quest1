#jobs_logic.py
from __future__ import annotations

from typing import Any, Dict
import arcade


class JobsLogic:
    def __init__(self, view: Any) -> None:
        self.view = view

    # Drawing markers on the map for pickups and dropoffs
    def draw_job_markers(self) -> None:
        v = self.view
        if not v.job_manager:
            return
        try:
            for job in v.job_manager.all_jobs():
                if getattr(job, "accepted", False) and not getattr(job, "picked_up", False):
                    px_c, py_c = v._get_job_pickup_coords(job)
                    if px_c is not None and py_c is not None:
                        px, py = v._cell_to_pixel(int(px_c), int(py_c))
                        arcade.draw_circle_filled(px, py, v.TILE_SIZE * 0.4, arcade.color.GOLD)
                        arcade.draw_circle_outline(px, py, v.TILE_SIZE * 0.4, arcade.color.BLACK, 2)
                        job_label = getattr(job, "id", None) or (getattr(job, "raw", {}) or {}).get("id", "PICKUP")
                        from arcade import Text
                        Text(f"{job_label}", px - 18, py + 15, arcade.color.BLACK, 8).draw()

                if getattr(job, "picked_up", False) and not getattr(job, "completed", False):
                    dx_c, dy_c = v._get_job_dropoff_coords(job)
                    if dx_c is not None and dy_c is not None:
                        dx, dy = v._cell_to_pixel(int(dx_c), int(dy_c))
                        v._draw_centered_rect_filled(dx, dy, v.TILE_SIZE * 0.6, v.TILE_SIZE * 0.6, arcade.color.RED)
                        v._draw_centered_rect_outline(dx, dy, v.TILE_SIZE * 0.6, v.TILE_SIZE * 0.6, arcade.color.BLACK, 2)
                        drop_label = getattr(job, "id", None) or (getattr(job, "raw", {}) or {}).get("id", "DROPOFF")
                        from arcade import Text
                        Text(f"{drop_label}", dx - 25, dy + 15, arcade.color.WHITE, 8).draw()
        except Exception as e:
            print(f"[ERROR] Dibujando marcadores: {e}")

    # Money synchronization based on completed jobs
    def synchronize_money_with_completed_jobs(self) -> None:
        v = self.view
        if not v.job_manager:
            return
        try:
            for job in v.job_manager.all_jobs():
                if getattr(job, "completed", False):
                    jid = getattr(job, "id", None)
                    if jid and jid not in v._counted_deliveries:
                        payout = v._get_job_payout(job)
                        if payout > 0:
                            v._add_money(payout)
                        v._counted_deliveries.add(jid)
        except Exception as e:
            print(f"[MONEY] Error sincronizando entregas: {e}")

    def recompute_money_from_jobs(self) -> None:
        v = self.view
        if not v.job_manager:
            return
        try:
            computed = 0.0
            for job in v.job_manager.all_jobs():
                if getattr(job, "completed", False):
                    computed += v._get_job_payout(job)
            current = v._get_state_money()
            if computed > current:
                v._set_state_money(computed)
                print(f"[MONEY] Recompute -> total ${computed:.2f}")
        except Exception as e:
            print(f"[MONEY] Error recompute: {e}")

    def remove_job_from_inventory(self, job: Any) -> None:
        v = self.view
        if job is None:
            return
        inv = v.state.get("inventory") if isinstance(v.state, dict) else getattr(v.state, "inventory", None)
        if not inv:
            return

        cw_before = getattr(inv, "current_weight", None)
        removed = False
        try:
            job_id = getattr(job, "id", None)
            if hasattr(inv, "remove") and job_id:
                inv.remove(job_id)
                removed = True
            elif hasattr(inv, "deque"):
                for item in list(inv.deque):
                    if getattr(item, "id", None) == job_id:
                        inv.deque.remove(item)
                        removed = True
                        break
        except Exception as e:
            print(f"[INV] Error remove(): {e}")

        try:
            cw_after = getattr(inv, "current_weight", None)
            if cw_before is not None and cw_after is not None:
                wt = float(getattr(job, "weight", 0.0) or 0.0)
                if removed and wt > 0 and cw_after >= cw_before - 1e-6:
                    try:
                        setattr(inv, "current_weight", max(0.0, float(cw_before) - wt))
                    except Exception:
                        pass
        except Exception:
            pass

    def pickup_nearby(self) -> bool:
        v = self.view
        if not v.job_manager:
            return False

        px = int(v.player.cell_x)
        py = int(v.player.cell_y)
        picked_any = False
        try:
            for job in v.job_manager.all_jobs():
                if not getattr(job, "accepted", False):
                    continue
                if getattr(job, "picked_up", False) or getattr(job, "completed", False):
                    continue

                jpx, jpy = v._get_job_pickup_coords(job)
                if jpx is None or jpy is None:
                    continue

                if abs(int(jpx) - px) + abs(int(jpy) - py) <= 1:
                    job.picked_up = True
                    job.dropoff_visible = True
                    picked_any = True

                    inventory = v.state.get("inventory") if isinstance(v.state, dict) else getattr(v.state, "inventory", None)
                    if inventory:
                        try:
                            if hasattr(inventory, "add"):
                                inventory.add(job)
                            elif hasattr(inventory, "push"):
                                inventory.push(job)
                        except Exception as e:
                            print(f"[PICKUP] Error añadiendo al inventario: {e}")

                    print(f"[PICKUP] Paquete {getattr(job,'id','?')} recogido en {px},{py} (pickup en {jpx},{jpy})")

            return picked_any
        except Exception as e:
            print(f"[PICKUP] Error en pickup_nearby: {e}")
            return False

    def try_deliver_at_position(self, px: int, py: int) -> bool:
        v = self.view
        if not v.job_manager:
            return False
        delivered_any = False
        try:
            for job in v.job_manager.all_jobs():
                if not getattr(job, "accepted", False) or not getattr(job, "picked_up", False):
                    continue
                if getattr(job, "completed", False):
                    continue

                dx, dy = v._get_job_dropoff_coords(job)
                if dx is None or dy is None:
                    continue

                cond = (
                    abs(int(dx) - px) + abs(int(dy) - py) <= 1
                    if getattr(v, "DROPOFF_ADJACENT", False)
                    else (int(dx) == px and int(dy) == py)
                )
                if cond:
                    job.completed = True
                    delivered_any = True

                    self.remove_job_from_inventory(job)

                    payout = v._get_job_payout(job)

                    # ✅ CORREGIDO: Cálculo correcto de on_time según requerimientos
                    on_time = True
                    try:
                        if v.game_manager and hasattr(v.game_manager, "get_job_time_remaining"):
                            rem = v.game_manager.get_job_time_remaining(getattr(job, "raw", {}) or {})
                            # on_time = True si no hay deadline o si aún hay tiempo restante
                            on_time = (rem == float("inf")) or (rem >= 0)
                    except Exception:
                        pass

                    self.notify_delivery(job, payout, on_time)

                    print(f"[DELIVER] Paquete {getattr(job,'id','?')} entregado cerca/en {px},{py} +${payout}")

            return delivered_any
        except Exception as e:
            print(f"[DELIVER] Error en try_deliver_at_position: {e}")
            return False

    def notify_delivery(self, job: Any, payout: float, on_time: bool) -> None:
        v = self.view
        payout = v._parse_money(payout)
        if payout > 0:
            v._add_money(payout)

        jid = getattr(job, "id", None) if job is not None else None
        try:
            if jid:
                v._counted_deliveries.add(jid)
        except Exception:
            pass

        # ✅ CORREGIDO: Cálculo de tiempo real para determinar tipo de entrega
        try:
            if v.player_stats and hasattr(v.player_stats, "update_reputation"):
                base_rep = v.player_stats.reputation
                print(f"[REPUTATION] Base reputation: {base_rep}")

                # Inicializar variables para el cálculo
                seconds_late = 0
                early_percent = 0
                event_type = "delivery_on_time"

                if v.game_manager and job:
                    try:
                        # Obtener información de tiempo del trabajo
                        raw_data = getattr(job, "raw", {})
                        deadline_str = raw_data.get("deadline")

                        if deadline_str:
                            # Calcular tiempo restante usando GameManager
                            remaining = v.game_manager.get_job_time_remaining(raw_data)
                            print(f"[TIME] Job {jid}: remaining time = {remaining}s")

                            if remaining == float("inf"):
                                # Sin deadline - siempre a tiempo
                                event_type = "delivery_on_time"
                            elif remaining >= 0:
                                # A tiempo o temprano
                                # Calcular si es entrega temprana (≥20% del tiempo total)
                                total_time = v.game_manager.get_job_total_time(raw_data)
                                if total_time > 0:
                                    early_percent = (remaining / total_time) * 100
                                    if early_percent >= 20:
                                        event_type = "delivery_early"
                                        print(f"[TIME] Early delivery: {early_percent:.1f}% early")
                                    else:
                                        event_type = "delivery_on_time"
                                        print(f"[TIME] On-time delivery: {early_percent:.1f}% remaining")
                            else:
                                # Tarde
                                seconds_late = abs(remaining)
                                event_type = "delivery_late"
                                print(f"[TIME] Late delivery: {seconds_late:.1f}s late")

                    except Exception as e:
                        print(f"[TIME] Error calculando tiempo entrega: {e}")
                        # Fallback: usar el valor 'on_time' que viene del caller
                        event_type = "delivery_on_time" if on_time else "delivery_late"

                # Actualizar reputación con el evento correcto
                rep_delta = v.player_stats.update_reputation(event_type, {
                    "seconds_late": seconds_late,
                    "early_percent": early_percent
                })

                print(f"[REPUTATION] Event: {event_type} -> {rep_delta:+d} points")
                print(f"[REPUTATION] New reputation: {v.player_stats.reputation}")

                # Aplicar multiplicador de pago por reputación alta
                payment_multiplier = v.player_stats.get_payment_multiplier()
                if payment_multiplier > 1.0:
                    bonus_payout = payout * (payment_multiplier - 1.0)
                    v._add_money(bonus_payout)
                    print(f"[MONEY] Reputation bonus: +${bonus_payout:.2f}")

                print(
                    f"[MONEY] Total payout: ${payout:.2f} (base) + ${bonus_payout if payment_multiplier > 1.0 else 0:.2f} (bonus)")

        except Exception as e:
            print(f"[REPUTATION] Error actualizando reputación: {e}")
            # Fallback al sistema simple si hay error
            try:
                rep = getattr(v.player_stats, "reputation", 70)
                rep += 3 if on_time else -2
                setattr(v.player_stats, "reputation", max(0, min(100, rep)))
            except Exception:
                pass

    # Right panel: list of active jobs with status
    def draw_active_jobs_panel(self) -> None:
        v = self.view
        v.jobs_title.draw()
        if v.job_manager and v.game_manager:
            try:
                active_jobs = [j for j in v.job_manager.all_jobs() if getattr(j, "accepted", False) and not getattr(j, "completed", False)]
                jobs_info = []
                for job in active_jobs[:8]:
                    status = "✓" if getattr(job, "picked_up", False) else "📦"
                    job_id = getattr(job, "id", "Unknown")
                    payout = v._get_job_payout(job)
                    job_text = f"- {job_id} {status}"
                    job_text += " → 🎯" if getattr(job, "picked_up", False) else f" (${payout})"
                    jobs_info.append(job_text)
                if not jobs_info:
                    jobs_info = ["- No hay pedidos activos"]
                    try:
                        available = v.job_manager.get_available_jobs(v.game_manager.get_game_time())
                    except Exception:
                        available = []
                    if available:
                        jobs_info.append(f"- {len(available)} disponibles")
                v.jobs_text.text = "\n".join(jobs_info)
            except Exception as e:
                v.jobs_text.text = f"- Error: {str(e)[:30]}..."
        else:
            v.jobs_text.text = "- Sistemas cargando..."
        v.jobs_text.draw()


