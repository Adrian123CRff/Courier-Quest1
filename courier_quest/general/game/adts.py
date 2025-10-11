
# adts.py
import heapq
import itertools
from typing import Generic, TypeVar, Optional, List, Iterator, Tuple, Dict

T = TypeVar("T")


# ---------------- Stack (LIFO) ----------------
class Stack(Generic[T]):
    """
    LIFO (Last In, First Out) data structure for undo systems and history.
    Chosen for O(1) push/pop operations, ideal for reversible actions like game state snapshots.
    """
    def __init__(self):
        self._data: List[T] = []

    def push(self, item: T) -> None:
        self._data.append(item)

    def pop(self) -> T:
        return self._data.pop()

    def peek(self) -> Optional[T]:
        return self._data[-1] if self._data else None

    def is_empty(self) -> bool:
        return not self._data

    def __len__(self):
        return len(self._data)


# ---------------- Queue (FIFO) - circular buffer ----------------
class Queue(Generic[T]):
    """
    FIFO (First In, First Out) data structure with circular buffer for event queues or pre-scheduled states.
    Chosen for O(1) amortized enqueue/dequeue, efficient for bounded queues like weather prequeue.
    """
    def __init__(self, capacity: int = 64):
        self._buf: List[Optional[T]] = [None] * capacity
        self._head = 0
        self._tail = 0
        self._size = 0

    def _grow(self):
        old = self._buf
        newcap = max(2 * len(old), 8)
        self._buf = [None] * newcap
        for i in range(self._size):
            self._buf[i] = old[(self._head + i) % len(old)]
        self._head = 0
        self._tail = self._size

    def enqueue(self, item: T):
        if self._size == len(self._buf):
            self._grow()
        self._buf[self._tail] = item
        self._tail = (self._tail + 1) % len(self._buf)
        self._size += 1

    def dequeue(self) -> T:
        if self._size == 0:
            raise IndexError("dequeue from empty queue")
        item = self._buf[self._head]
        self._buf[self._head] = None
        self._head = (self._head + 1) % len(self._buf)
        self._size -= 1
        return item

    def peek(self) -> Optional[T]:
        return self._buf[self._head] if self._size else None

    def __len__(self):
        return self._size

    def is_empty(self):
        return self._size == 0


# ---------------- Doubly linked list / Deque ----------------
class _DLLNode(Generic[T]):
    __slots__ = ("val", "prev", "next")

    def __init__(self, val: T):
        self.val = val
        self.prev: Optional["_DLLNode[T]"] = None
        self.next: Optional["_DLLNode[T]"] = None


class Deque(Generic[T]):
    """
    Doubly-linked list deque for efficient bidirectional traversal and modifications.
    Chosen for O(1) append/pop at both ends, suitable for inventory management allowing forward/backward navigation.
    """
    def __init__(self):
        self.head: Optional[_DLLNode[T]] = None
        self.tail: Optional[_DLLNode[T]] = None
        self._size = 0

    def append(self, val: T):
        node = _DLLNode(val)
        if not self.tail:
            self.head = self.tail = node
        else:
            node.prev = self.tail
            self.tail.next = node
            self.tail = node
        self._size += 1

    def appendleft(self, val: T):
        node = _DLLNode(val)
        if not self.head:
            self.head = self.tail = node
        else:
            node.next = self.head
            self.head.prev = node
            self.head = node
        self._size += 1

    def pop(self) -> T:
        if not self.tail:
            raise IndexError("pop from empty deque")
        v = self.tail.val
        self.tail = self.tail.prev
        if self.tail:
            self.tail.next = None
        else:
            self.head = None
        self._size -= 1
        return v

    def popleft(self) -> T:
        if not self.head:
            raise IndexError("popleft from empty deque")
        v = self.head.val
        self.head = self.head.next
        if self.head:
            self.head.prev = None
        else:
            self.tail = None
        self._size -= 1
        return v

    def remove_node(self, node: _DLLNode[T]) -> T:
        """Elimina un nodo específico y retorna su valor."""
        if not node:
            raise ValueError("Cannot remove None node")

        # Si es el único nodo
        if self.head == node and self.tail == node:
            self.head = None
            self.tail = None
        # Si es la cabeza
        elif self.head == node:
            self.head = node.next
            if self.head:
                self.head.prev = None
        # Si es la cola
        elif self.tail == node:
            self.tail = node.prev
            if self.tail:
                self.tail.next = None
        # Nodo intermedio
        else:
            if node.prev:
                node.prev.next = node.next
            if node.next:
                node.next.prev = node.prev

        val = node.val
        self._size -= 1
        # limpiar referencias para ayudar al GC
        node.prev = node.next = None
        return val

    def __len__(self):
        return self._size

    def __iter__(self) -> Iterator[T]:
        cur = self.head
        while cur:
            yield cur.val
            cur = cur.next


# ---------------- Vector (dynamic array wrapper) ----------------
class Vector(Generic[T]):
    """
    Dynamic array wrapper for lists of coordinates or stats.
    Chosen for O(1) amortized append and O(1) random access, suitable for player positions or job lists.
    """
    def __init__(self, initial: Optional[List[T]] = None):
        self._data: List[T] = list(initial) if initial else []

    def push(self, item: T):
        self._data.append(item)

    def pop(self) -> T:
        return self._data.pop()

    def get(self, i: int) -> T:
        return self._data[i]

    def set(self, i: int, v: T):
        self._data[i] = v

    def __len__(self): return len(self._data)

    def to_list(self) -> List[T]: return list(self._data)


# ---------------- Priority Queue (min-heap) con soporte update/remove --------------
class PriorityQueue:
    """
    Min-heap priority queue with update/remove support for job scheduling.
    Chosen for O(log n) push/pop and efficient priority-based selection, using lazy deletion for updates.
    """
    def __init__(self):
        self._heap: List[Tuple[float, int, object]] = []
        self._entry_finder: Dict[object, Tuple[float, int, object]] = {}
        self._counter = itertools.count()
        self.REMOVED = "<removed-task>"

    def push(self, item: object, priority: float):
        if item in self._entry_finder:
            self.remove(item)
        count = next(self._counter)
        entry = (priority, count, item)
        self._entry_finder[item] = entry
        heapq.heappush(self._heap, entry)

    def remove(self, item: object):
        entry = self._entry_finder.pop(item, None)
        if entry:
            # mark as removed by replacing item with REMOVED
            removed_entry = (entry[0], entry[1], self.REMOVED)
            # push marker; actual stale entries will be skipped on pop
            heapq.heappush(self._heap, removed_entry)

    def pop(self) -> object:
        while self._heap:
            priority, count, item = heapq.heappop(self._heap)
            if item is self.REMOVED:
                continue
            # valid entry
            self._entry_finder.pop(item, None)
            return item, priority
        raise KeyError("pop from an empty priority queue")

    def peek(self):
        while self._heap:
            priority, count, item = self._heap[0]
            if item is self.REMOVED:
                heapq.heappop(self._heap)
                continue
            return item, priority
        return None

    def __len__(self):
        return len(self._entry_finder)
