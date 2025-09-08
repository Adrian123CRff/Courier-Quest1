from .inventory import Inventory
from .weather_system import WeatherSystem

class GameState:
    def __init__(self):
        self.map_data = None
        self.jobs_data = None
        self.weather_data = None
        self.reputation = 70
        self.stamina = 100
        self.money = 0
        self.inventory = Inventory()
        self.weather_system = WeatherSystem()
        self.current_time = 0
        self.game_duration= 15 * 60

    def initialize_game(self, map_data, jobs_data, weather_data):
        self.map_data = map_data
        self.jobs_data = jobs_data
        self.weather_data = weather_data
        self.weather_system.initialize(weather_data)

    def update(self, delta_time):
        self.current_time += delta_time
        self.weather_system.update(delta_time)
        self.update_stamina(delta_time)

        # Verificar condiciones de victoria/derrota
        if self.reputation < 20:
            self.game_over("Derrota: Reputación muy baja")
        if self.current_time >= self.game_duration:
            if self.money >= self.map_data.get("goal", 3000):
                self.game_over("Victoria")
            else:
                self.game_over("Derrota: No alcanzaste la meta de ingresos")

    def update_stamina(self, delta_time):
        # Lógica para actualizar la resistencia
        pass

    def game_over(self, message):
        # Manejar fin del juego
        print(f"Juego terminado: {message}")