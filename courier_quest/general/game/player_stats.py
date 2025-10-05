# player_stats.py - PARCHE COMPLETO
import time
from typing import Dict, Any


class PlayerStats:
    """
    Gestión de stamina y reputación según especificaciones del PDF.

    - Consumo por celda: 0.5 base + penalizaciones por peso y clima
    - Recuperación: +1 por segundo cuando está quieto y sin input activo
    - Estados: Normal (>30), Cansado (10-30), Exhausto (≤10)
    """

    STAMINA_STATES = {
        "normal": {"min": 30, "max": 100, "multiplier": 1.0},
        "tired": {"min": 10, "max": 30, "multiplier": 0.8},
        "exhausted": {"min": 0, "max": 10, "multiplier": 0.0}
    }

    REPUTATION_THRESHOLDS = {
        "excellent": 90,
        "good": 85,
        "defeat": 20
    }

    def __init__(self):
        self.stamina: float = 100.0

        # Recuperación: 1 punto cada RECOVER_INTERVAL segundos cuando quieto y sin input
        self.RECOVER_INTERVAL: float = 1.0
        self._idle_recover_accum: float = 0.0

        # flags
        self.is_resting = False
        self.is_at_rest_point = False
        self.last_rest_time = time.time()

        # reputación
        self.reputation: int = 70
        self.consecutive_on_time_deliveries = 0
        self.first_late_delivery_of_day = True

    def update(self,
               delta_time: float,
               is_moving: bool,
               is_at_rest_point: bool = False,
               inventory_weight: float = 0.0,
               current_weather: str = "clear",
               input_active: bool = False):
        """
        Actualiza stamina:
        - Si is_moving: no recupera (consumo por celda se hace explícitamente al completar la celda).
        - Si no se mueve y input_active == False: acumula tiempo y recupera 1 punto por RECOVER_INTERVAL.
        - Si hay input_active (aunque no se mueva), NO recupera.
        """
        self.is_at_rest_point = is_at_rest_point

        if is_moving:
            # mientras se mueve no recupera y resetea acumulador
            self._idle_recover_accum = 0.0
            self.is_resting = False
            return

        # quieto:
        if not input_active:
            self._idle_recover_accum += delta_time
            while self._idle_recover_accum >= self.RECOVER_INTERVAL:
                self._idle_recover_accum -= self.RECOVER_INTERVAL
                self.stamina = min(100.0, self.stamina + 1.0)
        else:
            # actividad de entrada evita recuperación
            self._idle_recover_accum = 0.0

        self.is_resting = True
        if self.is_resting:
            self.last_rest_time = time.time()

    def get_stamina_state(self) -> str:
        for state, values in self.STAMINA_STATES.items():
            if values["min"] <= self.stamina <= values["max"]:
                return state
        return "normal"

    def get_speed_multiplier(self) -> float:
        state = self.get_stamina_state()
        return self.STAMINA_STATES[state]["multiplier"]

    def consume_stamina(self, base_cost: float = 0.5, weight: float = 0.0, weather_penalty: float = 0.0) -> bool:
        """
        Consume stamina cuando se completa una celda según especificaciones del PDF:
        - base_cost: 0.5 por celda
        - weight: peso del inventario (penalización si > 3)
        - weather_penalty: penalización numérica por clima

        Devuelve True si antes de consumir había > 0 stamina.
        """
        # Si ya está a 0 -> no puede moverse / no consumir más
        if self.stamina <= 0.0:
            return False

        # Penalización por peso (según PDF: -0.2 por cada unidad sobre 3)
        weight_penalty = 0.0
        if weight > 3.0:
            weight_penalty = 0.2 * (weight - 3.0)

        # Penalización por clima ya viene calculada desde player_manager
        total_cost = base_cost + weight_penalty + weather_penalty

        # restar (no bajar de 0)
        self.stamina = max(0.0, self.stamina - total_cost)
        return True

    def update_reputation(self, event_type: str, data: Dict[str, Any] = None) -> int:
        """
        Actualiza la reputación según especificaciones del PDF:
        - Entrega a tiempo: +3
        - Entrega temprana (≥20% antes): +5
        - Tarde ≤30s: -2; 31-120s: -5; >120s: -10
        - Cancelar pedido aceptado: -4
        - Perder/expirar paquete: -6
        - Racha de 3 entregas sin penalización: +2
        """
        data = data or {}
        reputation_change = 0

        if event_type == "delivery_on_time":
            reputation_change = 3
            self.consecutive_on_time_deliveries += 1
            if self.consecutive_on_time_deliveries >= 3:
                reputation_change += 2
                self.consecutive_on_time_deliveries = 0

        elif event_type == "delivery_early":
            early_percent = data.get("early_percent", 20)
            if early_percent >= 20:
                reputation_change = 5
                self.consecutive_on_time_deliveries += 1

        elif event_type == "delivery_late":
            seconds_late = data.get("seconds_late", 0)
            if seconds_late <= 30:
                reputation_change = -2
            elif seconds_late <= 120:
                reputation_change = -5
            else:
                reputation_change = -10

            # Mitigar primera penalización si reputación alta
            if self.first_late_delivery_of_day and self.reputation >= 85:
                reputation_change = reputation_change // 2  # Mitigar a la mitad
                self.first_late_delivery_of_day = False

            self.consecutive_on_time_deliveries = 0

        elif event_type == "cancel_order":
            reputation_change = -4
            self.consecutive_on_time_deliveries = 0

        elif event_type == "lose_package":
            reputation_change = -6
            self.consecutive_on_time_deliveries = 0

        # Aplicar cambio y mantener en rango 0-100
        old_reputation = self.reputation
        self.reputation += reputation_change
        self.reputation = max(0, min(100, self.reputation))

        return reputation_change

    def get_payment_multiplier(self) -> float:
        """+5% de pago si reputación ≥90 según PDF"""
        return 1.05 if self.reputation >= self.REPUTATION_THRESHOLDS["excellent"] else 1.0

    def is_game_over(self) -> bool:
        """Derrota inmediata si reputación < 20"""
        return self.reputation < self.REPUTATION_THRESHOLDS["defeat"]

    def get_stamina_percentage(self) -> float:
        """Retorna el porcentaje de stamina (0.0 a 1.0)"""
        return self.stamina / 100.0

    def can_move(self) -> bool:
        """Verifica si el jugador puede moverse (stamina > 0)"""
        return self.stamina > 0.0

    def reset(self):
        """Reinicia las estadísticas del jugador"""
        self.stamina = 100.0
        self.reputation = 70
        self.consecutive_on_time_deliveries = 0
        self.first_late_delivery_of_day = True
        self._idle_recover_accum = 0.0