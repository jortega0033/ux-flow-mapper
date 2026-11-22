# Loop Configuration — Minimal Triage (Claude Code)

Scaffolded with Loop Engineering (`@cobusgreyling/loop@0.2.0`, MIT, https://github.com/cobusgreyling/loop-engineering) using `init . --pattern daily-triage --tool claude`. The generated files were then adapted to this repository: project name, real test command, manual start instead of a schedule, and tighter constraints.

## Active Loops

| Pattern | Cadence | Status | Command |
|---------|---------|--------|---------|
| Daily Triage (`daily-triage`) | Manual, at most once a day. No scheduler. | L1 report-only | See "Next manual triage run" |

Nothing runs on its own. The generated starter suggested `/loop 1d $loop-triage`; that schedule is deliberately not used.

## Next manual triage run

A run rewrites two tracked files, `STATE.md` and `loop-run-log.md`, and leaves them modified in the working tree. So that this never lands on `main` or in a feature branch by accident, the person who starts the run prepares a branch first (the loop itself creates no branch and no commit):

```text
git fetch origin
git switch -C loop/triage origin/main
```

Start only from a clean working tree. Never run the loop on `main` or on a `feature/...` branch. After the run, read `STATE.md`, then either keep the report (commit only `STATE.md` and `loop-run-log.md` on `loop/triage` and open a pull request, as [`CLAUDE.md`](CLAUDE.md) describes) or drop it with `git restore STATE.md loop-run-log.md`. Both steps are done by a person.

From the repository root, on that branch, in an interactive Claude Code session, paste:

```text
Run the loop-constraints skill, then the loop-budget skill, then the loop-triage skill once, in report-only mode.
Inputs: `gh issue list --state open`, `gh pr list --state open`, `git log --since="48 hours ago" origin/main`,
and one run of `python -m unittest discover -s tests`. CI results come from `gh pr checks` where a pull request exists.
Do not edit any file except STATE.md and loop-run-log.md. Do not commit, push, comment, label or open anything.
Update STATE.md and append one entry to loop-run-log.md.
```

## Ticket work is not a loop run

Implementing a ticket is not a loop run. The owner starts it with `/next-ticket`, and it is governed by [`CLAUDE.md`](CLAUDE.md), the `implement-ticket` playbook, the review gate hook, CI and branch protection. The loop stays report-only, unscheduled and at L1.

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
| `.claude/skills/loop-triage/`, `loop-budget/`, `loop-constraints/` | The three skills a run uses, as generated, with one change: the `loop-constraints` skill stops when `loop-constraints.md` is missing (the generated text fell back to a `docs/safety.md` that this repository does not have). |
| `.claude/agents/loop-verifier.md` | Checker for a later L2 setup. Not used at L1. Limited to `Read, Grep, Glob`, like the other reviewer roles, so nothing in the L1 setup can run commands or edit. Its instructions tell it to run the tests itself; without `Bash` it answers `ESCALATE_HUMAN` instead. Moving to L2 means the owner adds `Bash` back to its `tools:` line in the same change that updates `loop-constraints.md` and this file. |

## Recorded health check

Run on 2026-11-22 from the repository root, after the adaptations above:

| Command | Result |
|---|---|
| `npx --yes @cobusgreyling/loop@0.2.0 doctor .` | exit 0, `Status: HEALTHY`, `Ready: 100/100 L2`, `state=STATE.md LOOP.md=yes budget=yes run-log=yes gate=no` |
| `npx --yes @cobusgreyling/loop@0.2.0 status .` | exit 0, `Pattern: daily-triage`, `State: STATE.md · never`, `constraints=yes`, no recent runs |

Run again on 2026-11-22 after the files were committed and after `loop-verifier` was limited to `Read, Grep, Glob`:

| Command | Result |
|---|---|
| `npx --yes @cobusgreyling/loop@0.2.0 doctor .` | exit 0, `Status: HEALTHY`, `Ready: 100/100 L3`, `state=STATE.md LOOP.md=yes budget=yes run-log=yes gate=no` |
| `npx --yes @cobusgreyling/loop@0.2.0 status .` | exit 0, `Pattern: daily-triage`, `Ready: 100/100 L3`, `State: STATE.md · never`, `constraints=yes`, no recent runs |

The label moved from L2 to L3 although no loop run has taken place. The tool counts any Git commit that touched `STATE.md` or `loop-run-log.md` in the last 14 days as "loop activity" (read in the tool's `loop-audit` code, `detectLoopActivity`), and the commit that added those two files is such a commit. The label will fall back once that commit is older than 14 days. It says nothing about this repository being ready for L3.

"Ready: 100/100 L2" or "L3" is the tool's score for which files exist and how recently they changed. It is not the operating level. The operating level is L1 report-only. Doctor's suggested next actions (a `docs/safety.md`, issue and pull request templates, workflows, a pattern registry) were not followed: the denylist lives in `loop-constraints.md`. CI now exists at `.github/workflows/ci.yml` (Python test suite and hook self-test); the loop does not use it as a gate and stays report-only.

## Links

- Pattern: [daily-triage](https://github.com/cobusgreyling/loop-engineering/blob/959fad23efa52456d3b478bd78eca1b1b4d9e88a/patterns/daily-triage.md)
- Checklist: [loop-design-checklist](https://github.com/cobusgreyling/loop-engineering/blob/959fad23efa52456d3b478bd78eca1b1b4d9e88a/docs/loop-design-checklist.md)
