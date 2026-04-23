# DOGFOOD — sokoban-tui

_Session: 2026-04-23T10:10:16, driver: pilot, duration: 8.0 min_

**PASS** — ran for 1.8m, captured 8 snap(s), 3 milestone(s), 0 blocker(s), 1 major(s).

## Summary

Ran a rule-based exploratory session via `pilot` driver. Found **1 major(s)**. Game reached 3 unique state snapshots. Captured 3 milestone shot(s); top candidates promoted to `screenshots/candidates/`. 4 coverage note(s) — see Coverage section.

## Findings

### Blockers

_None._

### Majors
- **[M1] state appears frozen during golden-path play**
  - Collected 10 state samples; only 1 unique. Game may not be receiving keys.
  - Repro: start game → press right/up/left/down repeatedly

### Minors

_None._

### Nits

_None._

### UX (feel-better-ifs)

_None._

## Coverage

- Driver backend: `pilot`
- Keys pressed: 193 (unique: 22)
- State samples: 25 (unique: 3)
- Score samples: 0
- Milestones captured: 3
- Phase durations (s): A=17.4, B=41.9, C=48.1
- Snapshots: `/tmp/tui-dogfood-rw-20260423-100821/reports/snaps/sokoban-tui-20260423-100828`

Unique keys exercised: /, 3, :, ?, H, R, c, down, enter, escape, h, left, n, p, question_mark, r, right, shift+slash, space, up, w, z

### Coverage notes

- **[CN1] Phase A exited early due to saturation**
  - State hash unchanged for 10 consecutive samples after 9 golden-path loop(s); no further learning expected.
- **[CN2] help modal discovered via high-value key probe**
  - Pressing '?' changed screen='Screen' → 'HelpScreen' / stack_len=1 → 2. Previously-undiscovered help surface.
- **[CN3] Phase B exited early due to saturation**
  - State hash unchanged for 10 consecutive samples during the stress probe; remaining keys skipped.
- **[CN4] help key opened a previously-undiscovered modal**
  - Pressing '?' pushed a new screen during the stress probe — worth inspecting the milestone snapshot for help-text quality.

## Milestones

| Event | t (s) | Interest | File | Note |
|---|---|---|---|---|
| first_input | 0.6 | 6155.3 | `sokoban-tui-20260423-100828/milestones/first_input.svg` | key=right |
| new_modal | 42.1 | 2146.0 | `sokoban-tui-20260423-100828/milestones/new_modal-03.svg` | Screen → HelpScreen |
| high_density | 53.1 | 6239.0 | `sokoban-tui-20260423-100828/milestones/high_density.svg` | interest=6239.0 |
