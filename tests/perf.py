"""Benchmark hot paths. Sokoban is dead simple so mostly this exists
to catch future regressions — the baseline numbers are microseconds."""

from __future__ import annotations

import time
from pathlib import Path

from sokoban_tui.engine import Game
from sokoban_tui.levels import PACKS


def bench(label: str, fn, repeats: int = 2000) -> None:
    samples = []
    # Warm up
    for _ in range(min(200, repeats // 10 or 1)):
        fn()
    for _ in range(repeats):
        t0 = time.perf_counter_ns()
        fn()
        samples.append(time.perf_counter_ns() - t0)
    samples.sort()
    med = samples[len(samples) // 2] / 1000.0  # ns → µs
    p99 = samples[int(len(samples) * 0.99)] / 1000.0
    print(f"  {label:<40} median {med:>8.2f} µs   p99 {p99:>8.2f} µs  (n={repeats})")


def main() -> None:
    # Pick a representative non-trivial level.
    big = None
    for p in PACKS:
        for i, ld in enumerate(p.levels):
            g = ld.load()
            if g.width * g.height > 200 and len(g.boxes) >= 5:
                big = (p.name, i, g)
                break
        if big:
            break
    assert big is not None
    print(f"sample level: {big[0]}#{big[1] + 1} — {big[2].width}×{big[2].height}, "
          f"{len(big[2].boxes)} boxes")

    sample_xsb = (Path(__file__).resolve().parent.parent
                  / "vendor" / "xsokoban" / "screens" / "screen.1").read_text()

    print("\nEngine hot paths:")
    bench("Game.parse (xsokoban #1)", lambda: Game.parse(sample_xsb))

    g = big[2]
    bench("Game.move (wall hit)", lambda: Game(
        cells=[row[:] for row in g.cells],
        width=g.width, height=g.height,
        player=g.player, boxes=set(g.boxes), goals=set(g.goals)
    ).move(0, 0))
    # move(0,0) is no-op (player → (px,py) = same cell; cells[py][px] is FLOOR so
    # technically "moves"). Use (1,0) on a fresh copy which may push or block.
    def one_move():
        gg = Game(cells=[row[:] for row in g.cells],
                  width=g.width, height=g.height,
                  player=g.player, boxes=set(g.boxes), goals=set(g.goals))
        gg.move(1, 0)
    bench("Game.move (+1,0)", one_move)

    bench("Game.is_solved (no)", lambda: g.is_solved())

    # Load every pack, parse every level, report total time.
    t0 = time.perf_counter_ns()
    total = 0
    for p in PACKS:
        for ld in p.levels:
            ld.load()
            total += 1
    elapsed = (time.perf_counter_ns() - t0) / 1e6
    print(f"\nParse all {total} levels across {len(PACKS)} packs: {elapsed:.1f} ms "
          f"({elapsed * 1000 / total:.1f} µs / level)")

    # Simulate 1000 moves on the sample level to model a play session.
    import random
    random.seed(0)
    gg = g
    t0 = time.perf_counter_ns()
    for _ in range(1000):
        dx, dy = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        gg.move(dx, dy)
    t1 = time.perf_counter_ns()
    # Undo them all.
    while gg.undo():
        pass
    t2 = time.perf_counter_ns()
    print(f"1000 random moves: {(t1 - t0) / 1000:.1f} µs total "
          f"({(t1 - t0) / 1000 / 1000:.2f} µs / move)")
    print(f"Undo all: {(t2 - t1) / 1000:.1f} µs")


if __name__ == "__main__":
    main()
