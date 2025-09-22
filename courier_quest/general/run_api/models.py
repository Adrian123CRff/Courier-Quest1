#models.py

from dataclasses import dataclass, field
from typing import Any, List, Dict
@dataclass
class GameState:
    # Estado mínimo y serializable
    player: Dict[str, Any] = field(default_factory=dict)
    city_map: Dict[str, Any] = field(default_factory=dict)   # <-- aquí va el JSON del mapa (tiles, width, height...)
    orders: List[Dict[str, Any]] = field(default_factory=list)
    weather_state: Dict[str, Any] = field(default_factory=dict)
    reputation: int = 70

    def to_dict(self) -> Dict[str, Any]:
        return {
            "player": self.player,
            "city_map": self.city_map,
            "orders": self.orders,
            "weather_state": self.weather_state,
            "reputation": self.reputation,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GameState":
        return cls(
            player=d.get("player", {}),
            city_map=d.get("city_map", {}),
            orders=d.get("orders", []),
            weather_state=d.get("weather_state", {}),
            reputation=d.get("reputation", 70)
        )