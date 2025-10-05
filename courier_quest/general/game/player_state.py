# player_state.py
import time
from typing import Optional
from .inventory import Inventory
from .player_stats import PlayerStats
from .weather_markov import WeatherMarkov


class PlayerState:
    def __init__(self):
        # Datos generales del juego
        self.map_data = {}
        self.jobs_data = []
        self.weather_data = {}
        self.money = 0.0
        self.current_time = 0.0
        self.game_duration = None  # Se establecerá dinámicamente
        self.start_time_epoch = time.time()
        self.at_rest_point = False
        self.player_x = 0
        self.player_y = 0

        # Subsistemas
        self.inventory = Inventory()
        self.weather_system = WeatherMarkov()
        self.player_stats = PlayerStats()
    # =======================
    # Inicialización del juego
    # =======================
    def initialize_game(self, map_data, jobs_data, weather_data, game_duration=None):
        """Inicializa el estado del juego con datos del mapa, trabajos y clima."""
        self.map_data = map_data or {}
        self.jobs_data = jobs_data or []
        self.weather_data = weather_data or {}

        self.game_duration = game_duration or self.map_data.get("max_time")
        if self.game_duration is None:
            raise ValueError("❌ No se pudo determinar game_duration")

        print(f"[PLAYER_STATE] Inicializado:")
        print(f"  - Duración del juego: {self.game_duration}s")
        print(f"  - Meta de ingresos: {self.map_data.get('goal', 'No especificada')}")

        try:
            # Configuración inicial del clima si hay datos de API
            if weather_data and "bursts" in weather_data:
                first_burst = weather_data["bursts"][0]
                self.weather_system.force_state(
                    first_burst.get("condition", "clear"),
                    first_burst.get("intensity", 0.5)
                )
        except Exception as e:
            print(f"Error inicializando weather system: {e}")
            self.weather_system.force_state("clear", 0.5)

    # =======================
    # Actualización por frame
    # =======================
    def update(self, delta_time: float):
        """Actualiza todos los sistemas del juego cada frame."""
        self.current_time += delta_time

        # Actualizar clima
        try:
            self.weather_system.update(delta_time)
        except Exception as e:
            print(f"Error actualizando weather system: {e}")

        # Obtener datos necesarios
        inventory_weight = getattr(self.inventory, "current_weight", 0.0)
        weather_state = self.weather_system.get_state()
        current_weather = weather_state.get("condition", "clear")

        # Actualizar estadísticas del jugador
        self.player_stats.update(delta_time, False, self.at_rest_point, inventory_weight, current_weather)

        # Verificar condiciones de victoria o derrota
        if self.player_stats.is_game_over():
            self.game_over("Derrota: Reputación muy baja")
        elif self.current_time >= self.game_duration:
            goal = self.map_data.get("goal", 3000)
            if self.money >= goal:
                self.game_over("Victoria: ¡Alcanzaste la meta de ingresos!")
            else:
                self.game_over("Derrota: No alcanzaste la meta de ingresos")

    # =======================
    # Métodos auxiliares
    # =======================
    def update_stamina(self, delta_time: float):
        """Reduce la stamina al moverse o realizar acciones."""
        weight = getattr(self.inventory, "current_weight", 0.0)
        current_weather = getattr(self.weather_system, "current_weather", "clear")
        self.player_stats.update(delta_time, True, self.at_rest_point, weight, current_weather)

    def recover_stamina_over_time(self, delta_seconds: float):
        """Recupera stamina gradualmente (por descanso o inactividad)."""
        weight = getattr(self.inventory, "current_weight", 0.0)
        current_weather = getattr(self.weather_system, "current_weather", "clear")
        self.player_stats.update(delta_seconds, False, self.at_rest_point, weight, current_weather)

    def consume_stamina_for_move(self):
        """Consume una pequeña cantidad de stamina por movimiento."""
        weight = getattr(self.inventory, "current_weight", 0.0)
        current_weather = getattr(self.weather_system, "current_weather", "clear")
        self.player_stats.update(0.1, True, self.at_rest_point, weight, current_weather)

    def update_reputation(self, event_type: str, data: dict = None) -> int:
        """Ajusta la reputación del jugador según un evento."""
        return self.player_stats.update_reputation(event_type, data)

    def get_payment_multiplier(self) -> float:
        """Obtiene el multiplicador de pago basado en reputación."""
        return self.player_stats.get_payment_multiplier()

    @staticmethod
    def game_over(message: str):
        """Maneja el fin del juego (puede integrarse con la UI)."""
        print(f"Juego terminado: {message}")

    # =======================
    # Propiedades útiles
    # =======================
    @property
    def stamina(self):
        return self.player_stats.stamina

    @property
    def reputation(self):
        return self.player_stats.reputation

    def current_weather_condition(self):
        return self.weather_system.get_state().get("condition", "clear")

    @property
    def weather_multiplier(self):
        return self.weather_system.get_state().get("multiplier", 1.0)

    # =======================
    # Serialización (guardar/cargar)
    # =======================
    def to_dict(self):
        """Convierte el estado completo en un diccionario serializable."""
        return {
            "map_data": self.map_data,
            "jobs_data": self.jobs_data,
            "weather_data": self.weather_data,
            "money": self.money,
            "stamina": self.stamina,
            "reputation": self.reputation,
            "current_time": self.current_time,
            "game_duration": self.game_duration,
            "at_rest_point": self.at_rest_point,
            "player_x": self.player_x,
            "player_y": self.player_y,
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Reconstruye un PlayerState desde un diccionario (para carga de partidas)."""
        state = cls()
        state.map_data = data.get("map_data", {})
        state.jobs_data = data.get("jobs_data", [])
        state.weather_data = data.get("weather_data", {})
        state.money = data.get("money", 0.0)
        state.current_time = data.get("current_time", 0.0)
        state.game_duration = data.get("game_duration", 15 * 60)
        state.at_rest_point = data.get("at_rest_point", False)
        state.player_x = data.get("player_x", 0)
        state.player_y = data.get("player_y", 0)

        # Reconstruir stamina y reputación
        state.player_stats.stamina = data.get("stamina", 100)
        state.player_stats.reputation = data.get("reputation", 50)

        return state
