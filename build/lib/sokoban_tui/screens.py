"""Modal screens: Level select, Won, Help."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, OptionList
from textual.widgets.option_list import Option

if TYPE_CHECKING:
    from .app import SokobanApp


class HelpScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "close"),
        Binding("question_mark", "app.pop_screen", "close"),
        Binding("q", "app.pop_screen", "close"),
    ]

    def compose(self) -> ComposeResult:
        t = Text()
        t.append("Sokoban — Controls\n\n", style="bold rgb(255,220,80)")
        t.append("Move / push    ", style="rgb(200,200,220)")
        t.append("arrows · h j k l · w a s d\n", style="bold rgb(255,255,255)")
        t.append("Undo           ", style="rgb(200,200,220)")
        t.append("u\n", style="bold rgb(255,255,255)")
        t.append("Reset level    ", style="rgb(200,200,220)")
        t.append("r\n", style="bold rgb(255,255,255)")
        t.append("Next / Prev    ", style="rgb(200,200,220)")
        t.append("n / p\n", style="bold rgb(255,255,255)")
        t.append("Level select   ", style="rgb(200,200,220)")
        t.append("L\n", style="bold rgb(255,255,255)")
        t.append("Quit           ", style="rgb(200,200,220)")
        t.append("q\n\n", style="bold rgb(255,255,255)")
        t.append("Glyphs\n", style="bold rgb(180,200,240)")
        t.append("  ☺ you    ☻ you on goal\n", style="rgb(220,220,235)")
        t.append("  ▣ box    ◼ box on goal\n", style="rgb(220,220,235)")
        t.append("  ◦ goal   █ wall\n\n", style="rgb(220,220,235)")
        t.append("Push boxes to all goals. Boxes only push —\n",
                 style="rgb(200,200,220)")
        t.append("they cannot be pulled. Press ", style="rgb(200,200,220)")
        t.append("u", style="bold rgb(255,220,80)")
        t.append(" to undo.\n\n", style="rgb(200,200,220)")
        t.append("esc / ? to close", style="rgb(150,150,170)")
        yield Vertical(Static(t), id="help-panel")


class WonScreen(ModalScreen):
    """Shown when the player completes a level.

    Keys here must not conflict with priority App bindings (up/down/
    enter/space). `n` advances, `r` retries, `L` level-select, `esc`
    back to the game.
    """
    BINDINGS = [
        Binding("n", "next", "next level"),
        Binding("r", "retry", "retry"),
        Binding("L", "select", "level select"),
        Binding("escape", "close", "back"),
    ]

    def __init__(self, moves: int, pushes: int, has_next: bool) -> None:
        super().__init__()
        self.moves = moves
        self.pushes = pushes
        self.has_next = has_next

    def compose(self) -> ComposeResult:
        t = Text()
        t.append("★ SOLVED ★\n\n", style="bold rgb(255,220,80)")
        t.append(f"{self.moves} moves · {self.pushes} pushes\n\n",
                 style="bold rgb(230,230,240)")
        nxt = "n next · " if self.has_next else ""
        t.append(f"{nxt}r retry · L levels · esc", style="rgb(180,200,240)")
        yield Vertical(Static(t), id="won-panel")

    # Each action pops back to the main screen first, then does its thing
    # against the App. Keeping the action chain simple means a failure in
    # one branch doesn't leave us stacked on a dead modal.

    def _sokoban_app(self) -> "SokobanApp":
        from .app import SokobanApp
        return cast(SokobanApp, self.app)

    def action_next(self) -> None:
        app = self._sokoban_app()
        if self.has_next:
            app.pop_screen()
            app.action_next_level()

    def action_retry(self) -> None:
        app = self._sokoban_app()
        app.pop_screen()
        app.action_reset()

    def action_select(self) -> None:
        app = self._sokoban_app()
        app.pop_screen()
        app.action_select_level()

    def action_close(self) -> None:
        self.app.pop_screen()


class LevelSelectScreen(ModalScreen):
    """Scrollable OptionList of (pack, level) pairs. Enter selects."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "close"),
        Binding("q", "app.pop_screen", "close"),
        # j/k are the arrow-alias for OptionList — Textual's OptionList
        # already supports up/down; we add j/k as priority bindings via
        # the App. Inside the modal, up/down are NOT priority (App
        # priority bindings still beat the screen) so we rebind them
        # here explicitly to be sure OptionList receives them. Textual
        # routes via the focused widget; OptionList handles them
        # natively.
    ]

    def __init__(self, packs, current_pack, current_idx: int) -> None:
        super().__init__()
        self._packs = packs
        self._current_pack = current_pack
        self._current_idx = current_idx
        # Flat index list of (pack, idx) tuples parallel to options.
        self._flat: list[tuple] = []

    def compose(self) -> ComposeResult:
        options: list[Option] = []
        initial_highlight = 0
        for p in self._packs:
            # Pack header row — non-selectable sentinel; we skip it in
            # on_option_selected by checking the id prefix.
            options.append(
                Option(
                    Text(f"━━ {p.display} ━━  ({len(p)} levels)",
                         style="bold rgb(180,200,240)"),
                    id=f"hdr:{p.name}",
                    disabled=True,
                )
            )
            self._flat.append(("hdr", p))
            for i in range(len(p)):
                label = Text()
                label.append(f"  {p.name} #{i + 1:>3}", style="rgb(220,220,235)")
                lvl = p[i]
                if lvl.title and lvl.title != f"{p.display} #{i + 1}":
                    label.append(f"  {lvl.title}", style="rgb(150,150,170)")
                options.append(Option(label, id=f"lvl:{p.name}:{i}"))
                self._flat.append(("lvl", p, i))
                if p is self._current_pack and i == self._current_idx:
                    initial_highlight = len(options) - 1
        ol = OptionList(*options, id="level-list")
        # Focus + initial highlight set on mount below.
        self._ol = ol
        self._initial_highlight = initial_highlight
        hint = Static(Text("enter select · esc close", style="rgb(150,150,170)"))
        yield Vertical(ol, hint, id="select-panel")

    def on_mount(self) -> None:
        try:
            self._ol.highlighted = self._initial_highlight
        except Exception:
            pass
        self._ol.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = event.option.id or ""
        if not opt_id.startswith("lvl:"):
            return
        _, pack_name, idx_s = opt_id.split(":")
        idx = int(idx_s)
        pack = next(p for p in self._packs if p.name == pack_name)
        from .app import SokobanApp
        app = cast(SokobanApp, self.app)
        app.pop_screen()
        # Call the app helper to switch levels.
        app.load_level(pack, idx)
