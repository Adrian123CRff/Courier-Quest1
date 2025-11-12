#money_utils.py
from __future__ import annotations

import re
from typing import Any


class MoneyUtils:
    def __init__(self, view: Any) -> None:
        self.view = view

    def parse_money(self, v) -> float:
        try:
            if v is None:
                return 0.0
            if isinstance(v, (int, float)):
                return float(v)
            s = str(v)
            m = re.search(r"-?\d+(?:[.,]\d+)?", s)
            if not m:
                return 0.0
            num = m.group(0).replace(",", ".")
            return float(num)
        except Exception:
            return 0.0

    def get_state_money(self) -> float:
        v = self.view
        if isinstance(v.state, dict):
            return self.parse_money(v.state.get("money", 0))
        return self.parse_money(getattr(v.state, "money", 0))

    def set_state_money(self, value: float) -> None:
        v = self.view
        try:
            val = self.parse_money(value)
            if isinstance(v.state, dict):
                v.state["money"] = val
            else:
                setattr(v.state, "money", val)
        except Exception as e:
            print(f"[MONEY] Error set_state_money: {e}")

    def add_money(self, amount: float) -> None:
        v = self.view
        amt = self.parse_money(amount)
        if amt <= 0:
            return
        try:
            current = self.get_state_money()
            self.set_state_money(current + amt)
            print(f"[MONEY] +${amt:.2f}  -> total ${self.get_state_money():.2f}")
        except Exception as e:
            print(f"[MONEY] Error actualizando state: {e}")

        # Best-effort mirror to other systems
        try:
            if v.game_manager:
                for attr in ["money", "cash", "balance"]:
                    if hasattr(v.game_manager, attr):
                        try:
                            old = self.parse_money(getattr(v.game_manager, attr))
                            setattr(v.game_manager, attr, old + amt)
                        except Exception:
                            pass
        except Exception:
            pass

        try:
            ss = v.score_system
            if ss:
                for name in ["add_money", "award", "add_cash"]:
                    if hasattr(ss, name):
                        try:
                            getattr(ss, name)(float(amt))
                        except Exception:
                            pass
        except Exception:
            pass


