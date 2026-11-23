# Design tokens

The colours of this client come from the Pipenzo "Flow look" token file, `flow_mapper/static/tokens.css`. The file is a byte copy (LF line endings, git blob `41d6d6db`) and is never edited here. The type, space, radius and motion tokens are defined in it, but this client has not adopted them yet; adopting them would be a layout change for a later ticket.

## Source and resync

- Source: `jortega0033/clip-to-reel-studio`, `extension/sidepanel/tokens.css`, commit `a13378ce73e5b27213c9a200fc960ec93afef054` (2026-11-21).
- Resync: `git -C <clip-to-reel-studio checkout> show <commit>:extension/sidepanel/tokens.css > flow_mapper/static/tokens.css`, then check `git hash-object flow_mapper/static/tokens.css` against the source blob and that `git ls-files --eol` shows `i/lf`. Do not copy the working-tree file (it can be CRLF). Nothing else changes. `index.html` loads it before `style.css`; the server already serves any `.css` file in the static folder, so there is no allowlist to update.

## Rule

New UI uses these tokens; no new colour literals (no hex, `rgb()`, `hsl()` or named colour) in `style.css`, `app.js` or `index.html`. Script code that needs a colour reads it with `getComputedStyle(document.documentElement).getPropertyValue('--token')`. If a token is missing, ask the owner; do not add a local value. Yellow (`--primary`) is for the primary action and the current-step marker only; red (`--danger`) is for danger only; text never sits on a bare alpha layer.

## Light and dark

Dark is the primary design (black page). The `:root` block is the matching light theme; the dark values apply inside `@media (prefers-color-scheme: dark)`, so the operating system colour scheme decides. There is no manual switch.

## Token names by role

| Role | Tokens |
|---|---|
| Surfaces | `--bg`, `--bg-raised`, `--surface`, `--bg-sunken` |
| Text | `--fg`, `--muted`, `--faint`, `--on-media` |
| Lines and controls | `--border`, `--hairline`, `--control-border`, `--input-border` |
| Accent (one) | `--primary`, `--primary-press`, `--primary-edge`, `--on-primary`, `--focus`, `--ring-accent` |
| Status | `--success`, `--ok`, `--ok-bg`, `--warn-fg`, `--warn-bg`, `--danger`, `--danger-bg`, `--info` |
| Dark blocks | `--ink`, `--on-ink`, `--on-ink-muted`, `--ink-border`, `--hero-bg`, `--on-hero`, `--on-hero-muted`, `--hero-chip-border`, `--hero-border` |
| Alpha layers | `--glass`, `--glass-strong`, `--glass-border`, `--glass-highlight`, `--glass-video`, `--glass-video-border`, `--scrim`, `--ink-hover`, `--state-hover`, `--state-selected`, `--btn-secondary`, `--btn-secondary-border` |
| Shadow, blur, gradient | `--shadow-1` to `--shadow-3`, `--shadow-float`, `--shadow-on-video`, `--shadow-on-video-lg`, `--hero-shadow`, `--blur`, `--grad-canvas`, `--grad-scrim-bottom`, `--grad-ink` |
| Type | `--font`, `--font-display`, `--mono` |
| Space and radius | `--space-1` to `--space-7`, `--radius-control`, `--radius-card`, `--radius-media`, `--radius-hero`, `--radius-chip`, `--radius-pill` |
| Motion | `--dur-1` to `--dur-4`, `--ease-out`, `--ease-in-out` |

The client currently uses the surface, text, line, accent, status and `--scrim` tokens. The shadow, blur and gradient tokens exist in the file; `docs/ui-quality.md` rules 3 and 4 still apply to how they are used.
