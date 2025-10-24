"""
Game Logic Handler - Handles game-specific logic like pickup/delivery
"""

from typing import Any


class GameLogicHandler:
    """Handles game-specific logic operations like pickup, delivery, and money management."""

    def __init__(self, parent_view):
        self.parent = parent_view

    def pickup_nearby(self) -> bool:
        """Handle pickup logic for nearby jobs."""
        # This method would contain the logic from the original _pickup_nearby method
        # For now, returning False as placeholder - will be implemented when refactoring
        return False

    def try_deliver_at_position(self, px: int, py: int) -> bool:
        """Try to deliver at a specific position."""
        # This method would contain the logic from the original _try_deliver_at_position method
        # For now, returning False as placeholder - will be implemented when refactoring
        return False

    def remove_job_from_inventory(self, job: Any):
        """Remove a job from the inventory."""
        try:
            inv = self.parent.state.get("inventory") if isinstance(self.parent.state, dict) else getattr(self.parent.state, "inventory", None)
            if inv and job:
                if hasattr(inv, "remove") and job in inv:
                    inv.remove(job)
                elif hasattr(inv, "deque") and job in inv.deque:
                    inv.deque.remove(job)
                # Recalcular peso
                if hasattr(inv, "current_weight"):
                    inv.current_weight = sum(float(getattr(j, 'weight', 0.0)) for j in (inv.deque if hasattr(inv, 'deque') else inv))
        except Exception as e:
            print(f"[INVENTORY] Error removing job: {e}")

    def synchronize_money_with_completed_jobs(self):
        """Synchronize money with completed jobs."""
        try:
            # 1) Identificar entregas ya pagadas
            already_paid = set()
            if self.parent.job_manager:
                for j in self.parent.job_manager.all_jobs():
                    if getattr(j, "completed", False) and getattr(j, "paid", False):
                        jid = getattr(j, "id", None) or getattr(j, "job_id", None)
                        if jid:
                            already_paid.add(jid)

            # 2) Pagar entregas no contabilizadas
            for jid in self.parent._counted_deliveries - already_paid:
                if self.parent.job_manager:
                    job = self.parent.job_manager.get_job(jid)
                    if job:
                        payout = self.parent._get_job_payout(job)
                        if payout > 0:
                            self.parent._add_money(payout)
                            print(f"[SYNC] Pago atrasado ${payout:.2f} por {jid}")
                            # Marcar como pagado
                            setattr(job, "paid", True)
        except Exception as e:
            print(f"[SYNC] Error sincronizando dinero: {e}")

    def recompute_money_from_jobs(self):
        """Recompute money from all jobs to ensure consistency."""
        try:
            # Forzar consistencia: recalcular dinero basado en jobs completados
            total_expected = 0.0
            if self.parent.job_manager:
                for j in self.parent.job_manager.all_jobs():
                    if getattr(j, "completed", False):
                        payout = self.parent._get_job_payout(j)
                        total_expected += payout

            current_money = self.parent._get_state_money()
            if abs(current_money - total_expected) > 0.01:  # Tolerancia para errores de punto flotante
                print(f"[RECOMPUTE] Ajustando dinero: ${current_money:.2f} -> ${total_expected:.2f}")
                self.parent._set_state_money(total_expected)
        except Exception as e:
            print(f"[RECOMPUTE] Error recalculando dinero: {e}")

    def notify_delivery(self, job: Any, pay: float, on_time: bool):
        """Notify about a delivery completion."""
        try:
            if job:
                jid = getattr(job, "id", None) or getattr(job, "job_id", None) or "Unknown"
                # Marcar como pagado para evitar doble pago
                setattr(job, "paid", True)
                # Añadir a entregas contabilizadas
                if jid:
                    self.parent._counted_deliveries.add(jid)

                # Actualizar estadísticas del jugador
                if hasattr(self.parent.player_stats, "deliveries_completed"):
                    self.parent.player_stats.deliveries_completed += 1
                if on_time and hasattr(self.parent.player_stats, "on_time_deliveries"):
                    self.parent.player_stats.on_time_deliveries += 1

                # Actualizar reputación basada en entregas a tiempo
                if hasattr(self.parent.player_stats, "reputation"):
                    rep_change = 2 if on_time else -1
                    self.parent.player_stats.reputation = max(0, min(100, self.parent.player_stats.reputation + rep_change))
        except Exception as e:
            print(f"[DELIVERY] Error notificando entrega: {e}")
