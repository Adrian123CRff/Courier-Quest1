#weather_coordinator.py
from __future__ import annotations

from typing import Any


class WeatherCoordinator:
    def __init__(self, view: Any) -> None:
        self.view = view

    def update_and_render(self, dt: float) -> None:
        v = self.view
        try:
            if v._freeze_weather:
                ws = v._resume_weather_state or (
                    v.state.get("weather_state") if isinstance(v.state, dict) else getattr(v.state, "weather_state", {})
                ) or {}
                v.weather_renderer.update(dt, ws)
            else:
                v.weather_markov.update(dt)
                v.weather_markov.apply_to_game_state(v.state)
                ws = v.state.get("weather_state", {}) if isinstance(v.state, dict) else getattr(v.state, "weather_state", {})
                v.weather_renderer.update(dt, ws)
        except Exception as e:
            print(f"Error actualizando clima: {e}")

    def get_current_condition_name(self) -> str:
        v = self.view
        try:
            if hasattr(v.weather_markov, "current_condition"):
                return v.weather_markov.current_condition
            return v.weather_markov.get_state().get("condition", "clear")
        except Exception:
            return "clear"


