# game_manager.py (modificaciones para integrar UndoSystem)
import time
from typing import Dict, Any
from .undo_system import UndoSystem  # ✅ Importar el nuevo sistema


class GameManager:
    def __init__(self):
        self.player_state = None
        self.job_manager = None
        self.score_system = None
        self.is_running = False
        self.start_time = 0
        self.undo_system = UndoSystem(max_steps=30)  # ✅ NUEVO: Sistema deshacer
        self.player_manager = None
        self.last_save_time = 0
        self.save_interval = 2.0  # Guardar estado cada 2 segundos

    def initialize_game(self, map_data, jobs_data, weather_data):
        """Inicializa todos los sistemas del juego"""
        from .player_state import PlayerState
        from .jobs_manager import JobManager

        self.player_state = PlayerState()
        self.job_manager = JobManager()

        # Inicializar componentes
        self.player_state.initialize_game(map_data, jobs_data, weather_data)

        # Cargar trabajos
        for job_data in jobs_data:
            self.job_manager.add_job_from_raw(job_data)

        self.start_time = time.time()
        self.is_running = True
        self.last_save_time = time.time()

        # ✅ Guardar estado inicial
        self.save_current_state()

    def update(self, delta_time: float):
        """Actualiza todos los sistemas del juego"""
        if not self.is_running:
            return

        # Actualizar player_state (que incluye weather_system internamente)
        self.player_state.update(delta_time)

        # ✅ Guardar estado periódicamente para deshacer
        current_time = time.time()
        if current_time - self.last_save_time >= self.save_interval:
            self.save_current_state()
            self.last_save_time = current_time

        # Verificar condiciones de victoria/derrota
        self._check_game_conditions()

    def save_current_state(self):
        """Guarda el estado actual para poder deshacer."""
        if not all([self.player_state, self.player_manager]):
            return

        try:
            state = self.undo_system.get_state_snapshot(
                self.player_state,
                self.player_state.inventory,
                self.player_state.weather_system,
                self.player_manager
            )
            self.undo_system.save_state(state)
        except Exception as e:
            print(f"Error guardando estado para deshacer: {e}")

    def undo_last_action(self) -> bool:
        """Deshace la última acción. Retorna True si fue exitoso."""
        if not self.undo_system.can_undo():
            print("No hay acciones para deshacer")
            return False

        try:
            previous_state = self.undo_system.undo()
            self.undo_system.restore_state(
                previous_state,
                self.player_state,
                self.player_state.inventory,
                self.player_state.weather_system,
                self.player_manager
            )
            print(f"Acción deshecha correctamente. Estados restantes: {self.undo_system.get_history_size()}")
            return True
        except Exception as e:
            print(f"Error al deshacer: {e}")
            return False

    def handle_player_movement(self, dx: int, dy: int) -> bool:
        """
        Maneja el movimiento del jugador con sistema de deshacer.
        Retorna True si el movimiento fue exitoso.
        """
        # ✅ Guardar estado antes del movimiento
        self.save_current_state()

        # Ejecutar movimiento
        if self.player_manager.move_by(dx, dy, self.player_state.map_data):
            print(f"Movimiento exitoso a ({self.player_manager.cell_x}, {self.player_manager.cell_y})")
            return True
        else:
            print("Movimiento no válido")
            # ✅ Descartar el estado guardado si el movimiento falló
            try:
                if self.undo_system.can_undo():
                    self.undo_system.undo()  # Descartar el estado recién guardado
            except:
                pass
            return False

    def _check_game_conditions(self):
        """Verifica condiciones de fin de juego"""
        goal = self.player_state.map_data.get("goal", 3000)

        # Victoria: alcanzar meta de ingresos
        if self.player_state.money >= goal:
            self.game_over("Victoria: ¡Alcanzaste la meta de ingresos!")

        # Derrota: reputación muy baja
        if self.player_state.reputation < 20:
            self.game_over("Derrota: Reputación muy baja")

        # Derrota: tiempo agotado
        if time.time() - self.start_time >= self.player_state.game_duration:
            self.game_over("Derrota: Tiempo agotado")

    def game_over(self, message: str):
        """Maneja el fin del juego"""
        self.is_running = False
        print(f"JUEGO TERMINADO: {message}")
        # ✅ Opcional: limpiar historial al terminar el juego
        self.undo_system.clear_history()