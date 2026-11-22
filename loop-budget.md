# Loop Budget — ux-flow-mapper

> Primary loop: **Daily Triage** (scaffolded by loop-init, pattern `daily-triage`). Operating level: L1 report-only, started by hand.

## Daily limits

| Loop | Max runs/day | Max tokens/day | Max sub-agent spawns/run |
|------|--------------|----------------|--------------------------|
| Daily Triage | 2 | 100k | 0 (L1) |

## On budget exceed

1. Stop. There is no scheduler to pause; do not start another manual run that day.
2. Append the event to `loop-run-log.md`.
3. Note it under High Priority in `STATE.md` for the owner.

## Kill switch

- Flag: a line `loop-pause-all` under High Priority in `STATE.md`. While it is there, a run exits immediately.
- Only the owner removes the flag.

## Estimate spend

```bash
npx @cobusgreyling/loop-cost --pattern daily-triage --level L1
```
