# player_state.py
import time
from typing import Optional
from .inventory import Inventory
from .weather_system import WeatherSystem
from .player_stats import PlayerStats  # Importación corregida


class PlayerState:
    def __init__(self):
        self.map_data = {}
        self.jobs_data = []
        self.weather_data = {}
        self.money = 0.0
        self.inventory = Inventory()
        self.weather_system = WeatherSystem()
        self.current_time = 0.0
        self.game_duration = 15 * 60
        self.at_rest_point = False
        self.start_time_epoch = time.time()

        # Usamos PlayerStats para gestionar stamina y reputación
        self.player_stats = PlayerStats()

    def initialize_game(self, map_data, jobs_data, weather_data):
        self.map_data = map_data or {}
        self.jobs_data = jobs_data or []
        self.weather_data = weather_data or {}
        try:
            self.weather_system.initialize(weather_data)
        except Exception:
            pass

    def update(self, delta_time: float):
        self.current_time += delta_time
        try:
            self.weather_system.update(delta_time)
        except Exception:
            pass

        # Actualizar estadísticas del jugador
        inventory_weight = getattr(self.inventory, "current_weight", 0.0)
        current_weather = getattr(self.weather_system, "current_weather", "clear")
        self.player_stats.update(delta_time, False, self.at_rest_point, inventory_weight, current_weather)

        # Verificar condiciones de victoria/derrota
        if self.player_stats.is_game_over():
            self.game_over("Derrota: Reputación muy baja")
        if self.current_time >= self.game_duration:
            goal = self.map_data.get("goal", 3000)
            if self.money >= goal:
                self.game_over("Victoria")
            else:
                self.game_over("Derrota: No alcanzaste la meta de ingresos")

    def update_stamina(self, delta_time):
        # Delegamos a PlayerStats
        weight = getattr(self.inventory, "current_weight", 0.0)
        current_weather = getattr(self.weather_system, "current_weather", "clear")
        self.player_stats.update(delta_time, True, self.at_rest_point, weight, current_weather)

    def recover_stamina_over_time(self, delta_seconds: float):
        """
        Método de compatibilidad. La recuperación ahora se maneja en PlayerStats.update
        """
        # Delegamos a PlayerStats
        weight = getattr(self.inventory, "current_weight", 0.0)
        current_weather = getattr(self.weather_system, "current_weather", "clear")
        self.player_stats.update(delta_seconds, False, self.at_rest_point, weight, current_weather)

    def update_reputation(self, event_type: str, data: dict = None) -> int:
        return self.player_stats.update_reputation(event_type, data)

    def get_payment_multiplier(self) -> float:
        return self.player_stats.get_payment_multiplier()

    @staticmethod
    def game_over(message: str):
        # Manejar fin del juego (puedes reemplazar print por UI/modal)
        print(f"Juego terminado: {message}")

    # ---------- stamina helpers ----------
    def consume_stamina_for_move(self):
        """
        Método de compatibilidad. Delega el consumo de resistencia a PlayerStats.
        Llamar *cuando el jugador completa el movimiento a una celda*.
        """
        # Delegamos a PlayerStats
        weight = getattr(self.inventory, "current_weight", 0.0)
        current_weather = getattr(self.weather_system, "current_weather", "clear")

        # Consumir stamina con movimiento=True
        self.player_stats.update(0.1, True, self.at_rest_point, weight, current_weather)

    # Propiedades para acceso directo
    @property
    def stamina(self):
        return self.player_stats.stamina

    @property
    def reputation(self):
        return self.player_stats.reputation

# Eliminar la clase PlayerStats duplicada que estaba al final del archivo