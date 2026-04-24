# DOGFOOD — sokoban

_Session: 2026-04-23T14:48:43, driver: pty, duration: 1.5 min_

**PASS** — ran for 1.1m, captured 16 snap(s), 1 milestone(s), 0 blocker(s), 0 major(s).

## Summary

Ran a rule-based exploratory session via `pty` driver. Found no findings worth flagging. Game reached 66 unique state snapshots. Captured 1 milestone shot(s); top candidates promoted to `screenshots/candidates/`. 1 coverage note(s) — see Coverage section.

## Findings

### Blockers

_None._

### Majors

_None._

### Minors

_None._

### Nits

_None._

### UX (feel-better-ifs)

_None._

## Coverage

- Driver backend: `pty`
- Keys pressed: 535 (unique: 40)
- State samples: 93 (unique: 66)
- Score samples: 0
- Milestones captured: 1
- Phase durations (s): A=41.1, B=14.6, C=9.1
- Snapshots: `/home/brian/AI/projects/tui-dogfood/reports/snaps/sokoban-20260423-144736`

Unique keys exercised: -, /, 2, 3, 5, :, ;, ?, H, R, ], backspace, c, ctrl+l, delete, down, enter, escape, f1, f2, h, home, k, l, left, m, n, p, page_down, question_mark, r, right, shift+slash, shift+tab, space, up, v, w, x, z

### Coverage notes

- **[CN1] Phase B exited early due to saturation**
  - State hash unchanged for 10 consecutive samples during the stress probe; remaining keys skipped.

## Milestones

| Event | t (s) | Interest | File | Note |
|---|---|---|---|---|
| first_input | 0.3 | 0.0 | `sokoban-20260423-144736/milestones/first_input.txt` | key=right |
