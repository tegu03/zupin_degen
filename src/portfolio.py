"""Saldo virtual sederhana untuk paper trading."""
from dataclasses import dataclass


@dataclass
class Portfolio:
    balance_usd: float
    open_positions: int = 0

    def can_open_position(self, size_usd: float, max_positions: int) -> bool:
        return self.open_positions < max_positions and self.balance_usd >= size_usd

    def open_position(self, size_usd: float) -> None:
        self.balance_usd -= size_usd
        self.open_positions += 1

    def close_position(self, returned_usd: float) -> None:
        self.balance_usd += returned_usd
        self.open_positions = max(0, self.open_positions - 1)
