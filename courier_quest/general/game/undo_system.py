# undo_system.py
import copy
from typing import Dict, Any, List
from game.adts import Stack


class UndoSystem:
    """
    Sistema para deshacer acciones del jugador.
    Guarda estados anteriores del juego en una pila.
    """

    def __init__(self, max_steps: int = 50):
        self.undo_stack = Stack()
        self.max_steps = max_steps
        self.current_step = 0

    def set_max_steps(self, new_max: int):
        """Cambia el número máximo de pasos de deshacer."""
        if new_max < 1:
            new_max = 1
        self.max_steps = new_max
        # Si hay más estados que el nuevo límite, eliminar los antiguos
        while self.undo_stack.__len__() > self.max_steps:
            self._remove_oldest()

    def save_state(self, game_state: Dict[str, Any]):
        """Guarda el estado actual del juego en la pila de deshacer."""
        if self.undo_stack.__len__() >= self.max_steps:
            # Eliminar el estado más antiguo si excedemos el límite
            self._remove_oldest()

        # Guardar copia profunda del estado
        state_copy = self._deep_copy_state(game_state)
        self.undo_stack.push(state_copy)
        self.current_step += 1

    def undo(self) -> Dict[str, Any]:
        """Restaura el estado anterior del juego."""
        if self.undo_stack.is_empty():
            raise ValueError("No hay estados anteriores para restaurar")

        previous_state = self.undo_stack.pop()
        self.current_step -= 1
        return previous_state

    def undo_n_steps(self, n: int) -> bool:
        """Restaura los últimos N estados del juego."""
        if n <= 0:
            return False
        if self.undo_stack.is_empty():
            return False

        # Limitar N al número de estados disponibles
        available_steps = len(self.undo_stack)
        steps_to_undo = min(n, available_steps)

        try:
            for _ in range(steps_to_undo):
                self.undo()
            return True
        except Exception:
            return False

    def can_undo(self) -> bool:
        """Verifica si hay estados anteriores para restaurar."""
        return not self.undo_stack.is_empty()

    def get_state_snapshot(self, player_state, inventory, weather_system, player_manager) -> Dict[str, Any]:
        """Crea un snapshot del estado actual del juego."""
        # Obtener estado del clima desde WeatherMarkov
        weather_state = weather_system.get_state()

        return {
            'player_position': (player_manager.cell_x, player_manager.cell_y),
            'player_pixel_position': (player_manager.pixel_x, player_manager.pixel_y),
            'money': player_state.money,
            'stamina': player_state.player_stats.stamina,
            'reputation': player_state.player_stats.reputation,
            'inventory': [copy.copy(job) for job in inventory._deque_values()],
            'inventory_weight': inventory.current_weight,
            'current_time': player_state.current_time,
            'weather_state': {
                'current_condition': weather_state.get('condition', 'clear'),
                'current_intensity': weather_state.get('intensity', 0.5),
                'current_multiplier': weather_state.get('multiplier', 1.0),
                'history': copy.copy(getattr(weather_system, 'history', [])),
                'prequeue': copy.copy(getattr(weather_system, 'prequeue', []))
            },
            'step_count': self.current_step
        }

    def restore_state(self, state: Dict[str, Any], player_state, inventory, weather_system, player_manager):
        """Restaura un estado guardado en el juego."""
        # Restaurar posición del jugador
        player_manager.cell_x, player_manager.cell_y = state['player_position']
        player_manager.pixel_x, player_manager.pixel_y = state['player_pixel_position']
        player_manager.target_pixel_x, player_manager.target_pixel_y = state['player_pixel_position']
        player_manager.moving = False
        try:
            player_manager.sprite.center_x = player_manager.pixel_x
            player_manager.sprite.center_y = player_manager.pixel_y
        except Exception:
            pass

        # Restaurar estadísticas
        player_state.money = state['money']
        player_state.player_stats.stamina = state['stamina']
        player_state.player_stats.reputation = state['reputation']
        player_state.current_time = state['current_time']

        # Restaurar inventario
        # Necesitamos reconstruir el inventario usando los métodos existentes
        inventory_items = state['inventory']
        inventory.deque = Stack()  # Reiniciar inventario
        inventory.current_weight = 0.0

        for job in inventory_items:
            inventory.add(job)

        # Restaurar clima WeatherMarkov
        weather_state_data = state['weather_state']
        weather_system.force_state(
            weather_state_data['current_condition'],
            weather_state_data['current_intensity']
        )
        # Restaurar historial y cola si existen
        if hasattr(weather_system, 'history'):
            weather_system.history = weather_state_data.get('history', [])
        if hasattr(weather_system, 'prequeue'):
            weather_system.prequeue = weather_state_data.get('prequeue', [])

        self.current_step = state['step_count']

    def _deep_copy_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Crea una copia profunda del estado."""
        return copy.deepcopy(state)

    def _remove_oldest(self):
        """Elimina el estado más antiguo (implementación básica)."""
        # Para una implementación más eficiente, podríamos usar deque en lugar de Stack
        temp_states = []
        while not self.undo_stack.is_empty():
            temp_states.append(self.undo_stack.pop())

        # Eliminar el más antiguo (primero en la lista)
        if temp_states:
            temp_states.pop(0)

        # Volver a poner los estados en la pila
        for state in reversed(temp_states):
            self.undo_stack.push(state)

    def clear_history(self):
        """Limpia todo el historial de deshacer."""
        self.undo_stack = Stack()
        self.current_step = 0

    def get_history_size(self) -> int:
        """Retorna cuántos estados hay guardados."""
        return len(self.undo_stack)