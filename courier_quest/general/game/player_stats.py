# player_stats.py
import time
from typing import Dict, Any


class PlayerStats:
    """
    Gestiona las estadísticas del jugador: resistencia y reputación.
    """

    # Estados de resistencia
    STAMINA_STATES = {
        "normal": {"min": 30, "max": 100, "multiplier": 1.0},
        "tired": {"min": 10, "max": 30, "multiplier": 0.8},
        "exhausted": {"min": 0, "max": 10, "multiplier": 0.0}
    }

    # Umbrales de reputación
    REPUTATION_THRESHOLDS = {
        "excellent": 90,  # +5% pago
        "good": 85,  # mitad de penalización en primera tardanza
        "defeat": 20  # derrota inmediata si es menor
    }

    def __init__(self):
        # Resistencia
        self.stamina = 100.0
        self.stamina_recovery_rate = 5.0  # puntos por segundo en reposo
        self.stamina_recovery_rate_rest_point = 10.0  # puntos por segundo en punto de descanso
        self.last_rest_time = time.time()
        self.is_resting = False
        self.is_at_rest_point = False

        # Reputación
        self.reputation = 70
        self.consecutive_on_time_deliveries = 0
        self.first_late_delivery_of_day = True

    def update(self, delta_time: float, is_moving: bool, is_at_rest_point: bool = False,
               inventory_weight: float = 0.0, current_weather: str = "clear"):
        """
        Actualiza las estadísticas del jugador basado en el tiempo transcurrido.
        """
        self.is_at_rest_point = is_at_rest_point

        # Actualizar resistencia
        if is_moving:
            # Consumo base por celda
            stamina_consumption_base = 0.5

            # Extra por peso del inventario
            weight_extra = 0.0
            if inventory_weight > 3.0:
                weight_extra = 0.2 * (inventory_weight - 3.0)

            # Extra por clima adverso
            weather_extra = 0.0
            if current_weather in ["rain", "wind"]:
                weather_extra = 0.1
            elif current_weather == "storm":
                weather_extra = 0.3
            elif current_weather == "heat":
                weather_extra = 0.2

            # Consumo total
            stamina_consumption = (stamina_consumption_base + weight_extra + weather_extra) * delta_time * 10
            self.stamina = max(0, self.stamina - stamina_consumption)
            self.is_resting = False
        else:
            # Recuperar resistencia en reposo
            if self.is_at_rest_point:
                recovery_rate = self.stamina_recovery_rate_rest_point
            else:
                recovery_rate = self.stamina_recovery_rate

            self.stamina = min(100, self.stamina + recovery_rate * delta_time)
            self.is_resting = True

        # Actualizar tiempo de descanso
        if self.is_resting:
            self.last_rest_time = time.time()

    def get_stamina_state(self):
        """Retorna el estado actual de resistencia del jugador."""
        for state, values in self.STAMINA_STATES.items():
            if values["min"] <= self.stamina <= values["max"]:
                return state
        return "normal"

    def get_speed_multiplier(self):
        """Retorna el multiplicador de velocidad basado en la resistencia."""
        state = self.get_stamina_state()
        return self.STAMINA_STATES[state]["multiplier"]

    def update_reputation(self, event_type: str, data: Dict[str, Any] = None) -> int:
        """
        Actualiza la reputación basado en eventos del juego.
        """
        data = data or {}
        reputation_change = 0

        if event_type == "delivery_on_time":
            reputation_change = 3
            self.consecutive_on_time_deliveries += 1

            # Bonificación por racha de 3 entregas sin penalización
            if self.consecutive_on_time_deliveries >= 3:
                reputation_change += 2
                self.consecutive_on_time_deliveries = 0

        elif event_type == "delivery_early":
            # Entrega temprana (≥20% antes)
            early_percent = data.get("early_percent", 20)
            if early_percent >= 20:
                reputation_change = 5
                self.consecutive_on_time_deliveries += 1

        elif event_type == "delivery_late":
            # Tarde ≤30s: -2; 31–120s: -5; >120s: -10
            seconds_late = data.get("seconds_late", 0)

            if seconds_late <= 30:
                reputation_change = -2
            elif seconds_late <= 120:
                reputation_change = -5
            else:
                reputation_change = -10

            # Primera tardanza del día a mitad de penalización si reputación ≥85
            if self.first_late_delivery_of_day and self.reputation >= 85:
                reputation_change = reputation_change // 2
                self.first_late_delivery_of_day = False

            self.consecutive_on_time_deliveries = 0

        elif event_type == "cancel_order":
            reputation_change = -4
            self.consecutive_on_time_deliveries = 0

        elif event_type == "lose_package":
            reputation_change = -6
            self.consecutive_on_time_deliveries = 0

        # Aplicar cambio de reputación
        self.reputation += reputation_change
        self.reputation = max(0, min(100, self.reputation))

        return reputation_change

    def get_payment_multiplier(self) -> float:
        """Retorna el multiplicador de pago basado en la reputación."""
        return 1.05 if self.reputation >= self.REPUTATION_THRESHOLDS["excellent"] else 1.0

    def is_game_over(self) -> bool:
        """Verifica si el juego debe terminar por baja reputación."""
        return self.reputation < self.REPUTATION_THRESHOLDS["defeat"]

    def consume_stamina(self, base_cost: float, weight: float, weather_penalty: float) -> bool:
        """
        Consume resistencia al moverse por una celda.
        """
        # Verificar si puede moverse
        if self.get_stamina_state() == "exhausted":
            return False

        # Calcular costo total
        weight_penalty = max(0, 0.2 * (weight - 3)) if weight > 3 else 0
        total_cost = base_cost + weight_penalty + weather_penalty

        # Consumir resistencia
        self.stamina -= total_cost
        self.stamina = max(0, self.stamina)

        return self.stamina > 0