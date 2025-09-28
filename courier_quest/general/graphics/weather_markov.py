# graphics/weather_markov.py
"""
WeatherMarkov: Cadena de Markov para clima con transición suave, intensidad,
prequeue (cola) y historial (pila). Tiene API simple para integrarse con GameState.
"""

from __future__ import annotations
import time
import random
from typing import Dict, Optional, Callable, List, Any, Tuple


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t

class WeatherMarkov:
    DEFAULT_CONDITIONS = [
        "clear", "clouds", "rain_light", "rain", "storm", "fog", "wind", "heat", "cold", "snow"
    ]
    DEFAULT_BASE_MULTIPLIER = {
        "clear": 0.99, #ver si esto hay que ajustarlo a 1.00 o lo dejamos con valor actual. OJO
        "clouds": 0.98,
        "rain_light": 0.92,
        "rain": 0.85,
        "storm": 0.75,
        "fog": 0.90,
        "wind": 0.95,
        "heat": 0.90,
        "cold": 0.92,
        "snow": 0.88
    }

    def __init__(
        self,
        transition_matrix: Optional[Dict[str, Dict[str, float]]] = None,
        api: Optional[Any] = None,
        seed: Optional[int] = None,
        min_duration: int = 45,
        max_duration: int = 60,
        transition_smooth_seconds: float = 3.0,
        enable_history: bool = True,
        debug: bool = False,   #  nuevo parámetro
    ):
        self.rng = random.Random(seed)

        if debug:
            self.min_duration = 3
            self.max_duration = 5
        else:
            self.min_duration = int(min_duration)
            self.max_duration = int(max_duration)

        self.transition_smooth_seconds = float(transition_smooth_seconds)

        # Matriz: prioridad argumento > API (si trae algo) > default
        self.transition_matrix = transition_matrix or {}
        self.base_multiplier = dict(self.DEFAULT_BASE_MULTIPLIER)
        self.api = api
        if api is not None:
            try:
                api_weather = api.get_weather() or {}
                for key in ("transition_matrix", "transitions", "forecast", "series"):
                    candidate = api_weather.get(key)
                    if isinstance(candidate, dict) and candidate:
                        self.transition_matrix = candidate
                        break
            except Exception:
                pass

        if not self.transition_matrix:
            self.transition_matrix = self._default_transition_matrix()

        # estado inicial
        initial_choices = list(self.DEFAULT_CONDITIONS)
        self.current_condition: str = self.rng.choice(self.DEFAULT_CONDITIONS)

        self.current_intensity: float = round(self.rng.uniform(0.25, 1.0), 3)
        self.current_multiplier: float = self.base_multiplier.get(
            self.current_condition, 1.0
        ) * self.current_intensity

        # tiempo y duración
        self.start_time = time.time()
        self.duration = self._pick_duration()

        # transición (interpolación)
        self._transitioning = False
        self._transition_from_multiplier = self.current_multiplier
        self._transition_to_multiplier = self.current_multiplier
        self._transition_start_time = 0.0
        self._transition_duration = float(self.transition_smooth_seconds)

        # prequeue: cola FIFO de estados forzados
        self.prequeue: List[str] = []

        # history stack (lista simple LIFO)
        self.history: List[Tuple[str, float]] = [] if enable_history else []

        # callbacks
        self._subs: List[Callable[[Dict], None]] = []

    def _default_transition_matrix(self) -> Dict[str, Dict[str, float]]:
        """
        Genera una matriz de transición más aleatoria y no lineal.
        Cada condición tiene probabilidad de quedarse igual (~0.35)
        y el resto se reparte entre varios estados de forma balanceada.
        """
        m = {}
        all_states = self.DEFAULT_CONDITIONS

        for s in all_states:
            # Inicializar todas las transiciones con 0
            row = {t: 0.0 for t in all_states}

            # 35% de probabilidad de quedarse en el mismo estado
            row[s] = 0.35

            # El 65% restante se reparte entre los demás estados
            share = 0.65 / (len(all_states) - 1)
            for t in all_states:
                if t != s:
                    row[t] = share

            m[s] = row
        return m

    def _pick_duration(self) -> int:
        return self.rng.randint(self.min_duration, self.max_duration)

    def _choose_next_condition(self) -> str:
        if self.prequeue:
            return self.prequeue.pop(0)
        probs = self.transition_matrix.get(self.current_condition, {})
        if not probs:
            return self.rng.choice(list(self.transition_matrix.keys()))
        choices, weights = zip(*probs.items())
        if sum(weights) <= 0:
            return self.rng.choice(choices)
        return self.rng.choices(choices, weights=weights, k=1)[0]

    def _push_history(self, cond: str, intensity: float):
        if self.history is not None:
            self.history.append((cond, float(intensity)))

    def update(self, dt: float):
        now = time.time()

        if self._transitioning:
            t = (now - self._transition_start_time) / max(1e-9, self._transition_duration)
            if t >= 1.0:
                self.current_multiplier = self._transition_to_multiplier
                self._transitioning = False
            else:
                self.current_multiplier = lerp(
                    self._transition_from_multiplier, self._transition_to_multiplier, t
                )

        elapsed = now - self.start_time
        if (not self._transitioning) and (elapsed >= self.duration):
            next_cond = self._choose_next_condition()
            self._start_transition_to(next_cond)

    def _start_transition_to(self, new_condition: str):
        self._push_history(self.current_condition, self.current_intensity)

        self._transitioning = True
        self._transition_start_time = time.time()
        self._transition_duration = self.transition_smooth_seconds
        self._transition_from_multiplier = self.current_multiplier

        new_intensity = round(self.rng.uniform(0.25, 1.0), 3)
        new_multiplier = self.base_multiplier.get(new_condition, 1.0) * new_intensity

        self.current_condition = new_condition
        self.current_intensity = new_intensity
        self._transition_to_multiplier = new_multiplier

        self.start_time = time.time()
        self.duration = self._pick_duration()
        self._emit_state()

    def get_state(self) -> Dict[str, Any]:
        return {
            "condition": self.current_condition,
            "intensity": round(self.current_intensity, 3),
            "multiplier": round(self.current_multiplier, 3),
            "time_left": max(0, int(self.duration - (time.time() - self.start_time))),
            "transitioning": bool(self._transitioning),
        }

    def force_state(self, condition: str, intensity: Optional[float] = None, save_history: bool = True):
        if save_history:
            self._push_history(self.current_condition, self.current_intensity)
        self.current_condition = condition
        self.current_intensity = float(intensity) if intensity is not None else round(self.rng.uniform(0.25, 1.0), 3)
        self._transitioning = False
        self.current_multiplier = self.base_multiplier.get(condition, 1.0) * self.current_intensity
        self.start_time = time.time()
        self.duration = self._pick_duration()
        self._emit_state()

    def push_future(self, condition: str):
        self.prequeue.append(condition)

    def undo(self) -> Optional[Tuple[str, float]]:
        if not self.history:
            return None
        cond, intensity = self.history.pop()
        self.force_state(cond, intensity, save_history=False)
        return (cond, intensity)

    def subscribe(self, callback: Callable[[Dict], None]):
        if callback not in self._subs:
            self._subs.append(callback)

    def _emit_state(self):
        s = self.get_state()
        for cb in list(self._subs):
            try:
                cb(s)
            except Exception:
                pass

    def apply_to_game_state(self, game_state: Any):
        s = self.get_state()
        payload = {
            "condition": s["condition"],
            "intensity": s["intensity"],
            "multiplier": s["multiplier"],
            "time_left": s["time_left"],
            "transitioning": s["transitioning"],
        }
        try:
            if hasattr(game_state, "weather_state"):
                game_state.weather_state = payload
            elif isinstance(game_state, dict):
                game_state["weather_state"] = payload
        except Exception:
            pass
