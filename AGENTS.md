# AGENTS.md

The working rules for any coding agent in this repository are in [`CLAUDE.md`](CLAUDE.md). This file repeats only the commands, a pointer to the ticket workflow and the loop rules so that tools which read `AGENTS.md` find them.

## Test commands

```text
python -m unittest discover -s tests -v
```

There is no lint command, no build step and no package manager. CI runs the test command above. Python 3.12 or newer, standard library only. See `CLAUDE.md` for the run command and for the checks that are planned but do not exist yet.

## Ticket workflow

To implement a GitHub issue, follow [`.claude/skills/implement-ticket/SKILL.md`](.claude/skills/implement-ticket/SKILL.md) and the section "Agent roles and ticket work" in `CLAUDE.md`. The role definitions are in `.claude/agents/`; each starts with an "In this repository" section. A `/next-ticket` run (owner only) is the only request to push a branch and open a pull request; otherwise do neither unless the owner asks in the current session. A pull request is marked ready only after both gates passed on the current diff and CI is green, and only the owner merges. A tool that cannot run Claude Code subagents reads the matching role file and does the before-coding and implementing steps itself, and says so in the pull request. The review gate (Code Reviewer) and the acceptance gate (Reality Checker) apply to every ticket. The review and acceptance gates cannot be done by the session that wrote the change: run them as the project subagents (a fresh context) or in a separate session, given only the diff, criteria and recorded output. No pull request is opened or marked ready until both gates have passed on the current diff.

## Loop conventions

- The loop is at L1: report-only, started by hand, no scheduler, no automated fixes, no auto-merge.
- See [`LOOP.md`](LOOP.md) for the manual triage command and the human gates.
