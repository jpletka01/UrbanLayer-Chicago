# Engineering decisions

Why the code looks the way it does: the choices made while building, the options passed over, and the evidence behind each one. The archive records *what* shipped; this folder records *why*.

- One file per build arc, named `YYYY-MM_arc-name.md`. Each queue item (PR) gets its own section, appended when the item merges.
- Record a decision when a reader of the code would reasonably ask "why this and not the obvious alternative?" That covers a deviation from the plan, a scope call, a trade-off, a test-design choice, a compatibility choice, or a bug found along the way. Skip routine edits.
- Each entry: **Decision**, **Alternatives**, **Why** (the evidence: a command, a dataset's columns, a test result), and **Revisit if** (what would make it wrong).
- Each item ends with a **Numbers** block, so a later redesign can be compared against what this one measured:
  - **Before → after** for anything the item changed, with the unit and the date measured.
  - **Reproduce:** the exact command or request that produced each number (prefer ones that spend no model tokens).
  - **Not measured:** what the item could have affected but nobody measured (latency, coverage, eval scores). A gap written down beats a number that was never taken.
  - Only numbers that were actually measured; a figure from a plan or an earlier session says so.
- Public repo: no server addresses, credentials, or private notes. Local-only plan files may be named but not linked.

## Files
- `2026-10_build-queue.md`: the confidence standard (WS0), code refresh (WS1), data health (WS6), Property Profile map repairs (WS3 Phase 1), and the truthful Property Discovery map (WS3 Phase 2), from 2026-10-20.
- `2026-10_discovery-index.md`: Property Discovery index builder fixes found by the WS8 coverage audit, from 2026-10-28.
- `2026-10_discovery-redesign.md`: the Property Discovery redesign, phase by phase: Phase 0 (draft edits, explicit "Update results", previous results kept while refreshing), from 2026-10-28.
