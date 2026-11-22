# Agency Agents roles used in this repository

The Markdown files in `.claude/agents/` whose names start with `engineering-` or `testing-` are copies of role definitions from Agency Agents. They are project-local Claude Code subagents. The file `loop-verifier.md` in the same folder is not from Agency Agents; it belongs to the Loop Engineering setup described in [`LOOP.md`](../../LOOP.md).

## Source and licence

- Upstream: https://github.com/msitarzewski/agency-agents
- Pinned revision: `8ae6164602c95ca78828b148b9052460ee426885` (upstream `main`, 2026-11-09)
- Licence: MIT, "Copyright (c) 2025 AgentLand Contributors". The upstream licence text at the pinned revision is kept unchanged in [`LICENSE`](LICENSE) next to this file. It covers only the copied role files, not the rest of this repository.
- Fetched with `gh api "repos/msitarzewski/agency-agents/contents/<path>?ref=<revision>"`.

## Installed roles

"Upstream SHA-256" is the hash of the file as fetched at the pinned revision. Reviewer roles have one added frontmatter line, `tools: Read, Grep, Glob`, so they cannot edit files or run commands. Nothing else in any file was changed.

| File in `.claude/agents/` | `name:` | Upstream path | Upstream SHA-256 | Local change |
|---|---|---|---|---|
| `engineering-software-architect.md` | Software Architect | `engineering/engineering-software-architect.md` | `b85121691776147bacde26673e68fbbacd6a7f0816d1ca8e203c264d25ce1d30` | added `tools: Read, Grep, Glob` |
| `engineering-code-reviewer.md` | Code Reviewer | `engineering/engineering-code-reviewer.md` | `7509fcc3ea1dda46511b2801996305bf3d4a125576f9655ff0b63df25602f446` | added `tools: Read, Grep, Glob` |
| `engineering-codebase-onboarding-engineer.md` | Codebase Onboarding Engineer | `engineering/engineering-codebase-onboarding-engineer.md` | `07aa548b45887c3ad768efad5fdbf6e57bea639df4f1b74c7e383142f454e2a1` | added `tools: Read, Grep, Glob` |
| `testing-accessibility-auditor.md` | Accessibility Auditor | `testing/testing-accessibility-auditor.md` | `362935907af23839775b9c6162f38c0c5a740542ab4350cb5c5b5a0d9f9a4268` | added `tools: Read, Grep, Glob` |
| `testing-reality-checker.md` | Reality Checker | `testing/testing-reality-checker.md` | `6d32fcdb114233e13902ec6372d50293b120e85d490b5e81d372c29808f988a1` | added `tools: Read, Grep, Glob` |
| `engineering-backend-architect.md` | Backend Architect | `engineering/engineering-backend-architect.md` | `ac717bde4848d7663fff8a3c7edc711fd119256de6a7ce38c036619372f42c99` | none |
| `engineering-frontend-developer.md` | Frontend Developer | `engineering/engineering-frontend-developer.md` | `1ae4cc10b2e0163bd3ed921ad54080b865cd02e591becd8919b64b73fab06dad` | none |
| `testing-test-automation-engineer.md` | Test Automation Engineer | `testing/testing-test-automation-engineer.md` | `4299d038e88387546d645ccbe767b1dfdb7de10da55eba1ab103149972cd2b9b` | none |

## Why these roles

| Role | Use in this repository |
|---|---|
| Software Architect (read-only) | Review a ticket's design against the layering in [`docs/architecture.md`](../../docs/architecture.md) before code is written: module split of the browser client, the restore operation, the worker boundary. |
| Code Reviewer (read-only) | Review a diff for correctness, missed edge cases and broken invariants. |
| Codebase Onboarding Engineer (read-only) | Trace a code path and report facts with file and function citations. |
| Accessibility Auditor (read-only) | Review keyboard operation, focus handling, accessible names and live-region announcements, which the PRD treats as acceptance criteria (A2, A3). |
| Reality Checker (read-only) | Check claimed evidence against what was actually run before a ticket or the release gate is called done. |
| Backend Architect | Implement work in `flow_mapper/*.py` (HTTP layer, storage, validation). |
| Frontend Developer | Implement work in `flow_mapper/static/`. |
| Test Automation Engineer | Build the JavaScript unit tests and the browser run for the release gate. |

The three implementing roles are written for larger stacks (frameworks, cloud services, Playwright or Cypress). In this repository the rules in [`CLAUDE.md`](../../CLAUDE.md) win: Python standard library only, native HTML, CSS and JavaScript, no pip or npm dependencies, no external requests.

## Name collision with user-level agents

A developer who has installed Agency Agents in `~/.claude/agents/` already has agents with the same `name:` values. Claude Code gives the project-level definition precedence, so inside this repository the copies here are used, including the read-only tool limits. The upstream names were kept on purpose so that the roles stay recognisable and can be compared with upstream.

