# game/player_stats.py
import time
from typing import Dict, Any


class PlayerStats:
    """
    Gestión de stamina y reputación.

    - Consumo por celda: 0.5 base + penalizaciones por peso y clima (se invoca en Player).
    - Recuperación: +3 puntos cada 1 segundo cuando está quieto y sin input activo.
    - Estados:
        - Normal: stamina > 30 -> multiplier = 1.0
        - Tired: 0 < stamina <= 30 -> multiplier = 0.8
        - Exhausted: stamina <= 0 -> no puede moverse
    """

    REPUTATION_THRESHOLDS = {
        "excellent": 90,
        "good": 85,
        "defeat": 20
    }

    def __init__(self):
        self.stamina: float = 100.0

        # Cuando la stamina llega a 0, activamos un bloqueo que impide
        # cualquier movimiento hasta que la stamina se recupere por encima
        # del umbral EXHAUSTION_UNLOCK_THRESHOLD (>= 30).
        self.EXHAUSTION_UNLOCK_THRESHOLD: float = 30.0
        self._exhaustion_locked: bool = False

        # Recuperación discreta: +3 puntos por cada 1.0s acumulado
        self.RECOVER_PER_TICK: float = 3.0
        self.RECOVER_TICK_SEC: float = 1.0
        self._idle_recover_accum: float = 0.0

        # flags y estado
        self.is_resting = False
        self.is_at_rest_point = False
        self.last_rest_time = time.time()

        # reputación
        self.reputation: int = 70
        self.consecutive_on_time_deliveries = 0
        self.first_late_delivery_of_day = True
        # historial de reputación para auditoría
        self.reputation_history = []

    def update(self,
               delta_time: float,
               is_moving: bool,
               is_at_rest_point: bool = False,
               inventory_weight: float = 0.0,
               current_weather: str = "clear",
               input_active: bool = False):
        """
        Actualiza stamina:
        - Si is_moving: no recupera y resetea acumulador.
        - Si no se mueve y input_active == False: acumula tiempo y por cada RECOVER_TICK_SEC recupera RECOVER_PER_TICK.
        - Si input_active == True: no recupera y acumulador se resetea.
        """
        self.is_at_rest_point = is_at_rest_point

        if is_moving:
            # mientras se mueve no recupera y resetea acumulador
            self._idle_recover_accum = 0.0
            self.is_resting = False
            return

        # quieto:
        if not input_active:
            # acumular tiempo inactivo y aplicar incrementos enteros cada RECOVER_TICK_SEC
            self._idle_recover_accum += delta_time
            # cuantos ticks completos pasaron
            ticks = int(self._idle_recover_accum // self.RECOVER_TICK_SEC)
            if ticks > 0:
                self._idle_recover_accum -= ticks * self.RECOVER_TICK_SEC
                self.stamina = min(100.0, self.stamina + ticks * self.RECOVER_PER_TICK)
            self.is_resting = True
            self.last_rest_time = time.time()
        else:
            # actividad de entrada evita recuperación y resetea acumulador
            self._idle_recover_accum = 0.0
            self.is_resting = False

        # Si está bloqueado por agotamiento, desbloquear únicamente cuando
        # la stamina alcance o supere el umbral de desbloqueo.
        try:
            if self._exhaustion_locked and self.stamina >= self.EXHAUSTION_UNLOCK_THRESHOLD:
                self._exhaustion_locked = False
        except Exception:
            pass

    def get_stamina_state(self) -> str:
        """
        Retorna:
         - "normal"  => stamina > 30
         - "tired"   => 0 < stamina <= 30
         - "exhausted" => stamina <= 0
        """
        if self.stamina <= 0.0:
            return "exhausted"
        if self.stamina > 30.0:
            return "normal"
        return "tired"

    def get_speed_multiplier(self) -> float:
        state = self.get_stamina_state()
        if state == "normal":
            return 1.0
        if state == "tired":
            return 0.8
        return 0.0

    def consume_stamina(self, base_cost: float = 0.5, weight: float = 0.0, weather_penalty: float = 0.0, intensity: float = 1.0) -> bool:
        """
        Consume stamina al completar una celda.
        Devuelve True si antes de consumir había > 0 stamina.
        """
        # Si ya está a 0 -> no puede moverse ni consumir
        if self.stamina <= 0.0:
            return False

        weight_penalty = 0.0
        if weight > 3.0:
            weight_penalty = 0.2 * (weight - 3.0)

        total_cost = base_cost + weight_penalty + float(weather_penalty) * intensity
        self.stamina = max(0.0, self.stamina - total_cost)
        # Si al consumir llegamos a 0 -> activar bloqueo de agotamiento
        if self.stamina <= 0.0:
            self.stamina = 0.0
            self._exhaustion_locked = True
        return True

    def can_move(self) -> bool:
        """Determina si el jugador puede iniciar movimiento.

        Comportamiento requerido:
        - Si el jugador está bloqueado por agotamiento (había llegado a 0),
          no puede moverse hasta que la stamina sea >= EXHAUSTION_UNLOCK_THRESHOLD.
        - En condiciones normales (no bloqueado), puede moverse si tiene
          algo de stamina (> 0.0).
        """
        try:
            if self._exhaustion_locked:
                return False
        except Exception:
            pass
        return self.stamina > 0.0

    # reputación, helpers y reset (idénticos a la versión anterior)
    def update_reputation(self, event_type: str, data: Dict[str, Any] = None) -> int:
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
                # aplicar bonus de racha en tempranas también
                if self.consecutive_on_time_deliveries >= 3:
                    reputation_change += 2
                    self.consecutive_on_time_deliveries = 0
        elif event_type == "delivery_late":
            seconds_late = data.get("seconds_late", 0)
            if seconds_late <= 30:
                reputation_change = -2
            elif seconds_late <= 120:
                reputation_change = -5
            else:
                reputation_change = -10
            if self.first_late_delivery_of_day and self.reputation >= 85:
                reputation_change = int(reputation_change / 2)
                self.first_late_delivery_of_day = False
            self.consecutive_on_time_deliveries = 0
        elif event_type == "cancel_order":
            reputation_change = -4
            self.consecutive_on_time_deliveries = 0
        elif event_type == "lose_package":
            reputation_change = -6
            self.consecutive_on_time_deliveries = 0

        self.reputation += reputation_change
        self.reputation = max(0, min(100, self.reputation))
        try:
            # registrar en historial
            self.reputation_history.append({
                "timestamp": time.time(),
                "event": event_type,
                "change": reputation_change,
                "reputation": self.reputation,
                "data": dict(data) if isinstance(data, dict) else data,
            })
        except Exception:
            pass
        return reputation_change

    def get_payment_multiplier(self) -> float:
        return 1.05 if self.reputation >= self.REPUTATION_THRESHOLDS["excellent"] else 1.0

    def is_game_over(self) -> bool:
        return self.reputation < self.REPUTATION_THRESHOLDS["defeat"]

    def reset(self):
        self.stamina = 100.0
        self._exhaustion_locked = False
        self.reputation = 70
        self.consecutive_on_time_deliveries = 0
        self.first_late_delivery_of_day = True
        self._idle_recover_accum = 0.0
        try:
            self.reputation_history.clear()
        except Exception:
            self.reputation_history = []
