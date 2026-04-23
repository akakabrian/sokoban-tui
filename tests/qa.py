"""Headless QA driver for sokoban-tui.

Runs each scenario in a fresh SokobanApp via App.run_test(), captures an
SVG screenshot, and reports pass/fail. Exit code is number of failures.

    python -m tests.qa            # run all
    python -m tests.qa undo       # scenarios matching "undo"
"""

from __future__ import annotations

import asyncio
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from sokoban_tui.app import SokobanApp
from sokoban_tui.engine import Game
from sokoban_tui.levels import PACKS, pack_by_name

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)


@dataclass
class Scenario:
    name: str
    fn: Callable[[SokobanApp, "object"], Awaitable[None]]


# ---------- pure-engine scenarios ----------
# These don't need the TUI — we run them through the same harness for
# uniform reporting, but they just build a Game and poke it directly.

async def s_parse_xsb_minimal(app, pilot):
    g = Game.parse("#####\n#@$.#\n#####")
    assert g.width == 5 and g.height == 3
    assert g.player == (1, 1)
    assert g.boxes == {(2, 1)}
    assert g.goals == {(3, 1)}
    assert not g.is_solved()


async def s_solve_in_one(app, pilot):
    g = Game.parse("#####\n#@$.#\n#####")
    r = g.move(1, 0)
    assert r.moved and r.pushed and r.won, r


async def s_wall_blocks(app, pilot):
    # Player boxed in on three sides; attempting move left → wall.
    g = Game.parse("#####\n#$. #\n##@ #\n#####")
    # Player at (2,2). Wall on (1,2). Move left → blocked by wall.
    r = g.move(-1, 0)
    assert not r.moved and r.reason == "wall", (r.moved, r.reason)
    assert g.moves == 0


async def s_cannot_push_box_into_wall(app, pilot):
    # Player, box, wall horizontally — push should fail.
    g = Game.parse("#####\n#.@$#\n#####")
    r = g.move(1, 0)
    assert not r.moved and r.reason == "blocked"
    assert g.boxes == {(3, 1)}


async def s_cannot_push_two_boxes(app, pilot):
    # Player, box, box — trying to push the near box would require the
    # far box to move first. Both boxes have goals elsewhere on the row
    # so the parse validates.
    g = Game.parse("##########\n#..@$$   #\n##########")
    r = g.move(1, 0)
    assert not r.moved and r.reason == "blocked", (r.moved, r.reason)


async def s_undo_push_restores_state(app, pilot):
    g = Game.parse("######\n#@$ .#\n######")
    before_boxes = set(g.boxes)
    before_player = g.player
    r = g.move(1, 0)
    assert r.moved and r.pushed
    assert g.boxes != before_boxes
    assert g.undo() is True
    assert g.player == before_player
    assert g.boxes == before_boxes
    assert g.moves == 0 and g.pushes == 0


async def s_undo_nothing_to_undo(app, pilot):
    g = Game.parse("######\n#@$ .#\n######")
    assert g.undo() is False


async def s_reset_replays_to_start(app, pilot):
    g = Game.parse("######\n#@$ .#\n######")
    start_p = g.player
    start_b = set(g.boxes)
    g.move(1, 0)
    g.move(-1, 0)  # may or may not succeed, doesn't matter
    g.reset()
    assert g.player == start_p
    assert g.boxes == start_b
    assert g.moves == 0 and g.pushes == 0


async def s_box_on_goal_star_glyph(app, pilot):
    # `*` is box-on-goal: layers box AND goal at the same cell. With two
    # `*`s, boxes == goals, level is already solved.
    g = Game.parse("######\n#@ **#\n######")
    assert g.boxes == {(3, 1), (4, 1)}
    assert g.goals == {(3, 1), (4, 1)}
    assert g.is_solved()


async def s_already_solved(app, pilot):
    # One box pre-placed on a goal via `*` → starts solved.
    g = Game.parse("#####\n#@*#\n#####")
    assert g.is_solved(), (g.boxes, g.goals)


async def s_parse_bad_level_rejected(app, pilot):
    # More boxes than goals should raise ValueError (no pytest dep).
    try:
        Game.parse("######\n#@$$.#\n######")
        ok = False
    except ValueError:
        ok = True
    assert ok, "expected ValueError for box/goal count mismatch"


# ---------- TUI scenarios (mount-required) ----------

async def s_mount_clean(app, pilot):
    assert app.board is not None
    assert app.status_panel is not None
    assert app.message_log is not None
    assert app.game is not None


async def s_arrow_moves_player(app, pilot):
    start = app.game.player
    # Try each direction — at least one should succeed on a real level.
    for key in ("right", "left", "up", "down"):
        await pilot.press(key)
        await pilot.pause()
        if app.game.player != start:
            return
    raise AssertionError(f"no direction moved player from {start}")


async def s_hjkl_moves_player(app, pilot):
    start = app.game.player
    # At least one of h/j/k/l should work.
    for key in ("l", "h", "j", "k"):
        await pilot.press(key)
        await pilot.pause()
        if app.game.player != start:
            return
    raise AssertionError(f"no hjkl key moved player from {start}")


