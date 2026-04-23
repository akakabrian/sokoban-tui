# Sokoban TUI — Design Decisions

## Engine: write-in-Python, no native dependency

Unlike simcity-tui (Micropolis C++ engine via SWIG), Sokoban's rules fit in
~150 lines of Python. A pure-Python core lets us:

- Skip bootstrap/SWIG entirely — `make venv && make run` is enough.
- Keep the undo stack in Python for zero-latency UI.
- Trivially port to agent API later.

Reference engines consulted:
- **xsokoban** (andrewcmyers/xsokoban on GitHub) — the canonical C engine
  that defines the 90-level public-domain pack and the XSB level format.
  Vendored at `vendor/xsokoban/` for the screens + the reference rules
  implementation (`play.c`).
- **OMerkel/Sokoban** — JS/Python implementation. Used for Microban/Sasquatch
  level packs which it bundles cleanly.

## Level format: XSB (standard)

Characters (from sokobano.de wiki + Cornell xsokoban man page):

| Char  | Meaning                 |
|-------|-------------------------|
| `#`   | Wall                    |
| ` `   | Floor (outside/inside — disambiguated by flood-fill from player) |
| `.`   | Goal                    |
| `$`   | Box                     |
| `*`   | Box on goal             |
| `@`   | Player                  |
| `+`   | Player on goal          |

Also accepted on parse: `-` / `_` as explicit floor (XSB wiki suggests both).

We ignore RLE on parse (none of our bundled packs use it). Collections ship
as one `.txt` file with levels separated by blank lines, optional `;`
comments, optional `; NN` headers.

## Level packs bundled

1. **xsokoban-90** — original 50 + 40 extra, public domain.
   Source: `vendor/xsokoban/screens/screen.1 … screen.90`.
2. **microban** — 155 levels by David W. Skinner, freely distributable
   with credit. Source: `vendor/skinner/Microban.txt`.
3. **microban-ii** — 135 levels by Skinner, same terms.
4. **sasquatch** — 50 levels by Skinner, harder set.

## Target layout (mirrors simcity-tui)

```
sokoban-tui/
├── sokoban.py                  # entry: argparse → run(...)
├── pyproject.toml
├── Makefile
├── DECISIONS.md                # this file
├── vendor/
│   ├── xsokoban/screens/...    # raw screen.N files
│   └── skinner/*.txt           # Microban / Sasquatch
├── sokoban_tui/
│   ├── __init__.py
│   ├── engine.py               # Level, Game, moves, undo
│   ├── levels.py               # Pack loader (XSB parser)
│   ├── tiles.py                # glyph/style tables
│   ├── app.py                  # SokobanApp, LevelView, side panels
│   ├── screens.py              # Help, LevelSelect, Won, Pause
│   └── tui.tcss
└── tests/
    ├── qa.py
    └── perf.py
```

## Controls

| Key                | Action                           |
|--------------------|----------------------------------|
| arrows / `hjkl`    | Move / push                      |
| `u`                | Undo                             |
| `r`                | Reset current level              |
| `n`                | Next level                       |
| `p`                | Previous level                   |
| `L`                | Level-select screen              |
| `?`                | Help                             |
| `q`                | Quit                             |

Mouse: click a tile adjacent to the player to step that direction
(phase F — not in MVP).

## Move / push counters

Classic Sokoban reports both moves and pushes. We show them live in the
status panel and persist best-of-ever to `~/.local/share/sokoban-tui/progress.json`
so the pack-select screen can show per-level bests (later phase).

## Undo stack

Unbounded (Sokoban levels are finite state — even a 100x100 level with
40 boxes has bounded reachable states, and a human will undo at most a
few hundred moves). Each entry is a dict: `{player, boxes_moved, pushed}`
reconstructable cheaply.

## Gate order (from tui-game-build skill)

1. Research — DONE (this document).
2. Engine — pure-Python `engine.py` with `Game.new(level) → Game`,
   `game.move(dx, dy) → MoveResult`, `game.undo()`, `game.is_solved()`.
   Gate: REPL `g = Game.parse("#####\n#@$.#\n#####"); g.move(1,0); g.is_solved() == True`.
3. TUI scaffold — 4-panel Textual app. Gate: launch, move player, push box.
4. QA harness — 8 base scenarios before polish.
5. Perf — baseline; only optimize if >10ms/frame.
6. Robustness — out-of-bounds, malformed levels, KeyError on glyph.
7. Polish (phased):
   - A: UI beauty, level-select screen.
   - B: Win screen + stats tracking.
   - C: (optional) agent REST API.
   - D: (optional) sound.
   - E: (optional) mouse support.
