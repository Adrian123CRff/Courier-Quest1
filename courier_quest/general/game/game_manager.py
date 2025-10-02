# game_manager.py
"""
GameManager - Coordina todos los sistemas del juego
"""
import time
from typing import Dict, Any


class GameManager:
    def __init__(self):
        self.player_state = None
        self.job_manager = None
        self.weather_system = None
        self.score_system = None
        self.is_running = False
        self.start_time = 0

    def initialize_game(self, map_data, jobs_data, weather_data):
        """Inicializa todos los sistemas del juego"""
        from .player_state import PlayerState
        from .jobs_manager import JobManager
        from .weather_system import WeatherSystem

        self.player_state = PlayerState()
        self.job_manager = JobManager()
        self.weather_system = WeatherSystem()

        # Inicializar componentes
        self.player_state.initialize_game(map_data, jobs_data, weather_data)
        self.weather_system.initialize(weather_data)

        # Cargar trabajos
        for job_data in jobs_data:
            self.job_manager.add_job_from_raw(job_data)

        self.start_time = time.time()
        self.is_running = True

    def update(self, delta_time: float):
        """Actualiza todos los sistemas del juego"""
        if not self.is_running:
            return

        self.player_state.update(delta_time)
        self.weather_system.update(delta_time)

        # Verificar condiciones de victoria/derrota
        self._check_game_conditions()

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