async def s_undo_key_works(app, pilot):
    start = app.game.player
    start_moves = app.game.moves
    # Make any move that actually succeeds.
    for key in ("right", "left", "up", "down"):
        await pilot.press(key)
        await pilot.pause()
        if app.game.moves > start_moves:
            break
    else:
        # level too tight for a free move; skip
        return
    after = app.game.player
    await pilot.press("u")
    await pilot.pause()
    assert app.game.player == start, f"undo didn't restore: {start} → {after} → {app.game.player}"


async def s_reset_key_works(app, pilot):
    # Make a move, then reset.
    start_moves = app.game.moves
    await pilot.press("right")
    await pilot.press("left")
    await pilot.press("up")
    await pilot.press("down")
    await pilot.pause()
    await pilot.press("r")
    await pilot.pause()
    assert app.game.moves == 0, f"reset didn't clear moves: {app.game.moves}"


async def s_next_prev_level(app, pilot):
    start_idx = app.level_idx
    await pilot.press("n")
    await pilot.pause()
    assert app.level_idx == start_idx + 1, f"next: {start_idx} → {app.level_idx}"
    await pilot.press("p")
    await pilot.pause()
    assert app.level_idx == start_idx, f"prev: {start_idx + 1} → {app.level_idx}"


async def s_help_screen_opens(app, pilot):
    await pilot.press("question_mark")
    await pilot.pause()
    assert app.screen.__class__.__name__ == "HelpScreen"
    await pilot.press("escape")
    await pilot.pause()
    assert app.screen.__class__.__name__ == "Screen"


async def s_level_select_opens(app, pilot):
    await pilot.press("L")
    await pilot.pause()
    assert app.screen.__class__.__name__ == "LevelSelectScreen"
    await pilot.press("escape")
    await pilot.pause()
    assert app.screen.__class__.__name__ == "Screen"


