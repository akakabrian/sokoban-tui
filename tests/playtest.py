"""End-to-end playtest driver.

Boots the app, picks a level, moves the player, pushes a box, verifies
win detection, exercises undo / reset / next-level / quit. Captures an
SVG screenshot at each milestone into tests/out/playtest_*.svg so the
output is reviewable offline.

Run:  python -m tests.playtest

This is a sibling of `tests.qa` — QA checks atomic invariants, playtest
tells a story. Failures fall out as assertions and an exit code.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from sokoban_tui.app import SokobanApp
from sokoban_tui.engine import Game

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)


async def playtest() -> int:
    app = SokobanApp(pack_name="microban", level_idx=0)
    failures: list[str] = []

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()

        # --- milestone 1: boot ------------------------------------------
        assert app.game is not None, "game didn't mount"
        assert app.pack.name == "microban"
        assert app.level_idx == 0
        app.save_screenshot(str(OUT / "playtest_01_boot.svg"))
        print(f"  ✓ booted on {app.pack.name} #{app.level_idx + 1}: {app.game.title}")

        # --- milestone 2: pick a specific level (level select) ----------
        # We exercise the open/close path via keys; actual selection is
        # driven through load_level (OptionList selection is covered in QA).
        await pilot.press("L")
        await pilot.pause()
        if app.screen.__class__.__name__ != "LevelSelectScreen":
            failures.append("level-select did not open")
        app.save_screenshot(str(OUT / "playtest_02_level_select.svg"))
        await pilot.press("escape")
        await pilot.pause()
        print("  ✓ level-select opens + closes")

        # --- milestone 3: move player + push box ------------------------
        # Swap in a tiny solve-in-one so we can deterministically exercise
        # a push, win, and undo path without depending on a specific
        # Microban layout.
        app.game = Game.parse("#####\n#@$.#\n#####", title="playtest mini")
        app.board.refresh()  # type: ignore[union-attr]
        app.status_panel.refresh_panel()  # type: ignore[union-attr]
        await pilot.pause()
        start_player = app.game.player
        start_boxes = set(app.game.boxes)
        app.save_screenshot(str(OUT / "playtest_03_mini_loaded.svg"))

        # Push the box right into the goal (solve in one).
        await pilot.press("right")
        await pilot.pause()
        if app.game.player == start_player:
            failures.append("player did not move after pressing right")
        if app.game.boxes == start_boxes:
            failures.append("box did not move — push failed")
        if app.game.pushes != 1:
            failures.append(f"expected 1 push, got {app.game.pushes}")
        print(f"  ✓ pushed box: moves={app.game.moves} pushes={app.game.pushes}")

        # --- milestone 4: win detection ---------------------------------
        if not app.game.is_solved():
            failures.append("is_solved() false after pushing onto goal")
        if app.screen.__class__.__name__ != "WonScreen":
            failures.append(
                f"WonScreen not shown: got {app.screen.__class__.__name__}"
            )
        app.save_screenshot(str(OUT / "playtest_04_won.svg"))
        print("  ✓ win detected — WonScreen visible")

        # Dismiss the win modal.
        await pilot.press("escape")
        await pilot.pause()

        # --- milestone 5: undo ------------------------------------------
        await pilot.press("u")
        await pilot.pause()
        if app.game.boxes != start_boxes:
            failures.append(f"undo didn't restore boxes: {app.game.boxes}")
        if app.game.player != start_player:
            failures.append(f"undo didn't restore player: {app.game.player}")
        if app.game.moves != 0 or app.game.pushes != 0:
            failures.append(
                f"counters not zeroed: moves={app.game.moves} pushes={app.game.pushes}"
            )
        app.save_screenshot(str(OUT / "playtest_05_undone.svg"))
        print(f"  ✓ undo restored state: moves={app.game.moves}")

        # --- milestone 6: reset (make a move, reset, verify zero) -------
        await pilot.press("right")
        await pilot.pause()
        # Game is solved again after right push — dismiss WonScreen if shown.
        if app.screen.__class__.__name__ == "WonScreen":
            await pilot.press("escape")
            await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        if app.game.moves != 0:
            failures.append(f"reset didn't clear moves: {app.game.moves}")
        app.save_screenshot(str(OUT / "playtest_06_reset.svg"))
        print("  ✓ reset returns to starting state")

        # --- milestone 7: next-level ------------------------------------
        # Load the first real level again before advancing.
        app.load_level(app.pack, 0)
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        if app.level_idx != 1:
            failures.append(f"next-level didn't advance: idx={app.level_idx}")
        app.save_screenshot(str(OUT / "playtest_07_next_level.svg"))
        print(f"  ✓ next-level advanced to #{app.level_idx + 1}")

        # --- milestone 8: quit ------------------------------------------
        # We let run_test's context handle the exit cleanly; firing the
        # quit action verifies the binding resolves without raising.
        await app.action_quit()
        print("  ✓ quit action completed")

    if failures:
        print(f"\nplaytest FAILED — {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nplaytest OK — 8/8 milestones")
    return 0


def pty_smoke() -> int:
    """Launch sokoban-tui in a real pty via pexpect, let it boot, send q,
    confirm clean exit. This is a minimal real-terminal smoke test — the
    pilot-driven `playtest()` above is the comprehensive one.
    """
    try:
        import pexpect
    except ImportError:
        print("  · pty-smoke skipped (pexpect not installed)")
        return 0

    repo = Path(__file__).resolve().parent.parent
    # pexpect type stub requires os._Environ[str]; mutate a copy of the
    # real environ in place so we don't leak TERM back into our shell.
    os.environ.setdefault("TERM", "xterm-256color")
    child = pexpect.spawn(
        sys.executable,
        [str(repo / "sokoban.py"), "--pack", "microban", "--level", "1"],
        timeout=15,
        dimensions=(40, 120),
        env=os.environ,
        cwd=str(repo),
    )
    # Wait briefly for the Textual header to paint — "Sokoban" appears
    # in the title bar. If we see it, we know the app mounted.
    try:
        child.expect("Sokoban", timeout=10)
    except pexpect.TIMEOUT:
        print("  ✗ pty-smoke: app did not paint title within 10s")
        child.close(force=True)
        return 1
    child.send("q")
    child.expect(pexpect.EOF, timeout=5)
    child.close()
    if child.exitstatus not in (0, None):
        print(f"  ✗ pty-smoke: non-zero exit {child.exitstatus}")
        return 1
    print("  ✓ pty-smoke: booted in real pty and quit cleanly")
    return 0


if __name__ == "__main__":
    rc = asyncio.run(playtest())
    rc |= pty_smoke()
    sys.exit(rc)
