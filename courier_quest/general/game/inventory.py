# inventory.py
from typing import Optional, List, Any
from game.adts import Deque

class Inventory:
    """
    Inventario implementado sobre una Deque doblemente enlazada (game.adts.Deque).
    """

    def __init__(self, max_weight: float = 10.0):
        self.deque = Deque()
        self.max_weight = float(max_weight)
        self.current_weight = 0.0
        self._cursor = None  # nodo interno (no el valor)

    @staticmethod
    def _job_weight(job) -> float:
        """
        Extrae el 'peso' del job de forma robusta.
        """
        try:
            # dict directamente
            if isinstance(job, dict):
                return float(job.get("weight", job.get("peso", 1.0)))
            # wrapper con .raw
            if hasattr(job, "raw") and isinstance(job.raw, dict):
                return float(job.raw.get("weight", job.raw.get("peso", 1.0)))
            # atributo directo
            if hasattr(job, "weight"):
                return float(getattr(job, "weight"))
        except Exception:
            pass
        return 1.0

    def can_add(self, job) -> bool:
        return (self.current_weight + self._job_weight(job)) <= self.max_weight

    def add(self, job) -> bool:
        w = self._job_weight(job)
        if not self.can_add(job):
            return False
        # append al final
        self.deque.append(job)
        self.current_weight += w
        # si no hay cursor, posicionarlo en el primer elemento
        if self._cursor is None:
            self._cursor = getattr(self.deque, "head", None)
        return True

    def _deque_values(self) -> List[Any]:
        """
        Normaliza la iteración sobre self.deque para devolver siempre los valores.
        """
        vals = []
        try:
            for n in self.deque:
                # si n es nodo con .val, devolvemos n.val; si n ya es valor, lo devolvemos tal cual
                vals.append(n.val if hasattr(n, "val") else n)
        except TypeError:
            # si self.deque no es iterable por alguna razón, intentar recorrer manualmente via head
            node = getattr(self.deque, "head", None)
            while node:
                vals.append(node.val if hasattr(node, "val") else node)
                node = node.next
        return vals

    def _rebuild_from_list(self, items: List[Any]) -> None:
        """Reconstruye self.deque a partir de items (lista de valores)."""
        new_deque = Deque()
        for it in items:
            new_deque.append(it)
        self.deque = new_deque
        # resetear cursor al head si hay elementos
        self._cursor = getattr(self.deque, "head", None)

    def _find_node_by_job_id(self, job_id: str):
        """Devuelve el nodo cuyo item tiene id == job_id, o None."""
        # primero intentamos recorrer con head/next si existe
        node = getattr(self.deque, "head", None)
        while node:
            item = node.val if hasattr(node, "val") else node
            cur_id = None
            if hasattr(item, "id"):
                cur_id = getattr(item, "id")
            elif isinstance(item, dict):
                cur_id = item.get("id")
            elif hasattr(item, "raw") and isinstance(item.raw, dict):
                cur_id = item.raw.get("id")
            if cur_id == job_id:
                return node
            node = getattr(node, "next", None)
        return None

    def remove(self, job_id: str) -> bool:
        """
        Elimina el pedido con id == job_id del inventario.
        """
        # Intentamos obtener el nodo
        node = self._find_node_by_job_id(job_id)

        if node is None:
            # Si no encontramos nodo, reconstruimos filtrando
            items = self._deque_values()
            new_items = []
            removed = False
            for it in items:
                # extraer id robustamente
                it_id = None
                if hasattr(it, "id"):
                    it_id = getattr(it, "id")
                elif isinstance(it, dict):
                    it_id = it.get("id")
                elif hasattr(it, "raw") and isinstance(it.raw, dict):
                    it_id = it.raw.get("id")
                if it_id == job_id and not removed:
                    removed = True
                    weight_to_subtract = self._job_weight(it)
                    self.current_weight = max(0.0, self.current_weight - weight_to_subtract)
                    continue
                new_items.append(it)
            if not removed:
                return False
            self._rebuild_from_list(new_items)
            return True

        # Si tenemos el nodo, proceder a eliminar
        try:
            weight_to_subtract = float(self._job_weight(node.val if hasattr(node, "val") else node))
        except Exception:
            weight_to_subtract = 0.0

        try:
            if hasattr(self.deque, "remove_node"):
                self.deque.remove_node(node)
            else:
                # fallback: reconstruir la lista sin el elemento
                items = self._deque_values()
                new_items = []
                removed = False
                for it in items:
                    it_id = None
                    if hasattr(it, "id"):
                        it_id = getattr(it, "id")
                    elif isinstance(it, dict):
                        it_id = it.get("id")
                    elif hasattr(it, "raw") and isinstance(it.raw, dict):
                        it_id = it.raw.get("id")
                    if it_id == job_id and not removed:
                        removed = True
                        continue
                    new_items.append(it)
                self._rebuild_from_list(new_items)
        except Exception:
            return False

        # ajustar peso y cursor
        self.current_weight = max(0.0, float(self.current_weight) - weight_to_subtract)

        # asegurar cursor válido
        try:
            if getattr(self.deque, "head", None) is None:
                self._cursor = None
            else:
                # si cursor apuntaba al nodo eliminado, moverlo al head
                found = False
                node = getattr(self.deque, "head", None)
                while node:
                    if node is self._cursor:
                        found = True
                        break
                    node = getattr(node, "next", None)
                if not found:
                    self._cursor = getattr(self.deque, "head", None)
        except Exception:
            self._cursor = getattr(self.deque, "head", None)

        return True

    # ... (resto de métodos sin cambios)
# inventory.py - AÑADIR MÉTODO PÚBLICO
# Añade este método a tu clase Inventory:

    def get_deque_values(self) -> List[Any]:
        """
        Método público para obtener los valores del deque.
        Reemplaza el uso de _deque_values().
        """
        return self._deque_values()

    def sort_by_priority(self):
        items = self._deque_values()
        items.sort(key=lambda job: -getattr(job, 'priority', 0))  # Merge Sort o QuickSort
        self._rebuild_from_list(items)

    def sort_by_deadline(self):
        items = self._deque_values()
        items.sort(key=lambda job: getattr(job, 'deadline_timestamp', float('inf')))
        self._rebuild_from_list(items)