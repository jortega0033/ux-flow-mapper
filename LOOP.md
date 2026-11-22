# Loop Configuration — Minimal Triage (Claude Code)

Scaffolded with Loop Engineering (`@cobusgreyling/loop@0.2.0`, MIT, https://github.com/cobusgreyling/loop-engineering) using `init . --pattern daily-triage --tool claude`. The generated files were then adapted to this repository: project name, real test command, manual start instead of a schedule, and tighter constraints.

## Active Loops

| Pattern | Cadence | Status | Command |
|---------|---------|--------|---------|
| Daily Triage (`daily-triage`) | Manual, at most once a day. No scheduler. | L1 report-only | See "Next manual triage run" |

Nothing runs on its own. The generated starter suggested `/loop 1d $loop-triage`; that schedule is deliberately not used.

## Next manual triage run

From the repository root, in an interactive Claude Code session, paste:

```text
Run the loop-constraints skill, then the loop-budget skill, then the loop-triage skill once, in report-only mode.
Inputs: `gh issue list --state open`, `gh pr list --state open`, `git log --since="48 hours ago" origin/main`,
and one run of `python -m unittest discover -s tests`. There is no CI to read.
Do not edit any file except STATE.md and loop-run-log.md. Do not commit, push, comment, label or open anything.
Update STATE.md and append one entry to loop-run-log.md.
```

## Human Gates

- The loop stays at L1 until the owner decides otherwise. No automated source fixes, no auto-merge, no scheduled runs.
- The binding rules are in [`loop-constraints.md`](loop-constraints.md). Budget and the kill switch are in [`loop-budget.md`](loop-budget.md).
- Every change to the product goes through an issue, a branch and a reviewed pull request as described in [`CLAUDE.md`](CLAUDE.md).

## Worktrees

- Not used at L1; a report-only run changes no source files.
- If the owner later moves to L2: one worktree per fix attempt, discarded after a `loop-verifier` REJECT.

## Connectors (MCP)

- None needed. The run uses the `gh` CLI and local `git` read commands.

## Budget

- Max sub-agent spawns per run: 0 (L1)
- Review `STATE.md` after each run

## Files

| File | Purpose |
|---|---|
| `STATE.md` | What the last run found. Rewritten by each run. |
| `loop-run-log.md` | One JSON entry per run. |
| `loop-budget.md` | Daily caps and the kill switch. |
| `loop-constraints.md` | Binding rules, read first on every run. |
| `.claude/skills/loop-triage/`, `loop-budget/`, `loop-constraints/` | The three skills a run uses, as generated. |
| `.claude/agents/loop-verifier.md` | Checker for a later L2 setup. Limited to `Read, Grep, Glob, Bash` so it can run tests but not edit. Not used at L1. |

## Recorded health check

Run on 2026-11-22 from the repository root, after the adaptations above:

| Command | Result |
|---|---|
| `npx --yes @cobusgreyling/loop@0.2.0 doctor .` | exit 0, `Status: HEALTHY`, `Ready: 100/100 L2`, `state=STATE.md LOOP.md=yes budget=yes run-log=yes gate=no` |
| `npx --yes @cobusgreyling/loop@0.2.0 status .` | exit 0, `Pattern: daily-triage`, `State: STATE.md · never`, `constraints=yes`, no recent runs |

"Ready: 100/100 L2" is the tool's score for which files exist. It is not the operating level. The operating level is L1 report-only. Doctor's suggested next actions (a `docs/safety.md`, issue and pull request templates, workflows, a pattern registry) were not followed: this repository has no CI, and the denylist lives in `loop-constraints.md`. `gate=no` means no CI gate workflow exists, which is intended.

## Links

- Pattern: [daily-triage](https://github.com/cobusgreyling/loop-engineering/blob/959fad23efa52456d3b478bd78eca1b1b4d9e88a/patterns/daily-triage.md)
- Checklist: [loop-design-checklist](https://github.com/cobusgreyling/loop-engineering/blob/959fad23efa52456d3b478bd78eca1b1b4d9e88a/docs/loop-design-checklist.md)
