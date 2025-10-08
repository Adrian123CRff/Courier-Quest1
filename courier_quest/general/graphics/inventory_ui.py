from __future__ import annotations

from typing import Any, List


class InventoryUI:
    def __init__(self, view: Any) -> None:
        self.view = view

    # Drawing of the inventory panel (delegated from MapPlayerView._draw_panel)
    def draw(self) -> None:
        view = self.view
        view.inventory_title.draw()

        # Intentar obtener inventario desde diferentes fuentes
        inventory = None
        if hasattr(view, "inventory") and view.inventory:
            inventory = view.inventory
        elif isinstance(view.state, dict):
            inventory = view.state.get("inventory", None)
        else:
            inventory = getattr(view.state, "inventory", None)
        if inventory:
            try:
                weight = getattr(inventory, "current_weight", 0)
                max_weight = getattr(inventory, "max_weight", 10)

                # Collect items from inventory structure
                if hasattr(inventory, 'get_deque_values'):
                    inventory_items: List[Any] = inventory.get_deque_values()
                else:
                    inventory_items = []
                    if hasattr(inventory, 'deque'):
                        for item in inventory.deque:
                            inventory_items.append(getattr(item, "val", item))

                # Optional sorting
                if view.inventory_sort_mode == "priority":
                    try:
                        inventory_items = sorted(
                            inventory_items,
                            key=lambda j: getattr(j, "priority", None) or (getattr(j, "raw", {}) or {}).get("priority", 999),
                        )
                    except Exception:
                        pass
                elif view.inventory_sort_mode == "deadline":
                    try:
                        inventory_items = sorted(
                            inventory_items,
                            key=lambda j: getattr(j, "deadline", None) or (getattr(j, "raw", {}) or {}).get("deadline", 999999),
                        )
                    except Exception:
                        pass

                items: List[str] = []
                view_slice = inventory_items[view.inventory_view_index:view.inventory_view_index + 4]
                for job in view_slice:
                    job_id = getattr(job, "id", job.get("id") if isinstance(job, dict) else str(job))
                    items.append(f"- {job_id}")

                inventory_info = f"Peso: {weight}/{max_weight}kg\n" + "\n".join(items or ["- Vacío"])
            except Exception:
                inventory_info = "Peso: 0/10kg\n- Error cargando"
        else:
            inventory_info = "Peso: 0/10kg\n- Vacío"

        view.inventory_text.text = inventory_info
        view.inventory_text.draw()

    # Key handling for inventory navigation and sorting.
    # Returns True if the key was handled (and a notification was shown), otherwise False.
    def handle_key_A(self) -> bool:
        view = self.view
        if view.job_notification_active and view.job_notification_data:
            return False
        # Intentar obtener inventario desde diferentes fuentes
        inventory = None
        if hasattr(view, "inventory") and view.inventory:
            inventory = view.inventory
        elif isinstance(view.state, dict):
            inventory = view.state.get("inventory", None)
        else:
            inventory = getattr(view.state, "inventory", None)
        if view.inventory_view_index > 0:
            view.inventory_view_index -= 1
            if hasattr(view, "show_notification"):
                view.show_notification("◀ Página anterior del inventario")
            return True
        return False

    def handle_key_D(self) -> bool:
        view = self.view
        if view.job_notification_active and view.job_notification_data:
            return False
        # Intentar obtener inventario desde diferentes fuentes
        inventory = None
        if hasattr(view, "inventory") and view.inventory:
            inventory = view.inventory
        elif isinstance(view.state, dict):
            inventory = view.state.get("inventory", None)
        else:
            inventory = getattr(view.state, "inventory", None)
        if not inventory:
            return False
        try:
            if hasattr(inventory, 'get_deque_values'):
                inventory_items = inventory.get_deque_values()
            else:
                inventory_items = []
                if hasattr(inventory, 'deque'):
                    for item in inventory.deque:
                        inventory_items.append(getattr(item, "val", item))

            if view.inventory_view_index + 4 < len(inventory_items):
                view.inventory_view_index += 1
                if hasattr(view, "show_notification"):
                    view.show_notification("▶ Página siguiente del inventario")
                return True
        except Exception:
            pass
        return False

    def handle_key_S(self) -> bool:
        view = self.view
        if view.inventory_sort_mode == "normal":
            view.inventory_sort_mode = "priority"
        elif view.inventory_sort_mode == "priority":
            view.inventory_sort_mode = "deadline"
        else:
            view.inventory_sort_mode = "normal"
        if hasattr(view, "show_notification"):
            view.show_notification(f"📋 Ordenando por: {view.inventory_sort_mode}")
        return True


