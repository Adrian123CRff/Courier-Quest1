import json
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ScoreEntry:
    """Representa una entrada en la tabla de récords."""
    player_name: str
    score: int
    reputation: float
    deliveries_completed: int
    date: str

    def to_dict(self) -> Dict[str, Any]:
        """Convierte la entrada a un diccionario para serialización."""
        return {
            "player_name": self.player_name,
            "score": self.score,
            "reputation": self.reputation,
            "deliveries_completed": self.deliveries_completed,
            "date": self.date
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScoreEntry':
        """Crea una entrada a partir de un diccionario."""
        return cls(
            player_name=data.get("player_name", "Unknown"),
            score=data.get("score", 0),
            reputation=data.get("reputation", 0.0),
            deliveries_completed=data.get("deliveries_completed", 0),
            date=data.get("date", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )


class ScoreSystem:
    """Sistema de puntuación y tabla de récords."""

    def __init__(self, save_dir: str = "saves"):
        self.save_dir = save_dir
        self.scores_file = os.path.join(save_dir, "highscores.json")
        self.current_score = 0
        self.deliveries_completed = 0
        self.on_time_deliveries = 0
        self.late_deliveries = 0
        self.total_earnings = 0.0

        # Asegurar que el directorio existe
        os.makedirs(save_dir, exist_ok=True)

        # Cargar récords existentes o crear archivo si no existe
        self.high_scores = self._load_high_scores()

    def _load_high_scores(self) -> List[ScoreEntry]:
        """Carga la tabla de récords desde el archivo."""
        if not os.path.exists(self.scores_file):
            return []

        try:
            with open(self.scores_file, 'r') as f:
                data = json.load(f)
                return [ScoreEntry.from_dict(entry) for entry in data]
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_high_scores(self) -> None:
        """Guarda la tabla de récords en el archivo."""
        with open(self.scores_file, 'w') as f:
            data = [entry.to_dict() for entry in self.high_scores]
            json.dump(data, f, indent=2)

    def add_points(self, points: int) -> None:
        """Añade puntos a la puntuación actual."""
        self.current_score += points

    def add_delivery(self, on_time: bool, earnings: float) -> None:
        """Registra una entrega completada."""
        self.deliveries_completed += 1
        self.total_earnings += earnings

        if on_time:
            self.on_time_deliveries += 1
            # Bonus por entrega a tiempo
            self.add_points(100)
        else:
            self.late_deliveries += 1
            # Puntos básicos por entrega tardía
            self.add_points(25)

    def calculate_final_score(self, reputation: float) -> int:
        """Calcula la puntuación final basada en entregas y reputación."""
        # Bonus por reputación
        reputation_bonus = int(reputation * 10)

        # Bonus por porcentaje de entregas a tiempo
        on_time_percentage = 0
        if self.deliveries_completed > 0:
            on_time_percentage = (self.on_time_deliveries / self.deliveries_completed) * 100
        on_time_bonus = int(on_time_percentage * 5)

        # Bonus por ganancias totales
        earnings_bonus = int(self.total_earnings / 10)

        # Puntuación final
        final_score = self.current_score + reputation_bonus + on_time_bonus + earnings_bonus
        return final_score

    def add_high_score(self, player_name: str, reputation: float) -> bool:
        """
        Añade una nueva puntuación a la tabla de récords.
        Retorna True si la puntuación entró en el top 10.
        """
        final_score = self.calculate_final_score(reputation)

        # Crear nueva entrada
        new_entry = ScoreEntry(
            player_name=player_name,
            score=final_score,
            reputation=reputation,
            deliveries_completed=self.deliveries_completed,
            date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        # Añadir a la lista y ordenar
        self.high_scores.append(new_entry)
        self.high_scores.sort(key=lambda x: x.score, reverse=True)

        # Mantener solo los 10 mejores
        if len(self.high_scores) > 10:
            self.high_scores = self.high_scores[:10]

        # Guardar cambios
        self._save_high_scores()

        # Verificar si la nueva puntuación está en el top 10
        return any(entry.player_name == player_name and entry.score == final_score for entry in self.high_scores)

    def get_high_scores(self, limit: int = 10) -> List[ScoreEntry]:
        """Obtiene las mejores puntuaciones, limitadas a 'limit'."""
        return self.high_scores[:min(limit, len(self.high_scores))]

    def reset_current_score(self) -> None:
        """Reinicia la puntuación actual y estadísticas."""
        self.current_score = 0
        self.deliveries_completed = 0
        self.on_time_deliveries = 0
        self.late_deliveries = 0
        self.total_earnings = 0.0

    def get_player_rank(self, score: int) -> int:
        """Obtiene la posición del jugador en la tabla de récords."""
        for i, entry in enumerate(self.high_scores):
            if score >= entry.score:
                return i + 1
        return len(self.high_scores) + 1


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
        self.bursts = []
        self.current_burst_index = 0

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

        Args:
            condition: Condición climática (clear, clouds, rain, etc.)
            intensity: Intensidad del clima (0.0 a 1.0)
        """
        self.current_weather = condition
        self.current_intensity = intensity
        self.weather_duration = self.bursts[self.current_burst_index].get("duration_sec", 90)
        self.current_duration = 0

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