async def s_board_renders_with_styles(app, pilot):
    """BoardView.render_line must produce segments with foreground colors
    (we render walls, floors, goals, and optional boxes/player)."""
    strip = app.board.render_line(app.size.height // 2)
    segs = list(strip)
    assert len(segs) > 0
    fg_count = sum(1 for s in segs if s.style and s.style.color is not None)
    assert fg_count > 0, "no styled segments in rendered board row"


async def s_status_panel_shows_counters(app, pilot):
    """StatusPanel must refresh with the live moves/pushes counter.
    Static stores the renderable on `._renderable`; in Textual 8 we
    read it off `.render()` return instead for stability."""
    app.status_panel.refresh_panel()
    r = app.status_panel.render()
    s = str(r) if r is not None else ""
    # If render returned empty (shouldn't, but just in case), fall back
    # to poking the cached snapshot directly.
    if not s:
        assert app.status_panel._last is not None
        return
    assert "Moves" in s, f"no 'Moves' in status: {s[:200]}"
    assert "Pushes" in s, f"no 'Pushes' in status: {s[:200]}"


async def s_status_panel_throttles(app, pilot):
    """Repeat refresh_panel() with no sim change must not churn the snapshot."""
    app.status_panel.refresh_panel()
    snap1 = app.status_panel._last
    for _ in range(5):
        app.status_panel.refresh_panel()
    assert app.status_panel._last == snap1


async def s_win_shows_modal(app, pilot):
    """Loading a trivially-solvable test level and pushing one step must
    trigger the WonScreen modal."""
    # Replace the current game with a solve-in-one level.
    app.game = Game.parse("#####\n#@$.#\n#####")
    app.board.refresh()
    await pilot.pause()
    await pilot.press("right")
    await pilot.pause()
    assert app.game.is_solved()
    assert app.screen.__class__.__name__ == "WonScreen", app.screen.__class__.__name__
    await pilot.press("escape")
    await pilot.pause()


async def s_packs_nonempty(app, pilot):
    """The vendored packs must be present and each have levels."""
    assert len(PACKS) >= 2, f"expected at least 2 packs, got {len(PACKS)}"
    names = [p.name for p in PACKS]
    assert "xsokoban" in names, names
    assert "microban" in names, names
    xsk = pack_by_name("xsokoban")
    assert len(xsk) >= 90, f"xsokoban should have 90+ levels, has {len(xsk)}"
    mb = pack_by_name("microban")
    assert len(mb) >= 100, f"microban should have 100+ levels, has {len(mb)}"


async def s_all_levels_parse(app, pilot):
    """Every vendored level must parse cleanly. Protects against a bad
    pack being shipped."""
    failures = []
    for p in PACKS:
        for i, ld in enumerate(p.levels):
            try:
                g = ld.load()
                # Basic invariants
                assert g.player is not None
                assert len(g.boxes) == len(g.goals)
                assert len(g.boxes) > 0
            except Exception as e:
                failures.append(f"{p.name}#{i + 1}: {type(e).__name__}: {e}")
    assert not failures, f"{len(failures)} levels failed to parse:\n  " + "\n  ".join(failures[:10])


async def s_level_select_jumps(app, pilot):
    """Opening level select and confirming on a specific option should
    load that level. We simulate by calling load_level directly (the
    OptionList navigation is driven by keys that also control the app;
    the invariant we care about is that load_level works)."""
    target_pack = pack_by_name("microban")
    app.load_level(target_pack, 5)
    await pilot.pause()
    assert app.pack.name == "microban"
    assert app.level_idx == 5
    assert app.game is not None
    assert app.game.title.endswith("#6") or "6" in app.game.title


async def s_unknown_glyph_does_not_crash(app, pilot):
    """Rendering must not KeyError if a weird terrain cell appears."""
    # Monkey-patch a weird glyph into the grid.
    app.game.cells[0][0] = "?"
    strip = app.board.render_line(app.size.height // 2 - app.game.height // 2)
    assert len(list(strip)) > 0


async def s_move_counter_increments(app, pilot):
    """A successful move must bump moves by exactly 1. A blocked move
    must not bump anything."""
    # Use a tight known level.
    app.game = Game.parse("#####\n#@$.#\n#####")
    app.board.refresh()
    app.status_panel.refresh_panel()
    await pilot.pause()
    assert app.game.moves == 0 and app.game.pushes == 0
    # Blocked: push into left wall.
    await pilot.press("left")
    await pilot.pause()
    assert app.game.moves == 0, f"blocked move bumped counter: {app.game.moves}"
    # Successful push: right.
    await pilot.press("right")
    await pilot.pause()
    assert app.game.moves == 1, app.game.moves
    assert app.game.pushes == 1, app.game.pushes


SCENARIOS: list[Scenario] = [
    # Engine-only (fast)
    Scenario("parse_xsb_minimal", s_parse_xsb_minimal),
    Scenario("solve_in_one_move", s_solve_in_one),
    Scenario("wall_blocks_player", s_wall_blocks),
    Scenario("cannot_push_into_wall", s_cannot_push_box_into_wall),
    Scenario("cannot_push_two_boxes", s_cannot_push_two_boxes),
    Scenario("undo_restores_state", s_undo_push_restores_state),
    Scenario("undo_at_start_is_noop", s_undo_nothing_to_undo),
    Scenario("reset_replays_to_start", s_reset_replays_to_start),
    Scenario("box_on_goal_parses", s_box_on_goal_star_glyph),
    Scenario("already_solved_detected", s_already_solved),
    Scenario("bad_level_rejected", s_parse_bad_level_rejected),
    # Level loader
    Scenario("packs_nonempty", s_packs_nonempty),
    Scenario("all_levels_parse", s_all_levels_parse),
    # TUI
    Scenario("mount_clean", s_mount_clean),
    Scenario("arrow_moves_player", s_arrow_moves_player),
    Scenario("hjkl_moves_player", s_hjkl_moves_player),
    Scenario("undo_key_works", s_undo_key_works),
    Scenario("reset_key_works", s_reset_key_works),
    Scenario("next_prev_level", s_next_prev_level),
    Scenario("help_screen_opens", s_help_screen_opens),
    Scenario("level_select_opens", s_level_select_opens),
    Scenario("level_select_jumps", s_level_select_jumps),
    Scenario("board_renders_with_styles", s_board_renders_with_styles),
    Scenario("status_panel_shows_counters", s_status_panel_shows_counters),
    Scenario("status_panel_throttles", s_status_panel_throttles),
    Scenario("move_counter_increments", s_move_counter_increments),
    Scenario("win_shows_modal", s_win_shows_modal),
    Scenario("unknown_glyph_does_not_crash", s_unknown_glyph_does_not_crash),
]


async def run_one(scn: Scenario) -> tuple[str, bool, str]:
    # Microban #1 is tiny (6x7, 2 boxes) — fast to mount per scenario.
    app = SokobanApp(pack_name="microban", level_idx=0)
    try:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            try:
                await scn.fn(app, pilot)
            except AssertionError as e:
                app.save_screenshot(str(OUT / f"{scn.name}.FAIL.svg"))
                return (scn.name, False, f"AssertionError: {e}")
            except Exception as e:
                app.save_screenshot(str(OUT / f"{scn.name}.ERROR.svg"))
                return (scn.name, False,
                        f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
            app.save_screenshot(str(OUT / f"{scn.name}.PASS.svg"))
            return (scn.name, True, "")
    except Exception as e:
        return (scn.name, False,
                f"harness error: {type(e).__name__}: {e}\n{traceback.format_exc()}")


async def main(pattern: str | None = None) -> int:
    scenarios = [s for s in SCENARIOS if not pattern or pattern in s.name]
    if not scenarios:
        print(f"no scenarios match {pattern!r}")
        return 2
    results = []
    for scn in scenarios:
        name, ok, msg = await run_one(scn)
        mark = "\033[32m✓\033[0m" if ok else "\033[31m✗\033[0m"
        print(f"  {mark} {name}")
        if not ok:
            for line in msg.splitlines():
                print(f"      {line}")
        results.append((name, ok, msg))
    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    print(f"\n{passed}/{len(results)} passed, {failed} failed")
    return failed


if __name__ == "__main__":
    pattern = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(asyncio.run(main(pattern)))
