# Offline UX Flow Mapper

A local tool for mapping how screens in an app connect. The first milestone (M1) is a keyboard-accessible editor that saves a flow to SQLite and reopens it after a restart. The product plan is in [docs/PRD.md](docs/PRD.md).

Everything runs on `127.0.0.1` with the Python standard library and a native HTML/CSS/JavaScript front end. There are no pip or npm dependencies and no external network requests.

## Status

| Area | State |
|---|---|
| M1 · create, add, label, move and remove screens, mark a start, create and delete directed actions, save revisions, reopen after restart (A1–A3) | Implemented |
| Straight-line connectors | Implemented (placeholder for M2) |
| Orthogonal routing (A4–A5), scenario analysis (A6–A7), history and restore (A8–A9), SVG/JSON export and import (A10), full offline integration run (A11) | Not built |

Verification status: automated tests and the browser demo have **not been recorded as run** in this tree. Results belong in the "Evidence" section below once someone has run them.

## Requirements

- Python 3.12 or newer.
- Chrome for the browser checks. The server itself works with any current browser.

## Quickstart

```text
python -m flow_mapper --data-dir ./data --port 8765
```

Open `http://127.0.0.1:8765/`. The flow list starts empty. Stop the server with Ctrl+C. Data is kept in `<data-dir>/flow_mapper.sqlite3`; start the server again with the same `--data-dir` to reopen saved flows. `data/` is ignored by Git.

The server binds to `127.0.0.1` only, rejects requests whose `Host` is not `127.0.0.1:<port>` or `localhost:<port>`, and requires a same-origin `Origin` header on every write.

## Run the tests

```text
python -m unittest discover -s tests -v
```

The tests use disposable temporary directories, start real loopback HTTP servers on ephemeral ports, and use synthetic fixtures only.

## Demo flow (opt-in)

Nothing is created automatically. To see a populated flow:

1. Start the server and open the page.
2. Choose **Create demo flow**. This creates "Demo: checkout journey", a fictional eight-screen graph with an Online and an Offline scenario. Scenarios are stored but not shown in M1.
3. Select the screen **Shipping** in the screen list. Use **Move right**, or the **X** and **Y** fields, or the arrow keys while the screen is focused on the canvas.
4. Set **X** for **Shipping** to 27 (it stays at Y 4). **Order placed** sits at 31, 4, so the footprints would overlap. The move is refused, the previous position is restored and the message says why.
5. Choose **Remove screen** for **Shipping**. The dialog focuses **Cancel**. Cancel keeps everything. Open it again and choose **Remove**; the screen and its connected actions disappear in one change.
6. Select **Cart**, tick **Start screen** if needed, choose **Add screen**, rename it with **Screen label**, then use **Transition source**, **Transition target**, **Transition label** and **Add transition**.
7. Choose **Save**. The status reads "Saved · revision 2".
8. Stop the server (Ctrl+C) and start it again with the same `--data-dir`. Open the flow from the **Flow list**. The graph, positions and revision number are unchanged.

To check blocked external access, run the server with the machine's network disabled or Chrome started with a proxy that refuses non-loopback hosts. The page loads no remote fonts, scripts, styles or images, and the Content-Security-Policy header restricts every fetch to the same origin.

## HTTP API (M1)

| Route | Purpose |
|---|---|
| `GET /api/v1/health` | Readiness |
| `GET /api/v1/flows` | List flows |
| `POST /api/v1/flows` | Create a flow from `title` or a full `graph` (client-supplied `id` and `requestId`) |
| `GET /api/v1/flows/{id}` | Current graph and revision |
| `POST /api/v1/flows/{id}/revisions` | Save a full graph at a base version (`op: "save"`) |
| `GET /api/v1/flows/{id}/revisions` | Revision list |
| `GET /api/v1/flows/{id}/revisions/{version}` | Immutable graph for a revision |

Saves are idempotent per `requestId`, reject stale base versions with `409 version_conflict`, and commit the revision and the new head in one `BEGIN IMMEDIATE` transaction. Errors have the shape `{"error": {"code", "message", "details"?}}`.

## Limitations

- One author, fixed 100 by 70 grid, fixed 6 by 3 screen size, one arrow per ordered pair of screens.
- Connectors are straight lines and can cross screens. Deterministic routing is future work.
- No pan or zoom controls (planned in UFM-03).
- Scenarios exist in the data but are not editable or analyzed in M1.
- No history view, restore, SVG export or JSON import in the UI.
- See the baseline verification below for the environments and workflow tested.

## Layout

```text
flow_mapper/        Python package (server, storage, graph validation) and static/ front end
tests/              unittest suite with synthetic fixtures
docs/PRD.md         requirements and technical specification
```

## Evidence

No verification has been recorded yet.

## Baseline verification

- The unit suite passed on Windows with Python 3.13 and on Ubuntu 24.04 in WSL2 with Python 3.12 (73 tests on Ubuntu). On Linux, use `python3` in the launch and test commands if `python` is unavailable.
- Windows Chrome 157 ran the workflow with external browser requests blocked. Created two screens, moved a screen with the keyboard, added a transition, then saved and reopened the flow after a server restart. The browser reported no uncaught page errors.
