"""Textual TUI for Sokoban.

Widgets:
  * BoardView — Strip-based renderer that reads Game state each frame.
  * StatusPanel — level name, moves/pushes, boxes-on-goal counter.
  * ControlsPanel — key legend.
  * RichLog — move feedback.
  * flash_bar — single-line transient message strip.
"""

from __future__ import annotations

from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.geometry import Size
from textual.strip import Strip
from textual.widget import Widget
from textual.widgets import Footer, Header, RichLog, Static

from . import tiles
from .engine import Game, MoveResult
from .levels import PACKS, Pack, LevelData
from .screens import HelpScreen, LevelSelectScreen, WonScreen


# Movement keys — arrows AND hjkl. All priority=True so scrollable
# widgets don't eat them.
_MOVE_KEYS = {
    "up":    (0, -1),
    "down":  (0,  1),
    "left":  (-1, 0),
    "right": ( 1, 0),
    "k":     (0, -1),
    "j":     (0,  1),
    "h":     (-1, 0),
    "l":     ( 1, 0),
    "w":     (0, -1),
    "s":     (0,  1),
    "a":     (-1, 0),
    "d":     ( 1, 0),
}


class BoardView(Widget):
    """Renders the current Game's board via Strip.render_line.

    Sokoban boards are small (typically 10–30 cells wide) so we don't
    need ScrollView or viewport cropping — we center the board inside
    the widget and render all rows every repaint. Perf is fine.
    """

    DEFAULT_CSS = ""

    def __init__(self, app_ref: "SokobanApp", **kw) -> None:
        super().__init__(**kw)
        self._app = app_ref

    def get_content_width(self, container: Size, viewport: Size) -> int:
        g = self._app.game
        return max(g.width + 4, 10) if g else 10

    def get_content_height(
        self, container: Size, viewport: Size, width: int
    ) -> int:
        g = self._app.game
        return max(g.height + 2, 5) if g else 5

    # --- core render path -------------------------------------------------

    def render_line(self, y: int) -> Strip:
        """Render viewport row `y`. We center the board both horizontally
        and vertically in the widget so small levels don't hug a corner."""
        g = self._app.game
        if g is None:
            return Strip.blank(self.size.width)

        widget_w = self.size.width
        widget_h = self.size.height
        pad_x = max(0, (widget_w - g.width) // 2)
        pad_y = max(0, (widget_h - g.height) // 2)

        board_y = y - pad_y
        if board_y < 0 or board_y >= g.height:
            return Strip.blank(widget_w, tiles._OUTSIDE_STYLE)

        segments: list[Segment] = []
        # Left pad
        if pad_x > 0:
            segments.append(Segment(" " * pad_x, tiles._OUTSIDE_STYLE))
        # Board row
        row_text_parts: list[Segment] = []
        for x in range(g.width):
            glyph, style = _cell_glyph(g, x, board_y)
            row_text_parts.append(Segment(glyph, style))
        # Coalesce adjacent same-style segments for lighter repaint.
        segments.extend(_rle(row_text_parts))
        # Right pad to fill widget width
        used = pad_x + g.width
        if used < widget_w:
            segments.append(Segment(" " * (widget_w - used), tiles._OUTSIDE_STYLE))
        return Strip(segments)


def _cell_glyph(g: Game, x: int, y: int) -> tuple[str, Style]:
    """Compose terrain + object layers for cell (x, y)."""
    has_player = (g.player == (x, y))
    has_box = (x, y) in g.boxes
    on_goal = (x, y) in g.goals

    if has_player:
        return tiles.player(on_goal)
    if has_box:
        return tiles.box(on_goal)
    return tiles.terrain(g.cells[y][x])


def _rle(segs: list[Segment]) -> list[Segment]:
    """Run-length encode adjacent same-style segments. Cheap win."""
    if not segs:
        return segs
    out = [segs[0]]
    for s in segs[1:]:
        last = out[-1]
        if s.style == last.style:
            out[-1] = Segment(last.text + s.text, last.style)
        else:
            out.append(s)
    return out


# --------------------------------------------------------------------------
# Side panels
# --------------------------------------------------------------------------


class StatusPanel(Static):
    """Shows the current level's identity and the live counters. We
    cache the last snapshot so a no-op refresh doesn't rebuild a Text."""

    def __init__(self, app_ref: "SokobanApp") -> None:
        super().__init__("", id="status")
        self._app = app_ref
        self._last: tuple | None = None

    def refresh_panel(self) -> None:
        a = self._app
        g = a.game
        if g is None:
            return
        on_goal = sum(1 for b in g.boxes if b in g.goals)
        snap = (a.pack.name, a.level_idx, g.moves, g.pushes,
                len(g.boxes), on_goal, g.is_solved())
        if snap == self._last:
            return
        self._last = snap
        t = Text()
        t.append(f"Pack   {a.pack.display}\n", style="bold rgb(180,200,240)")
        t.append(f"Level  {a.level_idx + 1} / {len(a.pack)}\n",
                 style="rgb(220,220,235)")
        if g.title:
            t.append(f"       {g.title}\n", style="rgb(150,150,170)")
        t.append("\n")
        t.append("Moves   ", style="rgb(150,150,170)")
        t.append(f"{g.moves}\n", style="bold rgb(230,230,240)")
        t.append("Pushes  ", style="rgb(150,150,170)")
        t.append(f"{g.pushes}\n", style="bold rgb(230,230,240)")
        t.append("Boxes   ", style="rgb(150,150,170)")
        t.append(f"{on_goal} / {len(g.boxes)}",
                 style="bold rgb(120,230,120)" if on_goal == len(g.boxes)
                       else "bold rgb(230,230,240)")
        if g.is_solved():
            t.append("   ★ SOLVED", style="bold rgb(255,220,80)")
        self.update(t)


class ControlsPanel(Static):
    def __init__(self) -> None:
        t = Text()
        t.append("Controls\n", style="bold rgb(180,200,240)")
        rows = [
            ("arrows / hjkl", "move & push"),
            ("u", "undo"),
            ("r", "reset level"),
            ("n / p", "next / prev"),
            ("L", "level select"),
            ("?", "help"),
            ("q", "quit"),
        ]
        for k, desc in rows:
            t.append(f"  {k:<14}", style="bold rgb(255,220,80)")
            t.append(f"{desc}\n", style="rgb(200,200,215)")
        super().__init__(t, id="controls")


# --------------------------------------------------------------------------
# The App
# --------------------------------------------------------------------------


class SokobanApp(App):
    CSS_PATH = "tui.tcss"
    TITLE = "Sokoban TUI"
    SUB_TITLE = ""

    # All movement bindings are priority so scrollable siblings don't
    # steal arrow keys. Letter keys don't conflict in practice but we
    # keep them priority for symmetry.
    BINDINGS = [
        *[Binding(k, f"move({dx},{dy})", show=False, priority=True)
          for k, (dx, dy) in _MOVE_KEYS.items()],
        Binding("u", "undo", "undo", priority=True),
        Binding("r", "reset", "reset"),
        Binding("n", "next_level", "next"),
        Binding("p", "prev_level", "prev"),
        Binding("L", "select_level", "levels"),
        Binding("question_mark", "help", "help"),
        Binding("q", "quit", "quit"),
    ]

    def __init__(self, pack_name: str | None = None, level_idx: int = 0) -> None:
        super().__init__()
        self.pack: Pack = (
            next(p for p in PACKS if p.name == pack_name)
            if pack_name else PACKS[0]
        )
        self.level_idx = max(0, min(level_idx, len(self.pack) - 1))
        self.game: Game | None = None
        # Increments on every movement attempt (including blocked moves).
        # Dogfood/state probes use this to distinguish "input ignored"
        # from "input accepted but no world change".
        self._input_serial = 0
        self._last_move_reason = "init"
        # widgets — attached in compose()
        self.board: BoardView | None = None
        self.status_panel: StatusPanel | None = None
        self.flash_bar: Static | None = None
        self.message_log: RichLog | None = None

    # --- compose ----------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        self.board = BoardView(self, id="board")
        self.status_panel = StatusPanel(self)
        self.flash_bar = Static("", id="flash")
        self.message_log = RichLog(id="log", max_lines=500, wrap=True, markup=True)
        with Vertical(id="left"):
            yield self.board
            yield self.flash_bar
        with Vertical(id="right"):
            yield self.status_panel
            yield ControlsPanel()
            yield self.message_log
        yield Footer()

    def on_mount(self) -> None:
        self._load_current()

    # --- level management -------------------------------------------------

    def _load_current(self) -> None:
        data: LevelData = self.pack[self.level_idx]
        self.game = data.load()
        self._input_serial = 0
        self._last_move_reason = "loaded"
        self.sub_title = f"{self.pack.display} — level {self.level_idx + 1}/{len(self.pack)}"
        if self.status_panel:
            self.status_panel.refresh_panel()
        if self.board:
            self.board.refresh()
        if self.message_log:
            self.message_log.write(
                f"[bold rgb(180,200,240)]▶ {self.game.title}[/] "
                f"({self.game.width}×{self.game.height}, {len(self.game.boxes)} boxes)"
            )
        self._flash(f"{self.game.title}")

    def _flash(self, msg: str) -> None:
        if self.flash_bar:
            self.flash_bar.update(msg)

    def load_level(self, pack: Pack, idx: int) -> None:
        """Called by LevelSelectScreen on selection."""
        self.pack = pack
        self.level_idx = max(0, min(idx, len(pack) - 1))
        self._load_current()

    def _modal_open(self) -> bool:
        return len(self.screen_stack) > 1

    def state_snapshot(self) -> dict[str, object]:
        g = self.game
        if g is None:
            return {
                "screen": self.screen.__class__.__name__,
                "stack_len": len(self.screen_stack),
                "pack": self.pack.name,
                "level_idx": self.level_idx,
                "level_count": len(self.pack),
                "ready": False,
                "input_serial": self._input_serial,
                "last_move_reason": self._last_move_reason,
            }
        on_goal = sum(1 for b in g.boxes if b in g.goals)
        return {
            "screen": self.screen.__class__.__name__,
            "stack_len": len(self.screen_stack),
            "pack": self.pack.name,
            "level_idx": self.level_idx,
            "level_count": len(self.pack),
            "player": [g.player[0], g.player[1]],
            "moves": g.moves,
            "pushes": g.pushes,
            "boxes": len(g.boxes),
            "boxes_on_goal": on_goal,
            "solved": g.is_solved(),
            "ready": True,
            "input_serial": self._input_serial,
            "last_move_reason": self._last_move_reason,
        }

    # --- actions ----------------------------------------------------------

    def action_move(self, dx: int, dy: int) -> None:
        if self._modal_open() or self.game is None:
            return
        self._input_serial += 1
        r: MoveResult = self.game.move(dx, dy)
        if not r.moved:
            self._last_move_reason = r.reason
            # Don't spam the log — flash-only feedback.
            self._flash(f"blocked ({r.reason})")
        else:
            self._last_move_reason = "moved"
            self._flash(
                f"moves {self.game.moves}  pushes {self.game.pushes}"
            )
        if self.board:
            self.board.refresh()
        if self.status_panel:
            self.status_panel.refresh_panel()
        if r.won:
            self._last_move_reason = "won"
            self._on_win()

    def action_undo(self) -> None:
        if self._modal_open():
            return
        if self.game and self.game.undo():
            self._last_move_reason = "undo"
            self._flash(f"undo — moves {self.game.moves}  pushes {self.game.pushes}")
            if self.board:
                self.board.refresh()
            if self.status_panel:
                self.status_panel.refresh_panel()

    def action_reset(self) -> None:
        if self._modal_open():
            return
        if self.game is None:
            return
        # Re-parse rather than undo-to-zero so we're immune to any state
        # drift from prior bugs; it's ~0.1 ms.
        self._load_current()
        if self.message_log:
            self.message_log.write("[rgb(220,180,90)]↺ reset[/]")

    def action_next_level(self) -> None:
        if self._modal_open():
            return
        if self.level_idx + 1 < len(self.pack):
            self.level_idx += 1
            self._load_current()
        else:
            self._flash(f"end of pack ({self.pack.display})")

    def action_prev_level(self) -> None:
        if self._modal_open():
            return
        if self.level_idx > 0:
            self.level_idx -= 1
            self._load_current()
        else:
            self._flash(f"start of pack ({self.pack.display})")

    def action_select_level(self) -> None:
        if self._modal_open():
            return
        self.push_screen(LevelSelectScreen(PACKS, self.pack, self.level_idx))

    def action_help(self) -> None:
        if self._modal_open():
            return
        self.push_screen(HelpScreen())

    # --- win flow ---------------------------------------------------------

    def _on_win(self) -> None:
        if self.game is None:
            return
        if self.message_log:
            self.message_log.write(
                f"[bold rgb(120,230,120)]★ SOLVED[/] — "
                f"{self.game.moves} moves / {self.game.pushes} pushes"
            )
        self.push_screen(
            WonScreen(self.game.moves, self.game.pushes,
                      has_next=self.level_idx + 1 < len(self.pack))
        )


def run(pack: str | None = None, level: int = 0) -> None:
    SokobanApp(pack_name=pack, level_idx=level).run()
