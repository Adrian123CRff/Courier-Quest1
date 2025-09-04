# general/graphics/sprites.py
import arcade


class CourierSprite(arcade.Sprite):
    def __init__(self, game_state):
        super().__init__("assets/sprites/courier.png", scale=0.5)
        self.game_state = game_state
        self.center_x = 100  # Posición inicial
        self.center_y = 100

    def update(self):
        # Actualizar posición basada en la velocidad
        speed = self.calculate_speed()
        # ... lógica de movimiento

    def calculate_speed(self):
        # Calcular velocidad basada en los factores del juego
        base_speed = 3  # celdas/segundo
        weather_multiplier = self.game_state.weather_system.get_speed_multiplier()
        weight_multiplier = max(0.8, 1 - 0.03 * self.game_state.inventory.get_total_weight())
        reputation_multiplier = 1.03 if self.game_state.reputation >= 90 else 1.0
        stamina_multiplier = 1.0 if self.game_state.stamina > 30 else 0.8

        return base_speed * weather_multiplier * weight_multiplier * reputation_multiplier * stamina_multiplier