A Claude Code session that was already running when these files were added keeps the definitions it loaded at start. Start a new session to pick up the project copies.

## Check that the roles load

From the repository root, in a new session:

```text
claude -p "List the project-level subagents defined in .claude/agents with the tools each one may use. Then run the Reality Checker subagent and ask it which tools it has."
```

The reviewer roles must report exactly `Read, Grep, Glob`.

### What was observed, and what was not

Observed on 2026-11-22 with Claude Code 2.1.323, headless, from the repository root:

- Software Architect, Code Reviewer, Codebase Onboarding Engineer, Accessibility Auditor and Reality Checker were listed with `Read, Grep, Glob`, and a launched Reality Checker reported exactly those three tools. The user-level copies of these roles have no `tools:` line, so this shows that the project copies were the ones loaded.
- **Not shown:** that Backend Architect, Frontend Developer and Test Automation Engineer are loaded from the project copies. These three files are unchanged from upstream and have no `tools:` line, exactly like a user-level install, and the listing shows names and tools only, not where a definition comes from. Project precedence for these three is assumed from how Claude Code resolves names, not observed. On a machine without a user-level install, check that the three names are listed at all.

## Updating

Fetch the same paths at a newer revision, re-apply the `tools:` line to the five reviewer roles, and update the revision and hashes in this file in the same commit.

## Local change: automatic delegation (2026-11-22)

One sentence beginning "Use proactively" was appended to the `description:` line of every Agency Agents role in `.claude/agents/` (not to `loop-verifier`). Claude Code uses that field to decide when to delegate, so the roles now run during ticket work without being named. Nothing else in the role files changed.

A section headed `## In this repository` was then inserted in every one of those role files, directly after the closing `---` of the frontmatter and before the upstream text (again not in `loop-verifier`). It is project-specific text written for this repository, not upstream text: it states the stack and constraints, the files the role owns or reviews, the commands, the invariants to check, which parts of the generic text do not apply, and what the role hands back. It ends with the sentence "This section and CLAUDE.md override the generic text below wherever they differ." The upstream text below it is unchanged.

This supersedes any statement above that a role file is unmodified, that "nothing else in the role files changed", or that the `tools:` line is the only local change. To compare a role with the pinned upstream file, first remove the "Use proactively" sentence, the whole "In this repository" section (from its heading up to the line before the upstream `# ...` title) and the `tools:` line where one was added. When updating to a newer upstream revision, re-apply all three, and re-check the section against the repository.

The steps at which each role runs are in `.claude/skills/implement-ticket/SKILL.md`.

### Verification (2026-11-22)

Run once from the repository root with Claude Code 2.1.323, headless, after the "In this repository" sections were inserted:

```text
claude -p "List every project subagent defined in .claude/agents with its exact name and tools, say for each whether its instructions begin with a section titled In this repository, and say whether a skill named implement-ticket is available. Plain list, no commentary." --model haiku
```

Observed (exit code 0): Backend Architect, Frontend Developer and Test Automation Engineer were listed with no `tools:` line (all tools inherited); Codebase Onboarding Engineer, Code Reviewer, Software Architect, Accessibility Auditor and Reality Checker with `Read, Grep, Glob`; each of the eight was reported as starting with the "In this repository" section. `loop-verifier` was listed with `Read, Grep, Glob` and without that section. The skill `implement-ticket` was reported as available.

**Not shown:** the answer cited file line numbers, so the model read the files to produce it. It confirms that the files are in place, that the frontmatter is intact and that the skill is registered. It does not prove that a delegated subagent receives the new section, and no subagent was launched in this check.

## Local change: SDLC kit (2026-11-22)

This pass added, without changing any role's upstream text: the review gate hook (`.claude/hooks/role_gate.py`, gate roles Code Reviewer and Reality Checker) and `.claude/settings.json`; the `next-ticket` driver and updated `implement-ticket` playbook; the skills `ui-ux-pro-max` and `unslop` (each with a `PROVENANCE.md`); `docs/ui-quality.md`, `docs/owner-decisions.md` and `docs/RELEASING.md`; CI, pull request template, issue template, CODEOWNERS and Dependabot configuration under `.github/`; `SECURITY.md` and `CHANGELOG.md`. One line naming `docs/ui-quality.md` was added to the "In this repository" checklist of Frontend Developer, Accessibility Auditor and Code Reviewer. UI Designer and UX Architect are not installed here.

### Correction: stale "no CI" statements (2026-11-22)

After CI was added at `.github/workflows/ci.yml`, the "In this repository" sections still said the repository has no CI. Edited: Reality Checker (the project line, and the checklist item now requires a green, linked CI run on the pull request instead of "no CI result is claimed"), Code Reviewer (project line; "or CI" dropped from the does-not-apply line) and Test Automation Engineer (project line). Only those sections changed; the upstream text is untouched. `LOOP.md` was corrected the same way.
