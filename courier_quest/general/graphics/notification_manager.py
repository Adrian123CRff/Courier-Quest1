# notification_manager.py - REEMPLAZAR COMPLETAMENTE
from __future__ import annotations
from typing import Any
import arcade


class NotificationManager:
    def __init__(self, view: Any) -> None:
        self.view = view

    def update_timers(self, dt: float) -> None:
        """Actualiza temporizadores usando tiempo real del juego"""
        v = self.view

        if v.job_notification_active:
            v.job_notification_timer -= dt
            if v.job_notification_timer <= 0:
                self.reject_current()
                return

        # ✅ NUEVO: Verificar trabajos disponibles por release_time REAL
        self.check_available_jobs_by_release_time()

    def check_available_jobs_by_release_time(self) -> None:
        """Verifica trabajos disponibles basado en release_time real"""
        v = self.view
        if v.job_notification_active or not v.game_manager:
            return

        try:
            current_game_time = v.game_manager.get_game_time()

            # Filtrar trabajos cuyo release_time ya pasó
            available_now = []
            for job_data in v.incoming_raw_jobs[:]:  # Copia para modificar
                release_time = job_data.get("release_time", 0)

                # ✅ USAR release_time REAL, no timer artificial
                if release_time <= current_game_time:
                    available_now.append(job_data)
                    v.incoming_raw_jobs.remove(job_data)

            # Mostrar notificaciones para trabajos disponibles
            for job_data in available_now:
                if not v.job_notification_active:
                    self.spawn_next_notification_immediate(job_data)
                    break  # Mostrar uno a la vez

        except Exception as e:
            print(f"[NOTIFICATION] Error verificando trabajos: {e}")

    def spawn_next_notification_immediate(self, job_data) -> None:
        """Muestra notificación para un trabajo específico"""
        v = self.view
        v.job_notification_active = True
        v.job_notification_data = job_data
        v.job_notification_timer = v.NOTIF_ACCEPT_SECONDS

        jid = v._raw_job_id(job_data)
        payout = v._get_job_payout(job_data)
        weight = job_data.get("weight", 0)

        v.show_notification(f"📦 NUEVO PEDIDO\nID:{jid} Pago:${payout} Peso:{weight}kg\n(A) Aceptar (R) Rechazar")

    # ... (mantener accept_current, reject_current, draw sin cambios)
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
                    # Registrar accepted_at para cronómetro basado en release_time
                    try:
                        accepted_at = float(v.game_manager.get_game_time()) if v.game_manager else None
                    except Exception:
                        accepted_at = None
                    if accepted_at is not None:
                        try:
                            setattr(job, "accepted_at", accepted_at)
                        except Exception:
                            pass
                        try:
                            raw["accepted_at"] = accepted_at
                        except Exception:
                            pass
                    if not getattr(job, "payout", None):
                        setattr(job, "payout", v._get_job_payout(job) or v._get_job_payout(raw))
            except Exception:
                pass

        v.accepted_job_ids.add(jid)
        v.job_notification_active = False
        v.job_notification_data = None
        v.next_spawn_timer = v.NEXT_SPAWN_AFTER_ACCEPT
        # Mostrar reputación actual para facilitar ver el contraste si luego se cancela
        try:
            rep = getattr(v.player_stats, "reputation", None)
            if rep is not None:
                v.show_notification(f"✅ Pedido {jid} aceptado. Reputación: {int(rep)}")
            else:
                v.show_notification(f"✅ Pedido {jid} aceptado")
        except Exception:
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
                total_time = v.game_manager.get_job_total_time(raw)

                if time_remaining != float('inf') and total_time != float('inf'):
                    minutes = int(time_remaining // 60)
                    seconds = int(time_remaining % 60)

                    # Calcular porcentaje de tiempo restante
                    time_percent = (time_remaining / total_time) * 100 if total_time > 0 else 0

                    # Color basado en urgencia
                    if time_percent >= 50:
                        time_color = arcade.color.GREEN
                    elif time_percent >= 25:
                        time_color = arcade.color.ORANGE
                    else:
                        time_color = arcade.color.RED

                    Text(f"Tiempo límite: {minutes:02d}:{seconds:02d}", left + 15, time_y, time_color, 12).draw()
                    Text(f"({time_percent:.0f}% restante)", left + 15, time_y - 15, time_color, 10).draw()
                    time_y -= 30
            except Exception as e:
                print(f"[NOTIFICATION] Error mostrando tiempo: {e}")


