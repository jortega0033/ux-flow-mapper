# AGENTS.md

The working rules for any coding agent in this repository are in [`CLAUDE.md`](CLAUDE.md). This file repeats only the commands and the loop rules so that tools which read `AGENTS.md` find them.

## Test commands

```text
python -m unittest discover -s tests -v
```

There is no lint command, no build step and no package manager. Python 3.12 or newer, standard library only. See `CLAUDE.md` for the run command and for the checks that are planned but do not exist yet.

## Loop conventions

- The loop is at L1: report-only, started by hand, no scheduler, no automated fixes, no auto-merge.
- See [`LOOP.md`](LOOP.md) for the manual triage command and the human gates.
