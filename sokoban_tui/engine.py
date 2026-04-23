"""Pure-Python Sokoban engine.

Level is a list[list[str]] — each cell one of `FLOOR` `WALL` `GOAL`.
Boxes + player are tracked separately as (x,y) so we can render a goal
under a box without stringly-typed "box-on-goal" bookkeeping.

All coordinates are (x, y) with y going DOWN (screen convention).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Terrain cells. Boxes/player are layered on top.
FLOOR = " "
WALL = "#"
GOAL = "."
# Characters that mean "no tile — render as blank space, not a floor."
# Everything outside the reachable region is OUTSIDE (transparent).
OUTSIDE = "~"


@dataclass
class MoveResult:
    """Outcome of a `Game.move()` call."""
    moved: bool = False    # player actually changed cell
    pushed: bool = False   # a box moved (implies moved)
    won: bool = False      # state is now a solution
    reason: str = ""       # short diag string if !moved

    def __bool__(self) -> bool:  # "did anything happen?"
        return self.moved


@dataclass
class Game:
    """A playable Sokoban position.

    The `cells` grid holds ONLY terrain (wall / floor / goal). Boxes are
    in a set; the player is a single (x, y). This makes undo trivial
    (just restore the three fields) and keeps render cheap.
    """
    cells: list[list[str]]         # cells[y][x] — terrain only
    width: int
    height: int
    player: tuple[int, int]
    boxes: set[tuple[int, int]]
    goals: set[tuple[int, int]]
    moves: int = 0
    pushes: int = 0
    # Each entry: (player_xy, {box_xy: new_xy} | None, pushed_bool).
    # We store per-move delta rather than full state — cheaper and all we
    # need to unwind one step.
    _undo: list[tuple[tuple[int, int], tuple[tuple[int, int], tuple[int, int]] | None]] = field(
        default_factory=list
    )
    # Name/metadata from the pack, if any.
    title: str = ""

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------

    @classmethod
    def parse(cls, text: str, title: str = "") -> "Game":
        """Parse an XSB level block (one level, no comments/headers).

        Recognized glyphs (all per XSB spec):
          #  wall
          space  floor
          -  floor (alt)
          _  floor (alt)
          .  goal
          $  box
          *  box-on-goal
          @  player
          +  player-on-goal
        """
        raw = [line.rstrip("\r\n") for line in text.splitlines() if line.strip()]
        if not raw:
            raise ValueError("empty level")
        width = max(len(r) for r in raw)
        height = len(raw)
        # Pad every row to width with OUTSIDE sentinels so indexing is
        # uniform. We'll later flood-fill "inside" from the player to
        # demote any leaked floor back to OUTSIDE for clean rendering.
        cells: list[list[str]] = [[OUTSIDE] * width for _ in range(height)]
        player: tuple[int, int] | None = None
        boxes: set[tuple[int, int]] = set()
        goals: set[tuple[int, int]] = set()

        for y, row in enumerate(raw):
            for x, ch in enumerate(row):
                if ch == "#":
                    cells[y][x] = WALL
                elif ch in (" ", "-", "_"):
                    cells[y][x] = FLOOR
                elif ch == ".":
                    cells[y][x] = GOAL
                    goals.add((x, y))
                elif ch == "$":
                    cells[y][x] = FLOOR
                    boxes.add((x, y))
                elif ch == "*":
                    cells[y][x] = GOAL
                    goals.add((x, y))
                    boxes.add((x, y))
                elif ch == "@":
                    cells[y][x] = FLOOR
                    player = (x, y)
                elif ch == "+":
                    cells[y][x] = GOAL
                    goals.add((x, y))
                    player = (x, y)
                # Any other char (stray, encoding garbage) → OUTSIDE.

        if player is None:
            raise ValueError("level has no player (@ or +)")
        if not boxes:
            raise ValueError("level has no boxes")
        if len(boxes) != len(goals):
            raise ValueError(
                f"level has {len(boxes)} boxes but {len(goals)} goals — must match"
            )

        # Flood fill reachable floor from the player — anything that was
        # space but NOT reachable is OUTSIDE (cosmetic: xsb files often
        # have stray spaces beyond the room bounds).
        reachable = _flood_inside(cells, player)
        for y in range(height):
            for x in range(width):
                if cells[y][x] == FLOOR and (x, y) not in reachable:
                    cells[y][x] = OUTSIDE

        return cls(
            cells=cells, width=width, height=height,
            player=player, boxes=boxes, goals=goals, title=title,
        )

    # ------------------------------------------------------------------
    # rules
    # ------------------------------------------------------------------

    def cell(self, x: int, y: int) -> str:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.cells[y][x]
        return OUTSIDE

    def is_solved(self) -> bool:
        # Short-circuit: if counts match and every box sits on a goal.
        return self.boxes == self.goals

    def move(self, dx: int, dy: int) -> MoveResult:
        """Try to move the player by (dx, dy). One of (-1,0)(1,0)(0,-1)(0,1).

        Rules (classic XSokoban):
          - Target cell must be FLOOR or GOAL (not WALL / OUTSIDE).
          - If target has a box, the cell BEYOND it must be FLOOR/GOAL
            and empty of another box; then box and player both move.
          - Otherwise just the player moves.
          - Any no-op increments nothing.
        """
        px, py = self.player
        tx, ty = px + dx, py + dy
        t = self.cell(tx, ty)
        if t in (WALL, OUTSIDE):
            return MoveResult(reason="wall")

        pushed_from_to: tuple[tuple[int, int], tuple[int, int]] | None = None
        if (tx, ty) in self.boxes:
            bx, by = tx + dx, ty + dy
            b = self.cell(bx, by)
            if b in (WALL, OUTSIDE) or (bx, by) in self.boxes:
                return MoveResult(reason="blocked")
            pushed_from_to = ((tx, ty), (bx, by))
            self.boxes.remove((tx, ty))
            self.boxes.add((bx, by))
            self.pushes += 1

        self._undo.append((self.player, pushed_from_to))
        self.player = (tx, ty)
        self.moves += 1
        return MoveResult(
            moved=True,
            pushed=pushed_from_to is not None,
            won=self.is_solved(),
        )

    def undo(self) -> bool:
        """Undo one move. Returns True if state changed."""
        if not self._undo:
            return False
        prev_player, pushed = self._undo.pop()
        self.player = prev_player
        if pushed is not None:
            frm, to = pushed
            # The box that we pushed from `frm` to `to` must be rolled back.
            self.boxes.discard(to)
            self.boxes.add(frm)
            self.pushes -= 1
        self.moves -= 1
        return True

    def reset(self) -> None:
        """Replay undo to the beginning — cheaper than re-parsing since we
        have the full stack."""
        while self.undo():
            pass


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _flood_inside(cells: list[list[str]], start: tuple[int, int]) -> set[tuple[int, int]]:
    """Return the set of (x,y) reachable from `start` without crossing
    walls or OUTSIDE. Used at parse time to trim cosmetic stray spaces."""
    h = len(cells)
    w = len(cells[0]) if h else 0
    seen: set[tuple[int, int]] = {start}
    stack = [start]
    while stack:
        x, y = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < w and 0 <= ny < h):
                continue
            if (nx, ny) in seen:
                continue
            c = cells[ny][nx]
            if c == WALL or c == OUTSIDE:
                continue
            seen.add((nx, ny))
            stack.append((nx, ny))
    return seen
