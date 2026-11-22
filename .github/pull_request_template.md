## Ticket

Closes #

## What changed

<!-- What the change does and why, in plain sentences. -->

## Evidence

<!-- Each command you ran and its result line. See CLAUDE.md, "Evidence before calling a ticket done". -->

| Command | Result |
|---|---|
| `python -m unittest discover -s tests -v` | |

## Agent roles run

| Role | What it was asked | Verdict |
|---|---|---|
| Code Reviewer (review gate) | | |
| Reality Checker (acceptance gate) | | |

## Risks and rollback

<!-- What could break, and how to undo this change. -->

## Checklist

- [ ] Both gates passed on the current diff
- [ ] CI is green
- [ ] `CHANGELOG.md` has a line under Unreleased
- [ ] UI changes checked against `docs/ui-quality.md`
- [ ] Copy and description read through the `unslop` skill
- [ ] Docs updated where a boundary, invariant or status changed
