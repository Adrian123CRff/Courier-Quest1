# weather_system.py
import random


class WeatherSystem:
    def __init__(self):
        self.current_weather = "clear"
        self.current_intensity = 0.0
        self.target_weather = "clear"
        self.target_intensity = 0.0
        self.transition_time = 4.0  # 3-5 segundos según PDF
        self.transition_progress = 0.0
        self.is_transitioning = False
        self.weather_duration = 0
        self.current_duration = 0

        # Matriz de transición completa con todas las condiciones climáticas
        self.transition_matrix = {
            "clear": {"clear": 0.6, "clouds": 0.2, "rain_light": 0.1, "rain": 0.05, "storm": 0.0, "fog": 0.05,
                      "wind": 0.0, "heat": 0.0, "cold": 0.0},
            "clouds": {"clear": 0.3, "clouds": 0.4, "rain_light": 0.15, "rain": 0.05, "storm": 0.0, "fog": 0.1,
                       "wind": 0.0, "heat": 0.0, "cold": 0.0},
            "rain_light": {"clear": 0.1, "clouds": 0.3, "rain_light": 0.3, "rain": 0.2, "storm": 0.05, "fog": 0.05,
                           "wind": 0.0, "heat": 0.0, "cold": 0.0},
            "rain": {"clear": 0.05, "clouds": 0.15, "rain_light": 0.2, "rain": 0.3, "storm": 0.2, "fog": 0.05,
                     "wind": 0.05, "heat": 0.0, "cold": 0.0},
            "storm": {"clear": 0.0, "clouds": 0.1, "rain_light": 0.15, "rain": 0.3, "storm": 0.3, "fog": 0.05,
                      "wind": 0.1, "heat": 0.0, "cold": 0.0},
            "fog": {"clear": 0.2, "clouds": 0.3, "rain_light": 0.1, "rain": 0.1, "storm": 0.0, "fog": 0.3, "wind": 0.0,
                    "heat": 0.0, "cold": 0.0},
            "wind": {"clear": 0.2, "clouds": 0.2, "rain_light": 0.1, "rain": 0.1, "storm": 0.1, "fog": 0.0, "wind": 0.3,
                     "heat": 0.0, "cold": 0.0},
            "heat": {"clear": 0.3, "clouds": 0.2, "rain_light": 0.0, "rain": 0.0, "storm": 0.0, "fog": 0.0, "wind": 0.1,
                     "heat": 0.4, "cold": 0.0},
            "cold": {"clear": 0.2, "clouds": 0.3, "rain_light": 0.1, "rain": 0.0, "storm": 0.0, "fog": 0.1, "wind": 0.1,
                     "heat": 0.0, "cold": 0.2}
        }

        # Multiplicadores de velocidad para cada clima
        self.speed_multipliers = {
            "clear": 1.00,
            "clouds": 0.98,
            "rain_light": 0.90,
            "rain": 0.85,
            "storm": 0.75,
            "fog": 0.88,
            "wind": 0.92,
            "heat": 0.90,
            "cold": 0.92
        }

    def update(self, delta_time):
        """
        Actualiza el sistema de clima.
        """
        if self.is_transitioning:
            # Actualizar transición
            self.transition_progress += delta_time / self.transition_time
            if self.transition_progress >= 1.0:
                # Transición completa
                self.current_weather = self.target_weather
                self.current_intensity = self.target_intensity
                self.is_transitioning = False
                self.transition_progress = 0.0
        else:
            # Actualizar duración del clima actual
            self.current_duration += delta_time
            if self.current_duration >= self.weather_duration:
                # Cambiar a nuevo clima
                self.next_weather()

    def next_weather(self):
        """
        Selecciona el siguiente clima usando la cadena de Markov.
        """
        # Obtener probabilidades para el clima actual
        probs = self.transition_matrix.get(self.current_weather, {"clear": 1.0})

        # Seleccionar nuevo clima
        r = random.random()
        cumulative = 0.0
        new_weather = self.current_weather

        for weather, prob in probs.items():
            cumulative += prob
            if r <= cumulative:
                new_weather = weather
                break

        # Generar nueva intensidad (0.2-0.8)
        new_intensity = random.uniform(0.2, 0.8)

        # Iniciar transición
        self.target_weather = new_weather
        self.target_intensity = new_intensity
        self.is_transitioning = True
        self.transition_progress = 0.0

        # Establecer nueva duración (45-60 segundos según PDF)
        self.weather_duration = random.uniform(45, 60)
        self.current_duration = 0

    def get_speed_multiplier(self):
        """
        Obtiene el multiplicador de velocidad actual, considerando transiciones.
        """
        if not self.is_transitioning:
            return self.speed_multipliers.get(self.current_weather, 1.0)

        # Durante transición, interpolar entre valores
        current_mult = self.speed_multipliers.get(self.current_weather, 1.0)
        target_mult = self.speed_multipliers.get(self.target_weather, 1.0)

        return current_mult + (target_mult - current_mult) * self.transition_progress

    def initialize(self, weather_data):
        if weather_data and "bursts" in weather_data:
            self.bursts = weather_data["bursts"]
        else:
            # Datos por defecto si no hay datos de clima
            self.bursts = [{"duration_sec": 90, "condition": "clear", "intensity": 0.2}]

        self.current_burst_index = 0
        self.set_weather(self.bursts[0]["condition"], self.bursts[0]["intensity"])

    def set_weather(self, condition, intensity):
        """
        Establece el clima actual y su intensidad
        """
        self.current_weather = condition
        self.current_intensity = intensity
        self.weather_duration = self.bursts[self.current_burst_index].get("duration_sec", 90)
        self.current_duration = 0

# ELIMINAR la segunda clase WeatherSystem duplicada