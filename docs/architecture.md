# Architecture and baseline status

This document describes the code as it is on `main` at commit `7672e0c` and compares it with [`PRD.md`](PRD.md). It was written during a preparation pass on 2026-11-22 that changed no product code. The requirements stay in the PRD; this file records what exists, what is planned, and what has not been verified.

Status words used below:

- **Implemented**: the code exists and the stated check was run during the preparation pass.
- **Planned**: the PRD asks for it and the code does not have it.
- **Needs verification**: the code or a claim exists, and nobody has recorded a run that proves it.

File and line references are for commit `7672e0c`. Function names are given so the references survive edits.

## 1. Shape of the system

A single Python process serves both a JSON API and the browser client from one loopback origin. There are four layers, each in one module:

```text
Browser client   flow_mapper/static/index.html, style.css, app.js   (native HTML, CSS, one ES module)
        |  fetch, same origin, JSON
HTTP layer       flow_mapper/server.py     ThreadingHTTPServer bound to 127.0.0.1
        |  method calls, ApiError
Storage          flow_mapper/storage.py    all SQL; one fresh SQLite connection per operation
        |  validate_graph()
Validation       flow_mapper/graph.py      pure functions, no I/O
        |
SQLite file      <data-dir>/flow_mapper.sqlite3   (WAL journal, user_version 1)
```

`flow_mapper/__main__.py` is the command line entry point (`main`, lines 17 to 36). `flow_mapper/errors.py` holds `ApiError`, the one exception type that storage raises and the HTTP layer turns into a JSON error body.

There is no framework, no package manifest, no build step and no dependency outside the Python standard library and the browser.

## 2. Module boundaries

| Module | Owns | Must not do |
|---|---|---|
| `graph.py` | The graph envelope rules and the normalized form: `validate_graph` (138 to 143), `_validate` (146 to 257), `empty_graph` (53 to 67), `default_scenario_id` (49 to 50). | Any I/O. It imports nothing from the package. |
| `storage.py` | The schema (`_DDL`, 16 to 33), every SQL statement, transactions (`Store._txn`, 119 to 143), request hashing (`_hash`, 49 to 51), idempotent replay. Raises `ApiError`. | HTTP concerns. It calls `validate_graph` itself, so no caller can store an unvalidated graph. |
| `server.py` | Host and Origin checks, routing (`_ROUTES`, 34 to 43), body parsing (`_read_json`, 196 to 219), security headers (`_SECURITY_HEADERS`, 24 to 33), static files (`_send_static`, 242 to 257). | SQL or graph rules. It only checks the request's key set and the `op` value (`_save`, 229 to 240) and delegates. |
| `static/app.js` | The working draft, rendering, keyboard and pointer input, the save and conflict flow. | Trusting itself: every rule it applies before a save is applied again by the server. |

## 3. Data ownership

- **The server owns revisions.** A revision row is written once and never updated. `flow.revision` points at the current one. `get_flow` (`storage.py` 223 to 239) joins the two.
- **The browser owns the draft.** `state.draft` is the working graph. `state.base` is the client's copy of the last revision the server confirmed (`app.js` 16 to 31). "Unsaved changes" means the canonical forms of the two differ (`canon`, `isDirty`, 80 to 99).
- **One file is the only persistent store**: `<data-dir>/flow_mapper.sqlite3`. `data/` and `*.sqlite*` are ignored by Git.
- **Graph data is independent of the view.** The stored graph has no camera, selection or route information.

## 4. Invariants and where they are enforced

