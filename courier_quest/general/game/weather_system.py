import random

class WeatherSystem:
    def __init__(self):
        self.current_weather = "clear"
        self.current_intensity = 0.0
        self.transition_matrix = {
            "clear": {"clear": 0.6, "clouds": 0.3, "rain": 0.1},
            "clouds": {"clear": 0.3, "clouds": 0.5, "rain": 0.2},
            "rain": {"clear": 0.2, "clouds": 0.4, "rain": 0.4}
        }
        self.weather_duration = 0
        self.current_duration = 0

    def initialize(self, weather_data):
        if weather_data and "bursts" in weather_data:
            self.bursts = weather_data["bursts"]
        else:
            # Datos por defecto si no hay datos de clima
            self.bursts = [{"duration_sec": 90, "condition": "clear", "intensity": 0.2}]

        self.current_burst_index = 0
        self.set_weather(self.bursts[0]["condition"], self.bursts[0]["intensity"])

    def update(self, delta_time):
        self.current_duration += delta_time
        if self.current_duration >= self.weather_duration:
            self.next_weather()

    def next_weather(self):
        # Implementar transición de clima con cadena de Markov
        pass

    def get_speed_multiplier(self):
        # Multiplicadores de velocidad según el clima
        multipliers = {
            "clear": 1.00,
            "clouds": 0.98,
            "rain": 0.85,
            "storm": 0.75,
            "fog": 0.88,
            "wind": 0.92,
            "heat": 0.90,
            "cold": 0.92
        }
        return multipliers.get(self.current_weather, 1.0)