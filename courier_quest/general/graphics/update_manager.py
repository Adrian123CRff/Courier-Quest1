#update_manager.py
"""
Update Manager - Handles game update logic and timers
"""

import time


class UpdateManager:
    """Manages game update cycles, timers, and periodic updates."""

    def __init__(self, parent_view):
        self.parent = parent_view

    def on_update(self, dt: float) -> None:
        """Main update method that handles all game logic updates."""
        if self.parent.game_manager:
            try:
                self.parent.game_manager.update(dt)
            except Exception as e:
                print(f"Error en game_manager.update: {e}")

        # notifications timers and spawning
        self.parent.notifications.update_timers(dt)

        if self.parent.active_notification and self.parent.notification_timer > 0:
            self.parent.notification_timer -= dt
            if self.parent.notification_timer <= 0:
                self.parent.active_notification = None

        input_active = (time.time() - self.parent._last_input_time) < self.parent.INPUT_ACTIVE_WINDOW
        self.parent._ensure_inventory()
        inventory = self.parent.state.get("inventory", None) if isinstance(self.parent.state, dict) else getattr(self.parent.state, "inventory", None)
        was_moving = bool(self.parent.player.moving)

        try:
            self.parent.player.update(dt, player_stats=self.parent.player_stats, weather_system=self.parent.weather_markov, inventory=inventory)
        except Exception:
            try:
                self.parent.player.update(dt)
            except Exception:
                pass

        if was_moving and not self.parent.player.moving:
            px = int(self.parent.player.cell_x)
            py = int(self.parent.player.cell_y)

            picked_up = False
            if self.parent.game_manager and hasattr(self.parent.game_manager, 'try_pickup_at'):
                try:
                    picked_up = self.parent.game_manager.try_pickup_at(px, py)
                except Exception as e:
                    print(f"Error en try_pickup_at: {e}")

            if not picked_up:
                picked_up = self.parent.jobs_logic.pickup_nearby()

            if picked_up:
                self.parent.show_notification("¡Paquete recogido! Ve al punto de entrega.")

            delivered = False
            if self.parent.game_manager and hasattr(self.parent.game_manager, 'try_deliver_at'):
                try:
                    result = self.parent.game_manager.try_deliver_at(px, py)
                    if result:
                        delivered = True
                        try:
                            jid = result.get('job_id') if isinstance(result, dict) else None
                            job = self.parent.job_manager.get_job(jid) if (jid and self.parent.job_manager) else None
                        except Exception:
                            job = None

                        # **Remover del inventario también en el flujo de GameManager**
                        self.parent.jobs_logic.remove_job_from_inventory(job)

                        # asegurar estado del job
                        try:
                            if job and not getattr(job, "completed", False):
                                job.completed = True
                        except Exception:
                            pass

                        pay_hint = 0.0
                        try:
                            if isinstance(result, dict):
                                pay_hint = result.get("pay", 0)
                        except Exception:
                            pass
                        pay = self.parent._get_job_payout(job) if job is not None else self.parent._parse_money(pay_hint)

                        on_time = True
                        try:
                            if hasattr(self.parent.game_manager, "get_job_time_remaining"):
                                rem = self.parent.game_manager.get_job_time_remaining(
                                    getattr(job, "raw", {}) if job is not None else {}
                                )
                                # on_time = True si no hay deadline o si aún hay tiempo restante
                                on_time = (rem == float("inf")) or (rem >= 0)
                        except Exception:
                            pass

                        self.parent.jobs_logic.notify_delivery(job, pay, on_time)

                        if isinstance(result, dict):
                            jid = result.get('job_id', '¿?')
                            self.parent.show_notification(f"¡Pedido {jid} entregado!\n+${pay:.0f}")
                        else:
                            self.parent.show_notification(f"¡Pedido entregado! +${pay:.0f}")
                except Exception as e:
                    print(f"Error deliver (GameManager): {e}")

            if not delivered:
                delivered = self.parent.jobs_logic.try_deliver_at_position(px, py)
                if delivered:
                    self.parent.show_notification("¡Pedido entregado! +$")

        # 1) pagar entregas no contabilizadas
        self.parent.jobs_logic.synchronize_money_with_completed_jobs()
        # 2) y forzar consistencia si algo lo desfasó
        self.parent.jobs_logic.recompute_money_from_jobs()

        # 3) verificar condiciones de fin de partida y registrar puntaje
        try:
            prev_game_over = getattr(self, "_game_over", False)
            self.parent.endgame.check_and_maybe_end()
            if getattr(self, "_game_over", False) and not prev_game_over:
                # activar overlay de derrota si aplica
                money = self.parent._get_state_money()
                goal = self.parent.endgame._compute_goal()
                rep = getattr(self.parent.player_stats, "reputation", 70)
                if rep < 20 or money < goal:
                    self.parent._show_lose_overlay = True
                    self.parent._lose_reason = "Reputación baja" if rep < 20 else "Meta no alcanzada"
        except Exception as e:
            print(f"[ENDGAME] Error: {e}")

        try:
            current_weather = self.parent.weather.get_current_condition_name()
            self.parent.player_stats.update(
                dt,
                bool(self.parent.player.moving),
                getattr(self, "at_rest_point", False),
                float(getattr(inventory, "current_weight", 0.0)) if inventory is not None else 0.0,
                current_weather,
                input_active=input_active
            )
        except Exception as e:
            print(f"Error actualizando player_stats: {e}")

        # unified weather update/render state propagation
        self.parent.weather.update_and_render(dt)