| Invariant | Enforced in | Covered by |
|---|---|---|
| The envelope has exactly the keys `schemaVersion, title, startId, scenarios, screens, transitions`; unknown keys are rejected at every level. | `graph._object` (88 to 102), `_validate` | `test_graph.test_unknown_keys_and_versions_rejected` |
| Labels are trimmed, NFC-normalized, free of control and line-separator characters, and counted in code points (title 120, scenario 60, screen 80, transition 120). | `graph._label` (74 to 85) | `test_labels_are_trimmed_and_nfc_normalized`, `test_label_length_counts_code_points`, `test_control_characters_and_blank_labels_rejected` |
| 1 to 8 scenarios with labels unique after case folding; 0 to 80 screens; 0 to 160 transitions. | `_validate` (162, 181, 219) | `test_scenario_count_limits`, `test_scenario_labels_unique_after_casefold`, `test_screen_limit` |
| A screen's top-left corner is at `0 <= x <= 94`, `0 <= y <= 67`; the footprint is 6 by 3; two screens overlap when `abs(dx) < 6 and abs(dy) < 3`; touching is allowed. | `graph.py` constants (19 to 22), `_validate` (191 to 205) | `test_overlap_rejected_but_touching_allowed`, `test_grid_bounds` |
| `startId` is null or a screen of kind `screen`. An exit has no outgoing transition. One transition per ordered pair. A self-transition on a non-exit is valid. | `_validate` (207 to 246) | `test_exit_rules`, `test_self_transition_allowed_duplicate_pair_rejected`, `test_dangling_endpoints_and_start` |
| `enabledIn` is null or a non-empty list of unique known scenario IDs. | `graph._enabled_in` (260 to 277) | `test_enabled_in_rules` |
| The stored graph is normalized: arrays sorted by ID, fixed key order, sorted `enabledIn`. | `_validate` (250 to 257) | `test_normalization_is_idempotent_and_order_independent` |
| A save with a known `requestId` and the same payload returns the original result; with a different payload it is a `409 request_conflict`. This check comes before the base-version check. | `Store.save_revision` (266 to 289) | `test_storage.test_replay_returns_original_commit_even_with_newer_head`, `test_replay_check_precedes_base_version_check`, `test_same_request_id_with_different_payload_conflicts` |
| A save whose `baseVersion` is not the head is a `409 version_conflict` and changes nothing. | `save_revision` (291 to 297) | `test_stale_base_conflicts_and_head_is_untouched` |
| The new revision row and the new head commit together or not at all (`BEGIN IMMEDIATE`). | `save_revision` (258 to 311), `fault_hook` seam at 306 to 307 | `test_mid_save_failure_rolls_back_and_retry_commits_once` |
| A locked database is a `503 database_busy` with `Retry-After: 1`. | `storage._busy_error` (62 to 66), `server._send_error` (133 to 141) | `test_lock_contention_returns_database_busy` |
| A database written by a newer schema refuses to start. | `Store._init_db` (89 to 117) | `test_future_schema_version_is_refused` |
| Only `127.0.0.1:<port>` and `localhost:<port>` are accepted as `Host`; every `POST` needs `Origin` equal to `http://<Host>`. | `_Handler._process` (146 to 153) | `test_http.RequestGuardTests` |
| Bodies are JSON objects of at most 512 KiB, with no duplicate keys and no `NaN` or `Infinity`. | `_read_json` (196 to 219) | `test_oversized_body_is_413`, `test_malformed_and_non_object_json` |
| Every response carries `Content-Security-Policy: default-src 'self'; script-src 'self'; ...`, `no-store`, `nosniff`, `no-referrer`. | `_SECURITY_HEADERS`, `_send` (115 to 127) | `test_security_headers_on_api_and_static` |
| The client loads nothing external, has no inline script, style or handlers, and never writes user text through an HTML sink. | Convention in `static/` | `test_static_and_cli.StaticAssetLintTests` (a text scan of the files directly inside `static/`) |

Two rules exist twice and can drift apart: the grid and footprint constants and the overlap test are in `graph.py` (19 to 22, 203) and again in `app.js` (3 to 9, `overlapOrBounds` 424 to 430). The limits of 80 screens and 160 transitions are also in both, but on the server they are not named constants: they are literal arguments of the `_array` calls in `_validate` (181 and 219), so a test can compare them only through `validate_graph`'s behaviour. `CELL` in `app.js` (10 pixels per grid unit) is a drawing scale and has no server counterpart. The server is the authority; the client copy only gives earlier feedback.

## 5. Traced workflow: move a screen, save, restart, reopen

This path was read in the source and then run once in a browser (see section 9).

