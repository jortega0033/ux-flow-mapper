# Owner decisions

A dated record of the decisions the owner made for this repository, so the rules do not depend on anyone's memory of a conversation. Changing any entry needs the owner. An agent that finds a decision blocking a ticket stops and says so.

All entries date from 2026-11-22, except entry 13 (2026-11-23).

| # | Decision | Date | Implemented in |
|---|---|---|---|
| 1 | The instructions, tooling and playbook live on the default branch (`main`), not on a preparation branch. | 2026-11-22 | `CLAUDE.md`, `.claude/`, `docs/` |
| 2 | Persona agents run automatically during ticket work and carry instructions tailored to this project. | 2026-11-22 | `.claude/agents/` ("In this repository" sections and "Use proactively" descriptions), `.claude/agency-agents/README.md` |
| 3 | Every open ticket is about app implementation. Tooling is installed, not ticketed. | 2026-11-22 | `.github/ISSUE_TEMPLATE/implementation-ticket.md` |
| 4 | Agents may take a ticket up to a ready pull request. Only the owner merges and releases. | 2026-11-22 | `CLAUDE.md` (Git workflow, Delivery workflow), `.claude/skills/next-ticket/SKILL.md`, `.claude/skills/implement-ticket/SKILL.md`, `docs/RELEASING.md`, `.claude/settings.json` |
| 5 | No scheduler. Ticket work starts only on the owner's go signal (`/next-ticket`), because the repository is used to train AI models. | 2026-11-22 | `.claude/skills/next-ticket/SKILL.md` (`disable-model-invocation: true`), `LOOP.md` |
| 6 | A review gate hook blocks opening or readying a pull request until the gate roles have run after the last code edit. | 2026-11-22 | `.claude/hooks/role_gate.py`, `.claude/settings.json`, `.gitignore` |
| 7 | Loop Engineering stays at L1, report-only and unscheduled. | 2026-11-22 | `LOOP.md`, `loop-constraints.md`, `loop-budget.md` |
| 8 | Continuous integration runs on Linux and Windows; the default branch requires a pull request and green checks. | 2026-11-22 | `.github/workflows/ci.yml` (job `test`); branch protection is set by the owner on GitHub |
| 9 | Permission rules: documented commands are allowed; force pushes, pushes to the default branch, merges, releases and reads of secrets are denied; edits to CI, agent configuration and Loop files ask first. | 2026-11-22 | `.claude/settings.json` |
| 10 | Open decisions on tickets are settled with the ticket's stated default (list below). | 2026-11-22 | This file; the issues named below |
| 11 | Rust is verified in CI only. Not applicable: this repository has no Rust. | 2026-11-22 | none |
| 12 | The ten UI rules in `docs/ui-quality.md` are binding, and the `ui-ux-pro-max` and `unslop` skills are installed in the repository and used for UI work and for copy. | 2026-11-22 | `docs/ui-quality.md`, `.claude/skills/ui-ux-pro-max/`, `.claude/skills/unslop/`, role checklists in `.claude/agents/` |
| 13 | Visual system: Pipenzo Flow look tokens (docs/design-tokens.md). SDLC kit version: jortega0033/sdlc-kit v1.0.0. | 2026-11-23 | `flow_mapper/static/tokens.css`, `flow_mapper/static/style.css`, `docs/design-tokens.md` |

## Entry 10: open decisions settled by the ticket default

| Issue | Decision | Setting applied |
|---|---|---|
| #1 | Router split: the pure router stays in #2; editor integration and pan and zoom moved to #9. | Stated default: split as written. |
| #1, #8 | Browser driver. | Stated default: zero-dependency DevTools Protocol client on Node 22, no `package.json`; not Playwright. |
| #1, #3 | Transitions disabled in the selected scenario. | Stated default: not drawn and not routed; they stay in the transition list with the text "not in <scenario>". |
| #1, #6 | Gate host. | Stated default: Linux with Chrome. The epic is not finished on a Windows-only run unless the owner accepts that in #6. Flag in issue: if no Linux host with Chrome is available, record a blocker in #6 and ask; do not switch silently. |
| #1, #4 | Comparing revisions. | Stated default: the read-only preview in #4 is the comparison; a visual or textual diff is out of scope and would be a follow-up issue. |
| #1 | Known gap: "connected actions" in the inspector and a pointer shortcut to connect two screens. | Stated default: left out of this batch; a small follow-up issue if the owner wants them. |

## Program decisions (owner, 2026-11-24)

The owner accepted the goal and each suggestion below. They apply from the phase they name; the rules of `CLAUDE.md` hold for phase 1 as written.

| Decision | Implemented in |
|---|---|
| The repository has a program goal above phase 1: a journey modelling and verification tool, in six phases. | Program issue #54 |
| Checking a running application needs a browser driver. Suggested: the driver the repository already plans, against local sample applications only. | Program issue #54 |
| The rule against packages outside the Python standard library stays. | Program issue #54 |
