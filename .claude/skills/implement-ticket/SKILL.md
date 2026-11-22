---
name: implement-ticket
description: Playbook for implementing a GitHub issue in this repository from start to pull request, with the project subagents run at fixed steps. Use whenever asked to implement, start, continue or finish a ticket, an issue or an epic child, for example "implement #12" or "work on the next ticket".
argument-hint: "[issue number]"
---

# Implement a ticket

Use this playbook for every implementation ticket in this repository. `CLAUDE.md` holds the commands, the architecture boundaries, the Git workflow and the evidence rules; where this playbook and `CLAUDE.md` differ, `CLAUDE.md` wins.

The project subagents in `.claude/agents/` are part of the work. Delegate to them at the steps below without waiting to be asked. If a before-coding or implementing step names a role that is not installed or cannot be run, do that step yourself and say so in the pull request. The review and acceptance gates cannot be done by the session that wrote the change: run them as the project subagents (a fresh context) or in a separate session, given only the diff, criteria and recorded output. The order is fixed: local checks, both gates, draft pull request, CI, then ready only when CI is green. No pull request is opened or marked ready until both gates have passed on the current diff.

## Steps

1. **Read the ticket.** `gh issue view <number>` and the epic it belongs to. Check that every prerequisite the epic and the ticket name is merged into `main`; a prerequisite can be part of an issue or a pull request that closes none (in epic #1, #2 needs only part 1 of #8, and #8 needs the preparation pull request). The epic's "Open decisions" have defaults that apply unless the owner changes them, so they do not block; a decision the ticket itself says to stop and ask about does. If the ticket is blocked, stop and say what blocks it.
2. **Read the rules.** `CLAUDE.md`, then the architecture notes it links to.
3. **Orient and check the approach.** Delegate as the table "Before coding" says. Settle open design questions before writing code.
4. **Branch** as the Git workflow in `CLAUDE.md` says. Never work on the default branch.
5. **UI tickets: design first.** Before changing any screen, run the `ui-ux-pro-max` skill (`python .claude/skills/ui-ux-pro-max/scripts/search.py "<product type>" --design-system`) and read `docs/ui-quality.md`.
6. **Implement** inside the ticket's stated scope. Delegate the work to the implementing role that matches the files being changed (table "While coding"). Do not widen scope; note anything else you find as a follow-up.
7. **Test.** Add or change tests for every acceptance criterion and material edge case, then run the checks listed in `CLAUDE.md`. Record each command and its result.
8. **Specialist review.** Run every role in the table "After coding" whose trigger matches the change.
9. **UI check, copy and changelog.** Both can change files the review gate hook counts as code, so they come before the gates. For UI tickets, check each changed screen against `docs/ui-quality.md`, rule by rule, and record the result. Run user-facing copy and documentation in the diff through the `unslop` skill. Add one line for the ticket to `CHANGELOG.md` under Unreleased. Fix what the check finds, re-run the tests, and keep the recorded UI-check result for the review gate.
10. **Review gate, always.** Run Code Reviewer on the full diff and give it the UI-check result from step 9. Fix every material finding, re-run the checks, and have the reviewer look again until no material finding is left.
11. **Acceptance gate, always.** Run Reality Checker with the ticket's acceptance criteria and the recorded local evidence. It checks that the documented checks passed locally and that CI is configured to run them; do not ask it about a CI result, which does not exist yet. Do not open a pull request unless it passes.
12. **Hand off.** Do not edit code after the gates; if a gate finding or CI failure forces a code change, re-run both gates on the new diff. Run the pull request text (not part of the diff) through the `unslop` skill. Capture the evidence `CLAUDE.md` asks for and fill in `.github/pull_request_template.md`. Do not push or open a pull request unless the owner asked in the current session; a `/next-ticket` run counts as that request. Open a draft pull request that names the issue only after the local checks passed and both gates passed on the current diff. Wait for CI on the draft. If CI fails, fix, re-run the local checks and both gates, and push. Mark it ready only when CI is green, and add the CI run link to the evidence. Only the owner merges; never merge.

## Roles

### Before coding

| Role | Access | Delegate to it |
|---|---|---|
| Codebase Onboarding Engineer | read-only reviewer | At the start of a ticket in an unfamiliar area, to trace the relevant code paths before anything is changed |
| Software Architect | read-only reviewer | Before implementing a ticket that adds or changes a module boundary, data model, storage schema, public API or dependency, to check the approach against the architecture notes |

### While coding

| Role | Access | Delegate to it |
|---|---|---|
| Backend Architect | can edit | When a ticket changes server-side code, HTTP routes, validation, persistence or data migrations |
| Frontend Developer | can edit | When a ticket changes browser-side code such as pages, components, client state, styling or keyboard interaction |
| Test Automation Engineer | can edit | When a ticket adds or changes tests, fixtures or a browser test harness, or when acceptance criteria need new automated checks |

### After coding

| Role | Access | Delegate to it |
|---|---|---|
| Accessibility Auditor | read-only reviewer | After a ticket changes user-facing UI, keyboard handling, focus order or markup |

### Gates that run on every ticket

| Role | Access | Delegate to it |
|---|---|---|
| Code Reviewer | read-only reviewer | After implementing or changing code for a ticket, before the work is called done or a pull request is opened |
| Reality Checker | read-only reviewer | As the last gate of every ticket, to check each acceptance criterion against evidence that was actually produced before the ticket is called done |

## Rules

- The session or role that wrote a change does not count as its reviewer.
- Read-only reviewers cannot run commands. Give them the diff, the acceptance criteria and the recorded command output.
- Where a role's general advice (frameworks, dependencies, cloud services) conflicts with `CLAUDE.md`, `CLAUDE.md` wins.
- In the pull request description, add a section "Agent roles run" listing each role that ran, what it was asked and its verdict and any step you did yourself because a role was missing.
