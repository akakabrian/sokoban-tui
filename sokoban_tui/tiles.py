"""Glyph + style tables for rendering a Sokoban board.

Separate layers:
  * terrain layer — wall / floor / goal / outside.
  * object layer — box, box-on-goal, player, player-on-goal.

The renderer looks up both and composes; this file owns the lookup.
"""

from __future__ import annotations

from rich.style import Style

# ----- terrain glyphs -----
GLYPH_WALL = "█"
GLYPH_FLOOR = "·"
GLYPH_GOAL = "◦"
GLYPH_OUTSIDE = " "

# ----- object glyphs -----
GLYPH_BOX = "▣"
GLYPH_BOX_ON_GOAL = "◼"  # distinguishable from a plain box at a glance
GLYPH_PLAYER = "☺"
GLYPH_PLAYER_ON_GOAL = "☻"

# ----- styles -----
# Backgrounds are near-black to keep the board readable; fg colors do
# the work. This follows the palette rules from tui-game-build.
BG_FLOOR = "rgb(22,22,28)"
BG_GOAL = "rgb(40,30,15)"
BG_WALL = "rgb(45,40,35)"
BG_OUTSIDE = "rgb(10,10,12)"

_WALL_STYLE = Style.parse(f"rgb(170,150,120) on {BG_WALL}")
_FLOOR_STYLE = Style.parse(f"rgb(70,70,90) on {BG_FLOOR}")
_GOAL_STYLE = Style.parse(f"bold rgb(255,200,80) on {BG_GOAL}")
_OUTSIDE_STYLE = Style.parse(f"on {BG_OUTSIDE}")

_BOX_STYLE = Style.parse(f"bold rgb(200,140,60) on {BG_FLOOR}")
_BOX_ON_GOAL_STYLE = Style.parse(f"bold rgb(120,230,120) on {BG_GOAL}")
_PLAYER_STYLE = Style.parse(f"bold rgb(255,255,255) on {BG_FLOOR}")
_PLAYER_ON_GOAL_STYLE = Style.parse(f"bold rgb(255,255,120) on {BG_GOAL}")


def terrain(cell: str) -> tuple[str, Style]:
    """Return (glyph, style) for a terrain cell code."""
    if cell == "#":
        return GLYPH_WALL, _WALL_STYLE
    if cell == ".":
        return GLYPH_GOAL, _GOAL_STYLE
    if cell == " ":
        return GLYPH_FLOOR, _FLOOR_STYLE
    # OUTSIDE / anything else.
    return GLYPH_OUTSIDE, _OUTSIDE_STYLE


def box(on_goal: bool) -> tuple[str, Style]:
    if on_goal:
        return GLYPH_BOX_ON_GOAL, _BOX_ON_GOAL_STYLE
    return GLYPH_BOX, _BOX_STYLE


def player(on_goal: bool) -> tuple[str, Style]:
    if on_goal:
        return GLYPH_PLAYER_ON_GOAL, _PLAYER_ON_GOAL_STYLE
    return GLYPH_PLAYER, _PLAYER_STYLE


# Unknown-class fallback — magenta so it's obvious during dev.
UNKNOWN = Style.parse("bold rgb(255,0,255) on rgb(0,0,0)")
