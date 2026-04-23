"""Load level packs from `vendor/` and turn them into `Game` objects.

Packs live in two shapes:

  * xsokoban — one file per level (`vendor/xsokoban/screens/screen.N`).
  * Skinner collections — a single `.txt` file with N levels separated
    by blank lines; `;` begins a comment line (often a level title or
    pack metadata).

The combined catalog is exposed as `PACKS: list[Pack]` where each
`Pack.levels[i]` is a `LevelData(xsb_text, title)` — we lazily parse
into `Game` only on demand so importing the module is cheap.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .engine import Game

# Repo root is two dirs above this file (sokoban_tui/ → repo).
REPO = Path(__file__).resolve().parent.parent
VENDOR = REPO / "vendor"


@dataclass(frozen=True)
class LevelData:
    xsb: str
    title: str = ""

    def load(self) -> Game:
        return Game.parse(self.xsb, title=self.title)


@dataclass
class Pack:
    name: str            # short id, e.g. "xsokoban"
    display: str         # human label, e.g. "XSokoban — Original 90"
    credit: str          # who made it; shown on the level-select screen
    levels: list[LevelData]

    def __len__(self) -> int:
        return len(self.levels)

    def __getitem__(self, i: int) -> LevelData:
        return self.levels[i]


# ---------- loaders ----------


def _load_xsokoban() -> Pack:
    """90 screen files in `vendor/xsokoban/screens/screen.N`, N=1..90.

    XSokoban README says "distributed in the public domain"."""
    screens_dir = VENDOR / "xsokoban" / "screens"
    levels: list[LevelData] = []
    # Sort numerically, not lexically: screen.10 must come after screen.9.
    files = sorted(
        screens_dir.glob("screen.*"),
        key=lambda p: int(p.suffix.lstrip(".")) if p.suffix.lstrip(".").isdigit() else 0,
    )
    for i, path in enumerate(files, start=1):
        xsb = path.read_text(encoding="utf-8", errors="replace")
        levels.append(LevelData(xsb=xsb, title=f"XSokoban #{i}"))
    return Pack(
        name="xsokoban",
        display="XSokoban — Original 90",
        credit="XSokoban (public domain, Cornell/Andrew Myers)",
        levels=levels,
    )


def _load_skinner_file(path: Path, name: str, display: str) -> Pack:
    """Parse a Skinner-style .txt into N LevelData.

    Format (observed in Microban.txt):
      * Top-of-file banner: `;` comment lines.
      * Each level preceded by `; <number>` on its own line.
      * Level body: consecutive non-blank, non-`;` lines.
      * Blank line ends the level.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    levels: list[LevelData] = []
    buf: list[str] = []
    title = ""

    def flush() -> None:
        nonlocal buf, title
        if buf:
            # Strip trailing empty lines inside the buffer.
            body = "\n".join(buf).rstrip()
            if body.strip():
                levels.append(LevelData(xsb=body, title=title or f"{display} #{len(levels)+1}"))
        buf = []

    for line in text.splitlines():
        stripped = line.rstrip()
        if stripped.startswith(";"):
            # Comment — might be a title/header. Capture.
            # Common headers look like `; 1`, `; 2`, ... or `; Level 5`.
            flush()
            maybe = stripped.lstrip(";").strip()
            if maybe:
                title = f"{display} #{maybe}" if maybe.split()[0].isdigit() else maybe
            continue
        if stripped == "":
            flush()
            continue
        # Only keep lines that look like a level row — at least one wall.
        # This filters out meta lines like "Copyright:" that some packs
        # put after `;` would-have-been but without the `;`.
        if "#" in stripped:
            buf.append(stripped)
    flush()

    return Pack(
        name=name,
        display=display,
        credit="David W. Skinner — freely distributable with credit",
        levels=levels,
    )


def _all_packs() -> list[Pack]:
    packs: list[Pack] = []
    try:
        packs.append(_load_xsokoban())
    except Exception as e:  # pragma: no cover — vendor missing is a hard error
        raise RuntimeError(f"failed to load xsokoban pack: {e}") from e

    skinner_dir = VENDOR / "skinner"
    skinner_files = [
        ("microban", "Microban", "Microban.txt"),
        ("microban2", "Microban II", "Microban II.txt"),
        ("sasquatch", "Sasquatch", "Sasquatch.txt"),
    ]
    for name, display, fname in skinner_files:
        path = skinner_dir / fname
        if path.exists():
            try:
                pack = _load_skinner_file(path, name, display)
                if pack.levels:
                    packs.append(pack)
            except Exception as e:  # pragma: no cover
                # Don't let one bad pack take down the game.
                import sys
                print(f"warning: failed to load {fname}: {e}", file=sys.stderr)
    return packs


PACKS: list[Pack] = _all_packs()


def pack_by_name(name: str) -> Pack:
    for p in PACKS:
        if p.name == name:
            return p
    raise KeyError(f"no such pack: {name!r}. Have: {[p.name for p in PACKS]}")


def total_levels() -> int:
    return sum(len(p) for p in PACKS)
