#active_jobs_ui.py
from __future__ import annotations

from typing import Any, List
import arcade


class ActiveJobsUI:
    def __init__(self, view: Any) -> None:
        self.view = view

    def draw(self) -> None:
        """Dibuja el panel de pedidos activos horizontalmente en la parte superior"""
        v = self.view
        
        # Medidas del panel horizontal en la parte superior
        panel_w = v.width - 20  # Ancho casi completo de la pantalla
        panel_h = 80  # Altura reducida para que no tape el mapa
        left = 10
        top = v.height - 10
        right = left + panel_w
        bottom = top - panel_h
        
        # Importar funciones de dibujo
        from .game_window import _draw_rect_lrbt_filled, _draw_rect_lrbt_outline
        
        # Fondo del panel
        _draw_rect_lrbt_filled(left, right, bottom, top, (25, 30, 45))
        _draw_rect_lrbt_outline(left, right, bottom, top, (70, 85, 110), 2)
        
        # Título
        arcade.Text("📦 PEDIDOS ACTIVOS", left + 10, top - 20, (255, 165, 0), 14, bold=True).draw()
        
        if v.job_manager and v.game_manager:
            try:
                active_jobs = [j for j in v.job_manager.all_jobs() if getattr(j, "accepted", False) and not getattr(j, "completed", False)]
                
                # Ordenar por deadline (tiempo restante)
                def get_deadline_priority(job):
                    try:
                        if v.game_manager and hasattr(v.game_manager, 'get_job_time_remaining'):
                            remaining = v.game_manager.get_job_time_remaining(getattr(job, "raw", {}))
                            return remaining if remaining != float('inf') else 999999
                        return 999999
                    except Exception:
                        return 999999
                
                active_jobs.sort(key=get_deadline_priority)
                
                if not active_jobs:
                    # Mostrar mensaje cuando no hay pedidos
                    arcade.Text("No hay pedidos activos", left + 200, top - 45, (180, 196, 220), 12).draw()
                    try:
                        available = v.job_manager.get_available_jobs(v.game_manager.get_game_time())
                        if available:
                            arcade.Text(f"{len(available)} pedidos disponibles", left + 200, top - 60, (144, 238, 144), 11).draw()
                    except Exception:
                        pass
                else:
                    # Mostrar pedidos activos horizontalmente (máximo 6 para que quepan bien)
                    x_offset = 0
                    for i, job in enumerate(active_jobs[:6]):
                        x_pos = left + 200 + (x_offset * 180)  # Espaciado horizontal
                        
                        # Estado del pedido
                        status = "✓" if getattr(job, "picked_up", False) else "📦"
                        job_id = getattr(job, "id", "Unknown")
                        payout = v._get_job_payout(job)
                        
                        # Calcular release_time y deadline
                        release_time_text = self._get_release_time_text(v, job)
                        deadline_text, deadline_color = self._get_deadline_text(v, job)
                        
                        # Color según estado
                        if getattr(job, "picked_up", False):
                            color = (144, 238, 144)  # Verde para entregas
                            status_text = f"{job_id} {status} → 🎯"
                        else:
                            color = (255, 255, 255)  # Blanco para recogidas
                            status_text = f"{job_id} {status} (${payout})"
                        
                        # Dibujar información del pedido horizontalmente
                        arcade.Text(status_text, x_pos, top - 45, color, 11).draw()
                        # Color del cronómetro según % restante de release_time
                        percent_remaining = self._get_release_time_percent(v, job)
                        if percent_remaining is not None:
                            import arcade as _arc
                            if percent_remaining >= 20:
                                release_color = _arc.color.GREEN
                            elif percent_remaining >= 10:
                                release_color = _arc.color.ORANGE
                            else:
                                release_color = _arc.color.RED
                        else:
                            # Fallback: verde si está en curso, amarillo si no
                            release_color = (144, 238, 144) if getattr(job, "picked_up", False) else (255, 215, 0)
                        arcade.Text(release_time_text, x_pos, top - 60, release_color, 9).draw()
                        if deadline_text:
                            arcade.Text(deadline_text, x_pos, top - 73, deadline_color, 9).draw()
                        
                        x_offset += 1
                        
            except Exception as e:
                arcade.Text(f"Error: {str(e)[:30]}...", left + 200, top - 45, (255, 120, 120), 11).draw()
        else:
            arcade.Text("Sistemas cargando...", left + 200, top - 45, (180, 196, 220), 12).draw()

    def _get_release_time_text(self, view, job) -> str:
        """Muestra el cronómetro de entrega basado en release_time desde la aceptación.
        Si no hay aceptación registrada, se usa el comportamiento anterior (liberación)."""
        try:
            current_time = view.game_manager.get_game_time() if view.game_manager else 0
            raw_data = getattr(job, "raw", {}) or {}
            release_time = raw_data.get("release_time", 0)
            accepted_at = raw_data.get("accepted_at", None)
            if accepted_at is None:
                accepted_at = getattr(job, "accepted_at", None)

            try:
                release_time = float(release_time or 0.0)
            except (TypeError, ValueError):
                release_time = 0.0
            try:
                accepted_at = float(accepted_at) if accepted_at is not None else None
            except (TypeError, ValueError):
                accepted_at = None

            if accepted_at is not None and release_time > 0.0:
                remaining = release_time - (float(current_time) - accepted_at)
                minutes = int(abs(remaining) // 60)
                seconds = int(abs(remaining) % 60)
                # Mostrar porcentaje restante cuando está en curso
                if remaining >= 0:
                    try:
                        percent = (remaining / release_time) * 100 if release_time else 0
                    except Exception:
                        percent = 0
                    return f"⏳ Tiempo restante: {minutes:02d}:{seconds:02d} ({percent:.0f}%)"
                else:
                    return f"⏰ Tarde: {minutes:02d}:{seconds:02d}"

            # Fallback: comportamiento original de liberación
            elapsed_since_release = float(current_time) - float(raw_data.get("release_time", 0) or 0.0)
            if elapsed_since_release < 0:
                remaining = abs(elapsed_since_release)
                minutes = int(remaining // 60)
                seconds = int(remaining % 60)
                return f"⏳ Libera en: {minutes:02d}:{seconds:02d}"
            else:
                minutes = int(elapsed_since_release // 60)
                seconds = int(elapsed_since_release % 60)
                return f"⏰ Liberado hace: {minutes:02d}:{seconds:02d}"
        except Exception:
            return "⏰ Tiempo: N/A"

    def _get_release_time_percent(self, view, job):
        """Devuelve el porcentaje restante de la ventana de entrega basada en release_time.
        Retorna None si no aplica (no aceptado, sin release_time o ya tarde)."""
        try:
            current_time = view.game_manager.get_game_time() if view.game_manager else 0
            raw_data = getattr(job, "raw", {}) or {}
            release_time = raw_data.get("release_time", 0)
            accepted_at = raw_data.get("accepted_at", None)
            if accepted_at is None:
                accepted_at = getattr(job, "accepted_at", None)

            try:
                release_time = float(release_time or 0.0)
            except (TypeError, ValueError):
                release_time = 0.0
            try:
                accepted_at = float(accepted_at) if accepted_at is not None else None
            except (TypeError, ValueError):
                accepted_at = None

            if accepted_at is not None and release_time > 0.0:
                remaining = release_time - (float(current_time) - accepted_at)
                if remaining >= 0:
                    return max(0.0, (remaining / release_time) * 100) if release_time else 0.0
            return None
        except Exception:
            return None

    def _get_deadline_text(self, view, job):
        """Devuelve texto de tiempo restante vs total y color por urgencia.
        Si no hay deadline, retorna (None, arcade.color.WHITE).
        """
        try:
            raw = getattr(job, "raw", {}) or {}
            if not raw.get("deadline"):
                return None, arcade.color.WHITE

            remaining = view.game_manager.get_job_time_remaining(raw)
            total = view.game_manager.get_job_total_time(raw)

            if remaining == float('inf') or total == float('inf'):
                return None, arcade.color.WHITE

            minutes = int(max(0, remaining) // 60)
            seconds = int(max(0, remaining) % 60)
            percent = (remaining / total) * 100 if total and total != 0 and remaining is not None else 0

            # Color según urgencia
            import arcade as _arc
            if percent >= 50:
                col = _arc.color.GREEN
            elif percent >= 25:
                col = _arc.color.ORANGE
            else:
                col = _arc.color.RED

            prefix = "⏰ Tiempo restante:" if remaining >= 0 else "⏱️ Tiempo vencido:" 
            txt = f"{prefix} {minutes:02d}:{seconds:02d} ({percent:.0f}%)"

            # Alertas visuales cuando está por expirar (una sola vez por trabajo)
            try:
                jid = getattr(job, "id", None)
                if jid and (percent <= 10 or remaining <= 30):
                    alerted = getattr(view, "_alerted_deadline_jobs", None)
                    if alerted is None:
                        alerted = set()
                        setattr(view, "_alerted_deadline_jobs", alerted)
                    if jid not in alerted:
                        if hasattr(view, "show_notification"):
                            view.show_notification(f"⏰ Pedido {jid} por vencer: {minutes:02d}:{seconds:02d} ({percent:.0f}%)")
                        alerted.add(jid)
            except Exception:
                pass
            return txt, col
        except Exception:
            return None, arcade.color.WHITE


