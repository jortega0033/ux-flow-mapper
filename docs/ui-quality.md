# UI quality rules

Ten binding rules for every screen, component and piece of user-facing copy in this repository. They were set by the owner on 2026-11-22 (rules 1 and 2 as stated by the owner, rules 3 to 10 proposed and approved the same day). An agent that finds a rule blocking a ticket stops and says so; it does not bend the rule.

1. No thick accent border on one side of a card, callout, alert, list item or quote (for example `border-left: 4px solid <accent>`). Use spacing, type weight, an icon or a full hairline border instead.
2. No "soft tinted background with a thin border of the same hue" as the default way to mark a status, tag, callout or card. One neutral surface and one clear signal (text, icon or a solid chip) is enough.
3. No gradient text and no purple-to-blue gradient as a default accent.
4. No blur or glass panels, and no drop shadow plus large radius on every card.
5. No emoji used as icons or bullets, and no sparkle marks.
6. No pill or badge on things that are not states. No all-caps, letter-spaced micro labels as section decoration.
7. No centred hero with a slogan in an application screen. Screens open on the user's task.
8. One accent colour, used for the primary action and the current selection. Status colours only for status.
9. Dense, aligned layouts on a consistent spacing scale. No card grid where a table or a list is the right form.
10. User-facing copy is plain and specific: no filler, no exclamation marks, and the same word for the same thing everywhere.

## How they are applied

- A UI ticket starts with the `ui-ux-pro-max` skill (`.claude/skills/ui-ux-pro-max/`): run its design-system search for the product type before designing, for example `python .claude/skills/ui-ux-pro-max/scripts/search.py "offline diagram editor" --design-system`. This repository's constraints (native HTML, CSS and JavaScript, no external request, no dependency) win over any suggestion that conflicts with them.
- A UI ticket ends with a check of each changed screen against this file, rule by rule. The result goes in the pull request under Evidence.
- User-facing copy, documentation and pull request text go through the `unslop` skill (`.claude/skills/unslop/`) before the pull request is opened.
- Enforcement is by the review gate: Code Reviewer checks every ticket's diff against these rules, and Frontend Developer, Accessibility Auditor and Code Reviewer name this file in their checklists. It is not enforced by a script. Rule 1 can be linted with a search for a one-sided border width of 2px or more; rule 2 cannot be detected reliably from CSS, so it needs a human or reviewer reading the styles.
- Existing breaches (the five findings in `flow_mapper/static/style.css`, `app.js` and `index.html`) are not fixed here. A ticket for them is pending: the owner creates it, and until then no ticket lists them.
- Colours come from the Pipenzo tokens in `flow_mapper/static/tokens.css`; see [`docs/design-tokens.md`](design-tokens.md) for the roles and the rule that new UI adds no colour literals.
