from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Actor = Literal["human", "ai"]
BombResult = Literal["hit", "near", "weak", "none"]


@dataclass
class Submarine:
    id: int
    cells: list[tuple[int, int]]
    hit_cells: set[tuple[int, int]] = field(default_factory=set)
    sunk: bool = False
    sunk_by: Actor | None = None

    def contains(self, cell: tuple[int, int]) -> bool:
        return cell in self.cells

    def register_hit(self, cell: tuple[int, int], actor: Actor) -> bool:
        if cell in self.cells:
            self.hit_cells.add(cell)

        if not self.sunk and set(self.cells).issubset(self.hit_cells):
            self.sunk = True
            self.sunk_by = actor
            return True

        return False

    @property
    def orientation(self) -> str:
        xs = {x for x, _ in self.cells}
        return "vertical" if len(xs) == 1 else "horizontal"


@dataclass
class HistoryItem:
    turn: int
    action_index: int
    actor: Actor
    x: int
    y: int
    result: BombResult
    score_human: int
    score_ai: int
    sunk_submarine_id: int | None
    is_bonus_action: bool

    ai_probability_map: list[list[float]] | None = None
    ai_information_map: list[list[float]] | None = None
    ai_score_map: list[list[float]] | None = None
    ai_selected_reason: str | None = None

    def cell(self) -> tuple[int, int]:
        return (self.x, self.y)
