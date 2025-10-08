from __future__ import annotations

from typing import Any


class PayoutUtils:
    def __init__(self, view: Any) -> None:
        self.view = view

    def get_job_payout(self, job_or_raw) -> float:
        v = self.view
        for name in ["payout", "pay", "reward", "price", "amount", "value", "money", "cash"]:
            if hasattr(job_or_raw, name):
                val = getattr(job_or_raw, name)
                if val is not None:
                    parsed = v._parse_money(val)
                    if parsed:
                        return parsed

        raw = getattr(job_or_raw, "raw", None)
        if isinstance(raw, dict):
            for k in ["payout", "pay", "reward", "price", "amount", "value", "money", "cash"]:
                if k in raw and raw[k] is not None:
                    parsed = v._parse_money(raw[k])
                    if parsed:
                        return parsed

        if isinstance(job_or_raw, dict):
            for k in ["payout", "pay", "reward", "price", "amount", "value", "money", "cash"]:
                if k in job_or_raw and job_or_raw[k] is not None:
                    parsed = v._parse_money(job_or_raw[k])
                    if parsed:
                        return parsed

        return 0.0


