# score_system.py - CORREGIDO
import json
import os
import time
import tempfile
import shutil
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ScoreEntry:
    """Representa una entrada en la tabla de récords."""
    player_name: str
    score: int
    money_earned: float
    reputation: float
    deliveries_completed: int
    on_time_deliveries: int
    date: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "player_name": self.player_name,
            "score": self.score,
            "money_earned": self.money_earned,
            "reputation": self.reputation,
            "deliveries_completed": self.deliveries_completed,
            "on_time_deliveries": self.on_time_deliveries,
            "date": self.date
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScoreEntry':
        return cls(
            player_name=data.get("player_name", "Unknown"),
            score=data.get("score", 0),
            money_earned=data.get("money_earned", 0.0),
            reputation=data.get("reputation", 0.0),
            deliveries_completed=data.get("deliveries_completed", 0),
            on_time_deliveries=data.get("on_time_deliveries", 0),
            date=data.get("date", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )


class ScoreSystem:
    """Sistema de puntuación según especificaciones del PDF"""

    def __init__(self, save_dir: str = "saves", game_duration: int = 900):  # ✅ PARÁMETRO DINÁMICO
        self.save_dir = save_dir
        self.scores_file = os.path.join(save_dir, "highscores.json")

        # Estadísticas de la partida actual
        self.total_money = 0.0
        self.deliveries_completed = 0
        self.on_time_deliveries = 0
        self.cancellations = 0
        self.lost_packages = 0
        self.game_start_time = 0
        self.game_duration = game_duration  # ✅ USAR VALOR DINÁMICO

        os.makedirs(save_dir, exist_ok=True)
        self.high_scores = self._load_high_scores()

    def _load_high_scores(self) -> List[ScoreEntry]:
        if not os.path.exists(self.scores_file):
            return []
        try:
            with open(self.scores_file, 'r') as f:
                data = json.load(f)
                return [ScoreEntry.from_dict(entry) for entry in data]
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_high_scores(self) -> None:
        """Atomic write to prevent corruption."""
        data = [entry.to_dict() for entry in self.high_scores]
        tmp_name = None
        try:
            with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=os.path.dirname(self.scores_file)) as tmp:
                json.dump(data, tmp, indent=2)
                tmp_name = tmp.name
            shutil.move(tmp_name, self.scores_file)
        except Exception as e:
            if tmp_name and os.path.exists(tmp_name):
                os.remove(tmp_name)
            raise

    def start_game(self):
        """Inicia el temporizador del juego"""
        self.game_start_time = time.time()
        self.total_money = 0.0
        self.deliveries_completed = 0
        self.on_time_deliveries = 0
        self.cancellations = 0
        self.lost_packages = 0

    def record_delivery(self, money_earned: float, on_time: bool):
        """Registra una entrega completada"""
        self.total_money += money_earned
        self.deliveries_completed += 1
        if on_time:
            self.on_time_deliveries += 1

    def record_cancellation(self):
        """Registra una cancelación"""
        self.cancellations += 1

    def record_lost_package(self):
        """Registra un paquete perdido"""
        self.lost_packages += 1

    def calculate_final_score(self, final_reputation: float) -> int:
        """
        Calcula el puntaje final según el PDF:
        score_base = suma de pagos * pay_mult (por reputación alta)
        bonus_tiempo = +X si terminas antes del 20% del tiempo restante
        penalizaciones = -Y por cancelaciones/caídas
        """
        # Multiplicador por reputación alta
        pay_mult = 1.05 if final_reputation >= 90 else 1.0
        score_base = self.total_money * pay_mult

        # Bonus por tiempo (si termina antes del 20% del tiempo restante)
        current_time = time.time()
        time_elapsed = current_time - self.game_start_time
        time_bonus = 0

        if time_elapsed < self.game_duration * 0.8:  # Terminó antes del 80% del tiempo
            time_bonus = self.total_money * 0.2  # 20% bonus

        # Penalizaciones
        penalties = (self.cancellations * 50) + (self.lost_packages * 100)

        # Puntuación final
        final_score = score_base + time_bonus - penalties
        return int(max(0, final_score))

    def add_high_score(self, player_name: str, final_reputation: float) -> bool:
        """Añade un nuevo puntaje alto"""
        final_score = self.calculate_final_score(final_reputation)

        new_entry = ScoreEntry(
            player_name=player_name,
            score=final_score,
            money_earned=self.total_money,
            reputation=final_reputation,
            deliveries_completed=self.deliveries_completed,
            on_time_deliveries=self.on_time_deliveries,
            date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        self.high_scores.append(new_entry)
        self.high_scores.sort(key=lambda x: x.score, reverse=True)

        if len(self.high_scores) > 10:
            self.high_scores = self.high_scores[:10]

        self._save_high_scores()
        return any(entry.player_name == player_name and entry.score == final_score
                   for entry in self.high_scores)

    def get_high_scores(self, limit: int = 10) -> List[ScoreEntry]:
        return self.high_scores[:min(limit, len(self.high_scores))]

    def get_current_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas actuales para mostrar en UI"""
        current_time = time.time() - self.game_start_time if self.game_start_time > 0 else 0
        return {
            "total_money": self.total_money,
            "deliveries_completed": self.deliveries_completed,
            "on_time_deliveries": self.on_time_deliveries,
            "cancellations": self.cancellations,
            "lost_packages": self.lost_packages,
            "time_elapsed": current_time,
            "time_remaining": max(0, self.game_duration - current_time)
        }