1. **Start.** `python -m flow_mapper --data-dir D --port N` calls `main` (`__main__.py` 17 to 36), which calls `create_server` (`server.py` 55 to 60). `Store.__init__` (`storage.py` 77 to 82) creates the directory and `_init_db` creates the two tables and sets `user_version` to 1. The process prints `Serving on http://127.0.0.1:N/`.
2. **Load.** `GET /` returns `index.html`, which loads `/static/style.css` and `/static/app.js` as an ES module. `boot` (`app.js` 978 to 985) lists the flows and opens the one named in `#flow=<id>`, if any.
3. **Edit.** With a canvas screen focused, an arrow key reaches the `keydown` handler on `#nodes` (889 to 910), which calls `moveScreen` (432 to 451). `overlapOrBounds` (424 to 430) refuses a move outside the grid or onto another screen and the position stays as it was. An accepted move changes `state.draft`, announces `Moved <label> to x X, y Y` in the live region and re-renders. The **Move** buttons and the **X** and **Y** fields call the same function.
4. **Save.** `save` (723 to 776) freezes `{flowId, requestId, baseVersion, graph}` in `state.pending` and sends `POST /api/v1/flows/{id}/revisions` with `op: "save"`. The frozen request is kept until its outcome is known; after a network error or a 5xx the next **Save** sends the same request again.
5. **HTTP layer.** `_process` (`server.py` 145 to 194) checks `Host`, then `Origin`, matches the route, reads the JSON body and calls `_save` (229 to 240), which requires exactly the keys `requestId, baseVersion, op, graph` and `op == "save"`.
6. **Storage.** `Store.save_revision` (`storage.py` 241 to 319) checks that the flow exists, validates and normalizes the graph, then inside one `BEGIN IMMEDIATE` transaction: replay check, base-version check, `INSERT` of the revision, `UPDATE` of the flow head. It returns `commitVersion`, the current `head`, the normalized graph and `replayed`.
7. **Result.** The client sets `state.base` to the committed revision, shows `Saved · revision N` and refreshes the flow list. If the response says the head is newer than the committed version, or the server answers `409 version_conflict`, the client enters the conflict state and keeps the draft (750 to 766).
8. **Restart and reopen.** A new process on the same `--data-dir` reads the same file. `GET /api/v1/flows` lists the flow with its revision number and `get_flow` returns the head graph.

## 6. Capability status against the PRD

