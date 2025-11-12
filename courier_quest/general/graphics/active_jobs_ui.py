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
                        
                        # Calcular release_time
                        release_time_text = self._get_release_time_text(v, job)
                        
                        # Color según estado
                        if getattr(job, "picked_up", False):
                            color = (144, 238, 144)  # Verde para entregas
                            status_text = f"{job_id} {status} → 🎯"
                        else:
                            color = (255, 255, 255)  # Blanco para recogidas
                            status_text = f"{job_id} {status} (${payout})"
                        
                        # Dibujar información del pedido horizontalmente
                        arcade.Text(status_text, x_pos, top - 45, color, 11).draw()
                        arcade.Text(release_time_text, x_pos, top - 60, (255, 215, 0), 9).draw()
                        
                        x_offset += 1
                        
            except Exception as e:
                arcade.Text(f"Error: {str(e)[:30]}...", left + 200, top - 45, (255, 120, 120), 11).draw()
        else:
            arcade.Text("Sistemas cargando...", left + 200, top - 45, (180, 196, 220), 12).draw()

    def _get_release_time_text(self, view, job) -> str:
        """Calcula y formatea el release_time del pedido"""
        try:
            # Obtener el tiempo actual del juego
            current_time = view.game_manager.get_game_time() if view.game_manager else 0
            
            # Obtener release_time del trabajo
            raw_data = getattr(job, "raw", {})
            release_time = raw_data.get("release_time", 0)
            
            # Calcular tiempo transcurrido desde el release_time
            elapsed_since_release = current_time - release_time
            
            # Formatear el tiempo
            if elapsed_since_release < 0:
                # Aún no ha sido liberado
                remaining = abs(elapsed_since_release)
                minutes = int(remaining // 60)
                seconds = int(remaining % 60)
                return f"⏳ Libera en: {minutes:02d}:{seconds:02d}"
            else:
                # Ya fue liberado, mostrar tiempo transcurrido
                minutes = int(elapsed_since_release // 60)
                seconds = int(elapsed_since_release % 60)
                return f"⏰ Liberado hace: {minutes:02d}:{seconds:02d}"
                
        except Exception:
            return "⏰ Tiempo: N/A"


