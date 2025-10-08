from __future__ import annotations

from typing import Any
import arcade


class NotificationManager:
    def __init__(self, view: Any) -> None:
        self.view = view

    # Timers and spawning logic
    def update_timers(self, dt: float) -> None:
        v = self.view
        if v.job_notification_active:
            v.job_notification_timer -= dt
            if v.job_notification_timer <= 0:
                self.reject_current()

        if v.next_spawn_timer > 0.0:
            v.next_spawn_timer -= dt

        if not v.job_notification_active:
            self.maybe_start_notification()

    def maybe_start_notification(self) -> None:
        v = self.view
        if v.job_notification_active or v.next_spawn_timer > 0.0:
            return
        v.incoming_raw_jobs = [r for r in v.incoming_raw_jobs if v._raw_job_id(r) not in v.accepted_job_ids]
        if v.incoming_raw_jobs:
            self.spawn_next_notification_immediate()

    def spawn_next_notification_immediate(self) -> None:
        v = self.view
        if not v.incoming_raw_jobs:
            return
        raw = v.incoming_raw_jobs.pop(0)
        v.job_notification_active = True
        v.job_notification_data = raw
        v.job_notification_timer = v.NOTIF_ACCEPT_SECONDS

        jid = v._raw_job_id(raw)
        payout = v._get_job_payout(raw)
        weight = raw.get("weight", 0)
        v.show_notification(f"📦 NUEVO PEDIDO\nID:{jid} Pago:${payout} Peso:{weight}kg\n(A) Aceptar (R) Rechazar")

    def accept_current(self) -> None:
        v = self.view
        if not v.job_notification_data:
            return
        raw = v.job_notification_data
        jid = v._raw_job_id(raw)

        inventory = v.state.get("inventory") if isinstance(v.state, dict) else getattr(v.state, "inventory", None)
        new_weight = float(raw.get("weight", 1.0))
        if inventory and (getattr(inventory, "current_weight", 0.0) + new_weight > getattr(inventory, "max_weight", 10.0)):
            v.show_notification("❌ Capacidad insuficiente")
            v.rejected_raw_jobs.append(raw)
            v.job_notification_active = False
            v.job_notification_data = None
            return

        if v.job_manager:
            try:
                v.job_manager.add_job_from_raw(raw)
                job = v.job_manager.get_job(jid)
                if job:
                    job.accepted = True
                    if not getattr(job, "payout", None):
                        setattr(job, "payout", v._get_job_payout(job) or v._get_job_payout(raw))
            except Exception:
                pass

        v.accepted_job_ids.add(jid)
        v.job_notification_active = False
        v.job_notification_data = None
        v.next_spawn_timer = v.NEXT_SPAWN_AFTER_ACCEPT
        v.show_notification(f"✅ Pedido {jid} aceptado")

    def reject_current(self) -> None:
        v = self.view
        if v.job_notification_data:
            v.rejected_raw_jobs.append(v.job_notification_data)
        v.job_notification_active = False
        v.job_notification_data = None
        v.show_notification("❌ Pedido rechazado")

    # Drawing of the right-bottom notification panel
    def draw(self) -> None:
        v = self.view
        if not v.job_notification_active or not v.job_notification_data:
            return
        raw = v.job_notification_data
        job_id = v._raw_job_id(raw)
        payout = v._get_job_payout(raw)
        weight = raw.get("weight", 0)
        priority = raw.get("priority", 1)
        description = raw.get("description", "Sin descripción")

        panel_width = 400
        panel_height = 250
        left = v.SCREEN_WIDTH - panel_width - 20 if hasattr(v, 'SCREEN_WIDTH') else v.width - panel_width - 20
        bottom = 100
        right = left + panel_width
        top = bottom + panel_height

        from .game_window import _draw_rect_lrbt_filled, _draw_rect_lrbt_outline  # avoid cycle at import time
        # Colores adaptados al tema oscuro del juego
        _draw_rect_lrbt_filled(left, right, bottom, top, (25, 30, 45))  # Fondo oscuro como el HUD
        _draw_rect_lrbt_outline(left, right, bottom, top, (70, 85, 110), 2)  # Borde azul claro

        from arcade import Text
        Text("📦 NUEVO PEDIDO", left + 5, top - 25, (255, 215, 0), 16, bold=True).draw()  # Dorado más suave

        info_y = top - 50
        Text(f"ID: {job_id}", left + 15, info_y, arcade.color.WHITE, 12).draw()
        Text(f"Pago: ${payout}", left + 15, info_y - 20, (144, 238, 144), 12).draw()  # Verde claro
        Text(f"Peso: {weight}kg", left + 15, info_y - 40, (135, 206, 235), 12).draw()  # Azul claro
        Text(f"Prioridad: {priority}", left + 15, info_y - 60, (255, 165, 0), 12).draw()  # Naranja

        time_y = info_y - 80
        if v.game_manager:
            try:
                time_remaining = v.game_manager.get_job_time_remaining(raw)
                if time_remaining != float('inf'):
                    minutes = int(time_remaining // 60)
                    seconds = int(time_remaining % 60)
                    time_color = arcade.color.GREEN if time_remaining > 300 else arcade.color.ORANGE if time_remaining > 60 else arcade.color.RED
                    Text(f"Tiempo límite: {minutes:02d}:{seconds:02d}", left + 15, time_y, time_color, 12).draw()
                    time_y -= 20
            except Exception:
                pass

        controls_y = bottom + 30
        Text("(A) Aceptar  (R) Rechazar", left + 15, controls_y, (255, 255, 0), 12).draw()  # Amarillo
        Text(f"Decidir en: {int(v.job_notification_timer)}s", left + 15, controls_y - 20, (255, 99, 71), 12).draw()  # Rojo coral