| PRD item | Status | Evidence |
|---|---|---|
| A1 create, save, restart, reopen | **Implemented** | `test_http.JourneyTests.test_a1_create_save_restart_reopen`; `test_static_and_cli.CliTests` starts the real command; browser run in section 9. |
| A2 add, label, connect, move with keyboard and screen list | **Implemented** in code (`addScreen` 458 to 485, `addTransition` 522 to 543, `moveScreen`). Move by button and by arrow key was run in a browser. Add screen, label editing and add transition **need verification** in a browser; no automated browser check exists. Two editor details from the PRD's "Editor behavior" text are **not implemented** and are outside the A2 acceptance row: "connected actions" in the screen inspector and the optional pointer shortcut to connect on the canvas (section 7, "Editor details"). | Section 9 |
| A3 remove with cancel and confirm; overlap refusal | **Implemented**; both were run in a browser. The server side is covered by `test_a3_overlap_save_rejected_and_nothing_committed` and `test_a3_delete_with_incident_edges_saves_in_one_revision`. | Section 9 |
| A4, A5 orthogonal routing, `blocked` and `search_budget`, worker | **Planned** (#2 pure router, #9 worker and drawing) | `renderCanvas` (`app.js` 335 to 420) draws one straight `<line>` per transition and a curve for a self-transition. There is no router and no worker. |
| Pan and zoom controls | **Planned** (#9) | The canvas is a fixed `viewBox="0 0 1000 700"` that scrolls in its pane. |
| A6, A7 scenario selection and analysis | **Planned** (#3) | Scenarios and `enabledIn` are validated, stored and returned unchanged. The client never reads them. No analysis code exists in Python or JavaScript. |
| A8 stale tab, conflict, replay | Server and editor logic **implemented** and unit tested (`SaveTests`, `test_replay_after_lost_response`, `test_conflict_response_reports_latest_revision`). The two-tab browser run **needs verification** (#4). | `save`, `reloadLatest` (778 to 791), `downloadDraft` (793 to 803) |
| A9 history, read-only preview, restore | **Partly implemented.** `GET .../revisions` and `GET .../revisions/{version}` exist (`list_revisions` 321 to 337, `get_revision` 339 to 360; `test_revision_history_routes`). **Planned** (#4): the restore operation (the server rejects every `op` except `save`, `server.py` 235 to 236), the `restored_from` column is always NULL, and there is no history or preview UI. | |
| A10 SVG export, JSON export and import | **Planned** (#5). The create route already accepts a full `graph` (`create_flow` 161 to 221), which import can use. The conflict flow can download the draft as JSON (`downloadDraft`). There is no export view, no import control and no SVG writer. | |
| A11 offline end-to-end run with external requests blocked | **Needs verification** (#6). No script, request log or recorded result is in the repository. | |
| JavaScript unit tests with `node --test`; browser automation | **Planned** (#8). There are no JavaScript tests and no browser driver in the repository. | |

## 7. Material drift between the PRD and the code

| Topic | PRD says | Code does | Consequence |
|---|---|---|---|
| Tooling | Pure JavaScript modules tested with Node's test runner; browser checks through Playwright or a DevTools Protocol client. The PRD calls these commands "design targets". | One browser module, `app.js`. No JavaScript tests, no browser driver. | Every remaining story names a `node --test` or browser check that cannot be run yet. The test foundation (#8) has to come first. |
| Verification record | "See the README for the working baseline and verified checks." | The README said both that nothing had been recorded as run and that the suite and a Chrome run had passed. | The README "Evidence" section now holds the runs observed in the preparation pass. The earlier claims (the suite on Ubuntu 24.04 in WSL2, a Chrome 157 run with external requests blocked) are kept in the README under "Baseline verification (claimed in the original commit, not reproduced)" and **need verification**; see section 9. |
| Editor details | The screen inspector includes "connected actions". "A pointer shortcut can connect directly on the canvas." | The inspector has label, kind, X, Y, four Move buttons, the start control and Remove (`index.html` 89 to 122). Transitions are shown in one flow-wide list and created with the source and target selects (`index.html` 130 to 143). The canvas `pointerdown` handler only selects and drags (`app.js` 914 to 932). | A gap that no open issue covers. The PRD words the pointer shortcut as optional. Listed in the epic (#1) as an owner decision. |
| Comparing revisions | Product outcome item 4: "compare the result with the prior revision". | No history view exists yet. | The history and restore issue (#4) plans a read-only preview and puts a visual diff out of scope. Whether the preview is enough is listed in the epic (#1) as an owner decision. |
| Flows per project | One flow per project. | Many flows per data directory, listed in the navigator. Recorded as a baseline decision in the PRD. | A10 import relies on this: an import creates a second flow. |
| Revision `POST` | One route takes `save` or `restore`. | Only `save`. The handler requires the `graph` key for every request. | Restore needs a second key set and a second request hash. The existing test `test_unsupported_operation_and_unknown_keys` sends `op: "restore"` together with a `graph` key and expects `422 invalid_request`; it keeps passing unchanged if the restore contract has no `graph` key (the contract proposed in the history and restore issue, #4), and it needs a change only if restore were to accept `graph`. |
| Create request hash | "An exact duplicate request returns the original result." | Matches. The request hash covers `title` or `graph`, never both, so an import and an empty create with the same title are different requests. | None for the baseline; relevant to import idempotency. |
| No-op save | Not stated. | Always appends a revision; the editor disables **Save** when nothing changed. Recorded as a baseline decision. | Restore of the current head would also append a revision. |
| Error codes | 400, 404, 413, 422, 409, 503. | Also 403 (`bad_host`, `bad_origin`) and 405. Recorded as a baseline decision. | None. |
| Pagination | "List and history reads may paginate." | No pagination. | Acceptable at the stated limits. |
| Fixtures | Routing fixture, blocked fixture, route oracle grids, 75-screen load fixture. | Only the eight-screen scenario fixture exists, twice: `demoGraph` in `app.js` (180 to 215) and `tests/support.py`. They match the PRD table. | The other fixtures are part of the routing and gate work. |

## 8. Constraints that shape the remaining work

These are facts of the current code that a new feature has to work with or change deliberately.

1. **Static files are served from one flat folder.** The route is `/static/<name>` with no subfolders, and only `.html`, `.css`, `.js`, `.svg` and `.json` are served (`server.py` 17 to 23, 37, 242 to 257). New browser modules either sit directly in `flow_mapper/static/` or the route and its tests are extended.
2. **The client is already an ES module.** `index.html` loads `app.js` with `type="module"`, so it can `import` sibling modules without a build step. Read against the Content-Security-Policy (`script-src 'self'`, no `worker-src`), a module worker loaded from `/static/` is allowed and a worker from a `blob:` URL or an inline script is not. This was not run; the routing work has to confirm it in a browser.
3. **The static lint test reads every file directly inside `static/`.** It forbids any `http://` or `https://` URL except `http://www.w3.org/2000/svg`, and the strings `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write` and `eval(`. An SVG exporter has to build its output without those and without the XLink namespace URL.
4. **`app.js` is one 985-line module with module-level state** (`state`, `remove`, `drag`). Routing, analysis, history and export all need the draft and the render cycle. Pure logic for them should live in separate modules that take plain data, so it can be tested under Node without a DOM.
5. **Node can test those modules as they are.** With Node 22.23, `node --test "tests/js/*.test.mjs"` imports a plain `.js` file that uses `export` without a `package.json` (checked with a throwaway module during the preparation pass). Passing a folder instead of a glob does not work. `python -m unittest discover -s tests` ignores a `tests/js/` folder.
6. **The request hash defines idempotency.** `_hash` is called with `{"baseVersion", "graph", "op": "save"}` for a save and `{"op": "create", "flowId", "graph", "title"}` for a create. A restore needs its own canonical document.
7. **The fault seam is `Store(fault_hook=...)`**, called with `"after_revision_insert"` between the revision insert and the head update. A restore that reuses the same insert path gets the same seam.
8. **`ThreadingHTTPServer` with a fresh SQLite connection per operation.** Writers are serialized by `BEGIN IMMEDIATE` with a one-second busy timeout.
9. **Windows detail.** `allow_reuse_address` is off on Windows (`server.py` 48 to 52). A test that restarts a server on the same port should use port 0 or wait for the old process to exit.

## 9. What was run during the preparation pass

Host: Windows 11, Python 3.13.14, Node 22.23.4, commit `7672e0c`, 2026-11-22.

| Check | Observed result |
|---|---|
| `python -m unittest discover -s tests -v` | `Ran 73 tests in 16.198s`, `OK` |
| `python -m flow_mapper --data-dir <temp> --port 18765` | Printed `Serving on http://127.0.0.1:18765/`; `GET /api/v1/health` returned `{"status": "ok", "schemaVersion": 1, "storage": "ready"}` |
| Browser run in the Claude desktop browser pane (Chromium 156) against that server | **Create demo flow** opened "Demo: checkout journey", revision 1, eight screens, seven transitions. **Move right** moved Shipping to 16, 4 and the status became "Unsaved changes". Arrow Down on the focused canvas screen moved it to 16, 5 and kept focus. Setting **X** to 27 was refused with "Cannot move: Shipping would overlap Order placed" and X went back to 16. **Remove screen** opened the dialog with **Cancel** focused; Escape kept all eight screens and announced "Removal cancelled"; **Remove** removed Shipping and its five transitions and moved focus to the next screen in the list. **Save** showed "Saved · revision 2". After stopping and restarting the server on the same data directory, the flow list showed revision 2 and reopening showed seven screens and two transitions. The request list held nine requests, all to `127.0.0.1:18765`. No console errors. |

Not run: add screen, label editing and add transition in a browser; the two-tab conflict flow in a browser; any run with external requests blocked; Linux; installed Chrome.

**Needs verification** (claims in the README that predate this pass and have no recorded run): the unit suite on Ubuntu 24.04 in WSL2 with Python 3.12, and a Windows Chrome 157 run of the workflow with external browser requests blocked. Neither was reproduced. The second one must not be read as proof for A11; the release gate issue (#6) has to produce and record that run.
