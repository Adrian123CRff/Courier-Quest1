#input_handler.py
"""
Input Handler - Manages all keyboard and mouse input
"""

import arcade
from typing import Any


class InputHandler:
    """Handles all input events and delegates to appropriate systems."""

    def __init__(self, parent_view):
        self.parent = parent_view
        self.waiting_for_undo_steps = False

    def on_key_press(self, key: int, modifiers: int) -> None:
        """Handle key press events."""
        self.parent._last_input_time = self.parent.time.time()

        if self.parent._show_lose_overlay:
            # cualquier tecla: volver al menú
            try:
                from .ui_view_gui import GameMenuView
                self.parent.window.show_view(GameMenuView())
            except Exception:
                pass
            return

        # snapshot for undo on any significant key
        try:
            if key in (
                arcade.key.UP, arcade.key.DOWN, arcade.key.LEFT, arcade.key.RIGHT,
                arcade.key.P, arcade.key.E
            ):
                self.parent.undo.snapshot()
        except Exception:
            pass

        # P: pickup manual (misma o adyacente)
        if key == arcade.key.P:
            try:
                picked = False
                if self.parent.game_manager and hasattr(self.parent.game_manager, 'try_pickup_at'):
                    picked = self.parent.game_manager.try_pickup_at(self.parent.player.cell_x, self.parent.player.cell_y)
                if not picked:
                    picked = self.parent._pickup_nearby()
                if picked:
                    self.parent.show_notification("¡Paquete recogido! Ve al punto de entrega.")
                else:
                    self.parent.show_notification("No hay paquete para recoger aquí o adyacente.")
            except Exception as e:
                print(f"[INPUT] Error recogiendo paquete (P): {e}")
            return

        # E: entrega manual (misma o adyacente)
        if key == arcade.key.E:
            px, py = int(self.parent.player.cell_x), int(self.parent.player.cell_y)
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

                        # también en atajo manual, remover del inventario
                        self.parent._remove_job_from_inventory(job)

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

                        self.parent._notify_delivery(job, pay, on_time)

                        if isinstance(result, dict):
                            jid = result.get('job_id', '¿?')
                            self.parent.show_notification(f"¡Pedido {jid} entregado!\n+${pay:.0f}")
                        else:
                            self.parent.show_notification(f"¡Pedido entregado! +${pay:.0f}")
                except Exception as e:
                    print(f"[INPUT] Error deliver (E, GM): {e}")

            if not delivered:
                if self.parent._try_deliver_at_position(px, py):
                    self.parent.show_notification("¡Pedido entregado! +$")
                else:
                    self.parent.show_notification("No hay entrega aquí.")
            return

        if key == arcade.key.A:
            if self.parent.job_notification_active and self.parent.job_notification_data:
                self.parent.notifications.accept_current()
                return
            if self.parent._pending_offer:
                try:
                    on_accept, _ = self.parent._pending_offer
                    if on_accept:
                        on_accept(None)
                finally:
                    self.parent._pending_offer = None
                    self.parent._offer_job_id = None
                return
            # Navegación del inventario - ir al item anterior
            try:
                inv = self.parent.state.get("inventory") if isinstance(self.parent.state, dict) else getattr(self.parent.state, "inventory", None)
                if inv:
                    items = []
                    if hasattr(inv, 'deque') and inv.deque:
                        items = list(inv.deque)
                    elif hasattr(inv, 'items') and inv.items:
                        items = list(inv.items)
                    elif hasattr(inv, '__iter__'):
                        items = list(inv)

                    if len(items) > 1:
                        self.parent.inventory_view_index = (self.parent.inventory_view_index - 1) % len(items)
                        self.parent.show_notification(f"Item {self.parent.inventory_view_index + 1} de {len(items)}")
                        return
            except Exception:
                pass
            if self.parent.inventory_ui.handle_key_A():
                return

        if key == arcade.key.D:
            if self.parent.job_notification_active and self.parent.job_notification_data:
                return
            # Navegación del inventario - ir al item siguiente
            try:
                inv = self.parent.state.get("inventory") if isinstance(self.parent.state, dict) else getattr(self.parent.state, "inventory", None)
                if inv:
                    items = []
                    if hasattr(inv, 'deque') and inv.deque:
                        items = list(inv.deque)
                    elif hasattr(inv, 'items') and inv.items:
                        items = list(inv.items)
                    elif hasattr(inv, '__iter__'):
                        items = list(inv)

                    if len(items) > 1:
                        self.parent.inventory_view_index = (self.parent.inventory_view_index + 1) % len(items)
                        self.parent.show_notification(f"Item {self.parent.inventory_view_index + 1} de {len(items)}")
                        return
            except Exception:
                pass
            if self.parent.inventory_ui.handle_key_D():
                        return

        if key == arcade.key.R:
            if self.parent.job_notification_active and self.parent.job_notification_data:
                self.parent.notifications.reject_current()
                return
            if self.parent._pending_offer:
                try:
                    _, on_reject = self.parent._pending_offer
                    if on_reject:
                        on_reject(None)
                finally:
                    self.parent._pending_offer = None
                    self.parent._offer_job_id = None
                return

        if key == arcade.key.S:
            if self.parent.inventory_ui.handle_key_S():
                return

        if key == arcade.key.L and modifiers & arcade.key.MOD_CTRL:
            self.parent._load_initial_jobs()
            self.parent.show_notification("🔄 Pedidos recargados")
            return

        # Ctrl+Shift+S: Guardar
        if key == arcade.key.S and (modifiers & arcade.key.MOD_CTRL) and (modifiers & arcade.key.MOD_SHIFT):
            # Add player position and elapsed time to state before saving
            try:
                self.parent.state["player_x"] = self.parent.player.cell_x
                self.parent.state["player_y"] = self.parent.player.cell_y
                if self.parent.game_manager and hasattr(self.parent.game_manager, "get_game_time"):
                    self.parent.state["elapsed_seconds"] = self.parent.game_manager.get_game_time()
            except Exception as e:
                print(f"[SAVE] Error adding player position: {e}")
            if self.parent.save_manager.save():
                self.parent.show_notification("💾 Partida guardada")
            else:
                self.parent.show_notification("❌ Error al guardar")
            return

        # Ctrl+O: Cargar
        if key == arcade.key.O and (modifiers & arcade.key.MOD_CTRL):
            if self.parent.save_manager.load():
                # re-inicializar sistemas con flag de reanudación
                try:
                    if isinstance(self.parent.state, dict):
                        self.parent.state["__resume_from_save__"] = True
                    else:
                        setattr(self.parent.state, "__resume_from_save__", True)
                except Exception:
                    pass
                self.parent._initialize_game_systems()
                self.parent.show_notification("📂 Partida cargada")
            else:
                self.parent.show_notification("❌ Error al cargar")
            return

        # C: cancelar pedido seleccionado del inventario (penaliza reputación)
        if key == arcade.key.C:
            self._cancel_current_job()
            return

        # Z eliminado para deshacer múltiple: solo el botón de UI permite deshacer

        # Manejo de movimiento solo con flechas
        dx, dy = 0, 0
        if key == arcade.key.UP:
            dy = -1
            self.parent.facing = "up"
        elif key == arcade.key.DOWN:
            dy = 1
            self.parent.facing = "down"
        elif key == arcade.key.LEFT:
            dx = -1
            self.parent.facing = "left"
        elif key == arcade.key.RIGHT:
            dx = 1
            self.parent.facing = "right"
        else:
            return

        self.parent._apply_facing()

        if self.parent.game_manager:
            try:
                if hasattr(self.parent.game_manager, 'handle_player_movement'):
                    self.parent.game_manager.handle_player_movement(dx, dy)
                    return
                if hasattr(self.parent.game_manager, 'handle_Player_movement'):
                    self.parent.game_manager.handle_Player_movement(dx, dy)
                    return
            except Exception:
                pass

        moved = self.parent.player.move_by(dx, dy, self.parent.game_map)
        if not moved:
            if self.parent.player.bound_stats and hasattr(self.parent.player.bound_stats, "can_move") and not self.parent.player.bound_stats.can_move():
                self.parent.show_notification("[INFO] No puedes moverte: resistencia agotada.")
            else:
                self.parent.show_notification("Movimiento bloqueado")

    def on_key_release(self, key: int, modifiers: int):
        """Handle key release events."""
        if not self.parent._pending_offer:
            return
        try:
            on_accept, on_reject = self.parent._pending_offer
            if key == arcade.key.A and on_accept:
                on_accept(None)
            elif key == arcade.key.R and on_reject:
                on_reject(None)
        finally:
            self.parent._pending_offer = None
            self.parent._offer_job_id = None

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        """Handle mouse press events."""
        if button == arcade.MOUSE_BUTTON_LEFT:
            # Botón de deshacer
            if self.parent.undo_button_rect:
                btn_left, btn_bottom, btn_right, btn_top = self.parent.undo_button_rect
                if btn_left <= x <= btn_right and btn_bottom <= y <= btn_top:
                    self._handle_undo()
                    return

            # Botones del inventario
            if self.parent.inventory_left_button_rect:
                btn_left, btn_bottom, btn_right, btn_top = self.parent.inventory_left_button_rect
                if btn_left <= x <= btn_right and btn_bottom <= y <= btn_top:
                    self._navigate_inventory_left()
                    return

            if self.parent.inventory_right_button_rect:
                btn_left, btn_bottom, btn_right, btn_top = self.parent.inventory_right_button_rect
                if btn_left <= x <= btn_right and btn_bottom <= y <= btn_top:
                    self._navigate_inventory_right()
                    return

    def _handle_undo(self):
        try:
            if hasattr(self.parent, "_undo_one_step"):
                self.parent._undo_one_step()
                return
        except Exception:
            pass
        self.parent.show_notification("No hay acciones para deshacer")

    def _navigate_inventory_left(self):
        """Navega hacia la izquierda en el inventario"""
        try:
            inv = self.parent.state.get("inventory") if isinstance(self.parent.state, dict) else getattr(self.parent.state, "inventory", None)
            if inv:
                items = []
                if hasattr(inv, 'deque') and inv.deque:
                    items = list(inv.deque)
                elif hasattr(inv, 'items') and inv.items:
                    items = list(inv.items)
                elif hasattr(inv, '__iter__'):
                    items = list(inv)

                if len(items) > 1:
                    self.parent.inventory_view_index = (self.parent.inventory_view_index - 1) % len(items)
                    self.parent.show_notification(f"Item {self.parent.inventory_view_index + 1} de {len(items)}")
        except Exception:
            pass

    def _navigate_inventory_right(self):
        """Navega hacia la derecha en el inventario"""
        try:
            inv = self.parent.state.get("inventory") if isinstance(self.parent.state, dict) else getattr(self.parent.state, "inventory", None)
            if inv:
                items = []
                if hasattr(inv, 'deque') and inv.deque:
                    items = list(inv.deque)
                elif hasattr(inv, 'items') and inv.items:
                    items = list(inv.items)
                elif hasattr(inv, '__iter__'):
                    items = list(inv)

                if len(items) > 1:
                    self.parent.inventory_view_index = (self.parent.inventory_view_index + 1) % len(items)
                    self.parent.show_notification(f"Item {self.parent.inventory_view_index + 1} de {len(items)}")
        except Exception:
            pass

    def _cancel_current_job(self):
        """Cancela el pedido actualmente seleccionado en el inventario"""
        try:
            # Obtener inventario
            inv = self.parent.state.get("inventory") if isinstance(self.parent.state, dict) else getattr(
                self.parent.state, "inventory", None)
            if not inv:
                self.parent.show_notification("No hay inventario disponible")
                return

            # Obtener items del inventario
            items = []
            if hasattr(inv, 'deque') and inv.deque:
                items = list(inv.deque)
            elif hasattr(inv, 'items') and inv.items:
                items = list(inv.items)
            elif hasattr(inv, '__iter__'):
                items = list(inv)

            if not items:
                self.parent.show_notification("No hay pedidos en el inventario")
                return

            # Obtener el trabajo actual
            if self.parent.inventory_view_index >= len(items):
                self.parent.inventory_view_index = 0

            current_job = items[self.parent.inventory_view_index]
            job_id = getattr(current_job, "id", None)

            if not job_id:
                self.parent.show_notification("No se puede identificar el pedido")
                return

            # Aplicar penalización de reputación
            rep_change = 0
            if hasattr(self.parent.player_stats, "update_reputation"):
                rep_change = self.parent.player_stats.update_reputation("cancel_order")

            # Remover del inventario
            self.parent.jobs_logic.remove_job_from_inventory(current_job)

            # Marcar como cancelado en el job_manager y ocultar marcadores
            if self.parent.job_manager:
                job_obj = self.parent.job_manager.get_job(job_id)
                if job_obj:
                    job_obj.accepted = False
                    job_obj.rejected = True
                    # Asegurar que el pickup/dropoff desaparezcan del mapa
                    try:
                        job_obj.picked_up = False
                        job_obj.dropoff_visible = False
                        job_obj.visible_pickup = False
                        job_obj.completed = False
                    except Exception:
                        pass
                    # Registrar en el JobManager para consistencia
                    try:
                        self.parent.job_manager.mark_rejected(job_id)
                    except Exception:
                        pass

            self.parent.show_notification(
                f"Pedido {job_id} cancelado. Reputación: {int(getattr(self.parent.player_stats, 'reputation', 0))} ({rep_change:+d})"
            )

        except Exception as e:
            print(f"[CANCEL] Error cancelando pedido: {e}")
            self.parent.show_notification("Error al cancelar pedido")