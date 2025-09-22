# undo_manager.py
from collections import deque
import pickle

class UndoManager:
    def __init__(self, max_steps=10):
        self._stack = deque(maxlen=max_steps)

    def push(self, state):
        # guardamos snapshot serializado para proteger contra cambios mutables
        self._stack.append(pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL))

    def can_undo(self) -> bool:
        return len(self._stack) > 0

    def undo(self):
        if not self.can_undo():
            return None
        data = self._stack.pop()
        return pickle.loads(data)