"""RL exposure hooks for sokoban-tui.

Headless adapter — bypasses Textual entirely. An RL "step" is one
movement attempt (noop ignored). Pack/level is fixed at construction.

State vector layout (flat float32, padded to STATE_DIM=200):
    Board is a (H, W) grid encoded as 4 channels flattened per cell:
        wall, goal, box, player.
    We pack a 10x10 window centered on the player so state is size
    consistent across levels. 10*10*4 = 400 dims — too large; reduce
    by packing a single int per cell with one-hot over 5 classes
    (floor, wall, goal, box, box-on-goal, player, player-on-goal)
    → compressed to a single normalized int per cell.

Final layout (total = 100 + 8 = 108):
    [0:100]  10x10 cell window centered on player, each cell in [0,6]/6
    [100:102] player (x,y) / (W,H) global position
    [102]    boxes_on_goal / num_boxes
    [103]    num_boxes / 16  (clipped)
    [104]    moves / 500  (clipped)
    [105]    pushes / 500  (clipped)
    [106]    solved (0/1)
    [107]    1.0 (bias)

Reward shaping:
    +1 per new box placed on a goal (delta)
    +10 on full solve
    -0.01 per step
    -1 per box removed from goal (regression penalty)

Terminal: solved OR time-cap (handled by env).
"""

from __future__ import annotations

import numpy as np

from .engine import Game, FLOOR, WALL, GOAL, OUTSIDE
from .levels import PACKS, Pack


STATE_DIM = 108
WINDOW = 10  # 10x10 window around player


def _cell_class(g: Game, x: int, y: int) -> int:
    """0=outside, 1=floor, 2=wall, 3=goal, 4=box, 5=box-on-goal, 6=player."""
    if not (0 <= x < g.width and 0 <= y < g.height):
        return 0
    c = g.cells[y][x]
    if c == OUTSIDE:
        return 0
    has_player = (g.player == (x, y))
    has_box = (x, y) in g.boxes
    on_goal = (x, y) in g.goals
    if has_player:
        return 6
    if has_box:
        return 5 if on_goal else 4
    if c == WALL:
        return 2
    if on_goal:
        return 3
    return 1


class RLGame:
    """Headless sokoban driver."""

    def __init__(self, pack_name: str | None = None, level_idx: int = 0):
        self.pack: Pack = (
            next(p for p in PACKS if p.name == pack_name)
            if pack_name else PACKS[0]
        )
        self.level_idx = max(0, min(level_idx, len(self.pack) - 1))
        self.game: Game = self.pack[self.level_idx].load()
        self._prev_on_goal = self._boxes_on_goal()
        self._prev_moves = 0

    def _boxes_on_goal(self) -> int:
        return sum(1 for b in self.game.boxes if b in self.game.goals)

    def reset(self) -> None:
        self.game = self.pack[self.level_idx].load()
        self._prev_on_goal = self._boxes_on_goal()
        self._prev_moves = 0

    def step_move(self, dx: int, dy: int) -> None:
        if self.game.is_solved():
            return
        self.game.move(dx, dy)

    # RL surface ------------------------------------------------------

    def game_state_vector(self) -> np.ndarray:
        g = self.game
        vec = np.zeros(STATE_DIM, dtype=np.float32)
        px, py = g.player
        half = WINDOW // 2
        idx = 0
        for wy in range(WINDOW):
            for wx in range(WINDOW):
                gx = px - half + wx
                gy = py - half + wy
                vec[idx] = _cell_class(g, gx, gy) / 6.0
                idx += 1
        vec[100] = px / max(1, g.width)
        vec[101] = py / max(1, g.height)
        on_goal = self._boxes_on_goal()
        n_boxes = max(1, len(g.boxes))
        vec[102] = on_goal / n_boxes
        vec[103] = min(16, len(g.boxes)) / 16.0
        vec[104] = min(500, g.moves) / 500.0
        vec[105] = min(500, g.pushes) / 500.0
        vec[106] = 1.0 if g.is_solved() else 0.0
        vec[107] = 1.0
        return vec

    def game_reward(self) -> float:
        on_goal = self._boxes_on_goal()
        delta = on_goal - self._prev_on_goal
        reward = float(delta)  # +1 per new box on goal, -1 per removal
        if self.game.is_solved():
            reward += 10.0
        reward -= 0.01  # per-step penalty (we're called once per step)
        self._prev_on_goal = on_goal
        self._prev_moves = self.game.moves
        return reward

    def is_terminal(self) -> bool:
        return bool(self.game.is_solved())


def state_vector_len() -> int:
    return STATE_DIM
