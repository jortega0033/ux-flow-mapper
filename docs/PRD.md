# Offline UX Flow Mapper

Product requirements and technical specification · Proposed v1

## Product requirements

### Problem and user

A frontend developer reviewing an app needs to see how screens connect, where a user gets stuck, and which routes change when a design is simplified. Screenshots show the appearance of individual screens. This tool captures the user’s path through them and makes gaps visible before anyone changes the app.

The primary user is one developer mapping a fictional flow on a local desktop. Named scenarios model conditions such as online and offline. They share a flow and select which actions are available.

### Product outcome

A complete v1 supports this sequence:

1. Create a flow and add screens, actions, and explicit exits.
2. Move screens and see the connected routes reroute around them.
3. Check each scenario for dead ends, unreachable screens, and sections with no route to an exit.
4. Fix a problem, save a revision, and compare the result with the prior revision.
5. Reopen the project after restarting the server. Export a shareable SVG or a portable JSON file locally.

The first usable increment is a keyboard-accessible editor that saves and reopens one fictional flow. Routing, analysis, revision recovery, and export make up the rest of the epic.

### Scope and defaults

| In v1 | Later |
|---|---|
| One local author and one flow per project. A single start screen, named scenarios, labeled directed transitions, and explicit success or alternate exits. | Concurrent multi-author collaboration, accounts, and shared hosting. |
| A fixed-grid SVG editor with pan, zoom, a list of screens, and a text inspector. | Freehand drawing, custom shapes, arbitrary node sizes, and image or live-page imports. |
| Deterministic routing, analysis, and versioned saves. JSON round-trip and standalone SVG export. | Automatic capture of an app’s behavior, cross-project graphs, and integrations with design or issue tools. |

Use made-up examples. Ship an empty project list by default, with an explicit way to create a synthetic demo. Editor labels and keyboard shortcuts remain discoverable in Chrome. Project data stays within the chosen local data directory.

## Epic · Verify a user journey before implementing it

A frontend developer can map a proposed user journey, find structural problems under multiple scenarios, revise the design, and retain an inspectable record of what changed. Each story contributes a separately demonstrable part of that outcome.

| Story | As a user, I want… | Acceptance |
|---|---|---|
| UFM-01 · Create and reopen | …to create and reopen a flow so I can continue a review later. | A1, A2 |
| UFM-02 · Edit the journey | …to add, label, move, connect, and remove screens and actions so the map reflects the product. | A2, A3 |
| UFM-03 · Follow clear routes | …to move a screen while keeping the diagram readable. | A4, A5 |
| UFM-04 · Check scenarios | …to check available actions and exits under an explicit scenario so I can find where users get stuck. | A6, A7 |
| UFM-05 · Recover a revision | …to inspect a previous version and save it as a new current version so I can undo a larger design decision. | A8, A9 |
| UFM-06 · Share the output | …to export a visual copy and a portable editable copy of a saved flow. | A10, A11 |

### Product acceptance criteria

| ID | Given and action | Expected evidence |
|---|---|---|
| A1 | From empty storage, name a flow, save the first screens and restart the server with the same data path. | Exactly one flow is listed. Reopening shows the same saved graph, positions, and revision number. |
| A2 | Using the keyboard and the screen list, add a screen, edit its label, connect it to an exit, and move it one grid unit. | Each action succeeds with visible focus and an announced result. Screen list, inspector and SVG reflect the same state. |
| A3 | Remove a screen with outgoing and incoming transitions. Cancel once, then confirm. Also try moving a screen onto another screen. | Cancel preserves the draft. Confirm removes the screen and its incident transitions in one draft edit and clears the start marker if it pointed to that screen. An overlapping move restores the position from before that move or drag and explains the constraint. |
| A4 | Open the routing fixture. Move an unrelated screen into the path of an existing connector and drop it in a valid position. | The connector reroutes after drop. The resulting orthogonal segments avoid the obstacle. Repeating the same inputs yields the same polyline. |
| A5 | Run the router against the blocked-grid fixture. Then change the blockage to permit a path. | The first result reports the edge as unroutable and shows a text status without displaying a misleading route. The second returns a valid route and clears the status. |
| A6 | Run the example graph under Online and Offline. | The unreachable, dead-end, and no-exit result sets equal the fixture expectations below. Each result can select the affected screen. |
| A7 | Add the two repair transitions, first for the Online cycle and then for the Offline recovery screen. | Each repair clears the relevant finding in its scenario. The unused screen remains unreachable in both. |
| A8 | Open revision 2 in two tabs. Save an edit from tab A, then try saving a different edit from tab B. Re-send A’s original request. | Tab B sees the current version and keeps its unsaved draft. Exactly one revision exists for A’s request. A replay returns A’s original saved version even if a newer version exists. |
| A9 | Inspect revision 1 in a read-only preview, then restore it on the current version. Inject a write failure in a separate test. | The preview leaves the current draft intact. Restore appends a new revision with revision 1’s exact graph and preserves the history. A failed commit leaves the previous version, project-list title and saved revision, and revision count intact. |
| A10 | Export a saved scenario as SVG and the full flow as JSON. Import that JSON twice using the same create request. | SVG opens as a local file with the same layout and selected scenario. The import creates exactly one separate flow. Graph, scenario IDs and positions match the exported graph within that copy. |
| A11 | Run A1 through A10 against fictional fixtures. Block external requests in Chrome while leaving loopback available. | The launch, edit, save, issue inspection, and export paths complete. A request log records zero external requests from the app. A control request confirms the test’s network block. |

## Technical specification

### Stack and runtime

- Python 3.12 standard library for the local HTTP server, SQLite persistence, and Python tests. Use a CLI with an explicit data directory and a loopback port.
- Chrome with HTML, CSS, native JavaScript modules, and SVG. Place heading, navigation, form controls, and the accessible screen and transition lists in standard HTML.
- Pure JavaScript modules for graph analysis and routing. Run their tests with Node’s built-in test runner. Use the installed Chrome and the workspace’s Playwright integration for browser checks. Confirm the runner and browser executable in preflight. For an image without Playwright, use Node 22’s built-in WebSocket client with Chrome DevTools Protocol on a disposable loopback-only debugging profile. Use it to capture request evidence and drive test inputs.
- Serve a single origin at `127.0.0.1`. Keep runtime assets in the project. Proposed commands use `python3 -m flow_mapper --data-dir <path> --port <port>`, `python3 -m unittest discover -s tests`, and `node --test <graph-test-paths>`. These are design targets for the implementation.

### Editor behavior

- The project list shows saved titles, saved revision numbers, and a create action. The editor opens the saved revision and maintains a single working draft in memory.
- A toolbar gives Edit, Analyze, History, and Export predictable keyboard targets. The screen list provides equivalent operations for users who skip the canvas. A screen’s inspector includes label, outcome type, grid position, connected actions, and start-screen control. Converting a screen to an exit requires clearing outgoing transitions and moving its start marker first.
- Select a source and target through controls that can be operated by keyboard. A pointer shortcut can connect directly on the canvas. Both inputs call the same edit action and validation.
- A move preview can show simple connector guides. The inspector has four named Move buttons plus numeric X and Y controls. The toolbar has named Pan and Zoom controls. The verified routes update after drop or a keyboard move. Apply results only for the current draft generation and active scenario.
- Use a polite live region for editing, saving, and analysis status. A native removal dialog focuses Cancel first. Escape cancels. On dismissal, return focus to the initiating control, the next remaining screen, or Add Screen when the list is empty.
- Use one in-flight save per open editor. Preserve its frozen payload and request ID until its outcome is known. An unanswered request must be replayed before submitting another. Keep any subsequent edits in the local draft. If the replay reports a newer head than the committed version, enter the conflict flow and preserve that draft. Otherwise update the saved base and leave later edits marked unsaved.
- Show save and conflict states in text. A conflict offers reload after explicit discard or download of the unsaved draft as importable JSON. Restore becomes available after saving or explicitly discarding local edits. A browser leave prompt can guard an unsaved draft.

### Graph contract

Use a versioned JSON envelope. Coordinates are integer grid units. IDs are lower-case UUIDs scoped to their flow. Labels are plain text. Graph data stays independent of camera pan and zoom.

| Field | Validity and meaning |
|---|---|
| `schemaVersion` | An integer, initially `1`. Unsupported versions produce a clear import error. |
| `title` | Trimmed non-empty text, 1–120 characters. |
| `startId` | Screen ID or null. A blank draft may have no start. Analysis then prompts for one. A start can point to any non-exit screen. |
| `scenarios[]` | 1–8 distinct IDs and labels of 1–60 characters, unique after Unicode normalization and case folding on the server. New flows begin with a default scenario. |
| `screens[]` | Up to 80 entries with ID, plain-text label of 1–80 characters, kind, `x` and `y`. Kind is `screen`, `success_exit`, or `alternate_exit`. Screen footprints are fixed at 6 by 3 grid units within a 100 by 70 grid. Footprint interiors may not overlap. Touching boundaries are allowed and may block a connector port. |
| `transitions[]` | Up to 160 directed entries with ID, source, target, plain-text label of 1–120 characters, and `enabledIn`. Endpoints must exist. An exit has no outgoing links. A self-transition on a non-exit is valid. Allow one arrow per ordered endpoint pair in v1. |
| `enabledIn` | Null enables the transition in every scenario. A non-empty list enables it in exactly the listed scenarios. Lists contain unique known IDs. |

Trim labels, normalize them to Unicode NFC, and reject non-printing control characters. Count Unicode code points for label limits in the browser and service. Persist normalized graph arrays sorted by stable ID, with context-independent field order. Keep layout ordering in coordinates and render z-order deterministic. Removing a scenario requires review of any affected transitions. Remove that scenario from a multi-scenario transition and remove a transition when its last selected scenario is removed. The final remaining scenario cannot be removed. The deletion preview reports specific affected edges.

### Scenario analysis

For each selected scenario, first build adjacency lists using only enabled transitions. Walk forward from the start, then walk backward from all explicit exits. Use visited sets so cycles terminate. Return findings sorted by code and screen ID for deterministic tests.

| Finding | Rule |
|---|---|
| Unreachable | The screen is outside the forward visited set. |
| Dead end | The screen is reachable, is neither kind of exit, and has zero enabled outgoing transitions. |
| No route to exit | The screen is reachable, has an enabled outgoing transition, and is absent from the reverse visited set. This covers a trapped cycle and an upstream path with no eventual exit. |
| Missing start | The draft lacks a valid start. Prompt the user to select one before showing reachability results. |

Structural checks use connectivity rather than the geometry of a drawn route. An unroutable connector is a layout finding. It remains in the logical graph.

### Connector routing

1. Use one port per side at its rounded-down midpoint, and a stub connecting it to the adjacent exterior grid vertex. Disqualify ports whose exterior vertex or stub is blocked or outside the grid. Give ports a fixed order.
2. Treat closed screen rectangles as obstacles. Only a connector’s own endpoint stubs may touch their designated bounds. Validate proposed segments against the obstacle rectangles and the grid boundary.
3. Run one multi-source A* search from all eligible source ports to a virtual destination connected to all eligible target ports. State is grid vertex and incoming direction. For a self-transition, also keep the originating port in state so the destination requires a distinct port. Each grid step costs 10 and a direction change adds 3, including endpoint stubs. Use the minimum Manhattan distance to an eligible target exterior vertex times 10 as the heuristic. Resolve ties by port order and a stable coordinate and direction order.
4. Compress adjacent collinear segments. Connector crossings are permitted. On the default grid, cap finalized states at 35,000 for a normal edge and 120,000 for a self-transition. Exhausting all eligible states yields `blocked`. Hitting a configured cap first yields `search_budget`. Ignore obsolete priority queue entries without counting them as finalized states.
5. Run graph-wide computation in a web worker after committed layout or scenario changes. The editor keeps controls responsive while work runs. A screen drag can show a lightweight preview. Use a draft generation counter to ignore late worker results.

A routing request returns either a verified polyline or a reason such as `blocked` or `search_budget`. The interface reports a descriptive row for each unavailable route. Verify the result against an independent segment-intersection test before drawing or exporting it.

### Storage and HTTP API

Use an SQLite database within the explicit data directory. Enable foreign keys and version schema migrations. Use one write transaction for flow state and each revision. List and history reads may paginate without changing the document.

| Table | Columns and invariants |
|---|---|
| `flow` | ID primary key, current revision number, current title, created and updated timestamps. A visible record has an existing current snapshot. |
| `revision` | Flow ID, increasing version, normalized graph JSON, request ID, canonical request hash, UTC timestamp, optional source version for a restore. Primary key is flow ID and version. Request ID is unique per flow. |

| Route | Contract |
|---|---|
| `GET /api/v1/health` | Returns a small readiness result after storage opens. |
| `GET /api/v1/flows` | Returns flow IDs, titles, current revisions, and update times. |
| `POST /api/v1/flows` | Client-created flow ID and stable request ID. Creates an empty or imported graph as version 1. An exact duplicate request returns the original result. Reusing the flow ID with a different create request conflicts. |
| `GET /api/v1/flows/{id}` | Returns the current graph and revision. |
| `POST /api/v1/flows/{id}/revisions` | Accepts base version and request ID with one operation. Save takes a validated full graph. Restore takes the version to restore and reads that immutable graph on the server. Returns the committed version or a conflict with the latest revision. |
| `GET /api/v1/flows/{id}/revisions` | Returns revision numbers, timestamps, and restore provenance. |
| `GET /api/v1/flows/{id}/revisions/{version}` | Returns the immutable graph for that revision. |

Check an existing request ID and canonical hash before the base-version check. A changed payload under the same key conflicts. A new command with a stale base version conflicts and leaves the head untouched. On a successful save, increment the version and insert the snapshot and new head in one `BEGIN IMMEDIATE` transaction. A transient database lock returns a retryable error. Keep the same request ID when retrying an unchanged command after a lost response. A response includes both the command’s committed version and the current head.

Import parses JSON under a 512 KiB limit and validates schema, references, geometry, and limits before writing. A valid JSON import creates a new project. The selected scenario SVG renderer uses the same route function as the on-screen diagram, computed for the exported saved revision and scenario. Show the saved revision number before export, including when the editor has unsaved changes. SVG renders only enabled transitions and escapes all text and attributes. Include a title and description naming the flow, revision, and scenario. If any enabled edge cannot be routed, refuse SVG export, list the affected edges in text, and offer JSON.

Use 400 for malformed JSON, 404 for missing records, 413 for oversized requests, 422 for invalid graph data, 409 for command or version conflicts, and 503 for a transient database lock. Errors include a stable code and a safe display message.

Bind the service to loopback. Validate the host on every request and require the same-origin Origin header on writes. Serve static files and API routes from the same origin. Reject external assets and scripts. Render labels as text. Put local database files outside source control when the project is created.

### Verification fixtures

#### Scenario fixture with exact expected results

Use one start screen `A`, normal screens `B`, `D`, `E`, `F`, `G`, success exit `C`, and alternate exit `H`. A test fixture maps aliases to stable UUIDs. In A through H order, place the screens at (2,4), (15,4), (31,4), (15,14), (31,14), (45,14), (45,26), and (31,26). Use the same graph and locations in the UI and API fixtures.

| Enabled in | Edges |
|---|---|
| Both | A → B, B → H |
| Online | B → C, B → E, E → F, F → E |
| Offline | B → D |

| Scenario | Unreachable | Dead end | No route to exit |
|---|---|---|---|
| Online | D, G | none | E, F |
| Offline | C, E, F, G | D | none |

Add `F → C` in Online and `D → H` in Offline. The no-exit finding and dead-end finding respectively clear. The unreachable sets stay the same.

#### Routing and persistence fixtures

- **Editor routing fixture.** Place source at (2,4), target at (20,4), and an unrelated screen at (11,10), all with the standard 6 by 3 footprint. Side ports use the rounded-down midpoint. With an edge from source to target, the direct segment is (8,5) to (20,5). Move the unrelated screen to (11,4). Verify the old segment would intersect its rectangle and the actual new route avoids it with an independently checked path cost.
- **Editor blocked fixture.** Place source at (0,0), target at (20,4), and blockers at (7,0) and (0,4). The top and left exterior vertices are outside the canvas. Both remaining source ports are blocked. Verify `blocked`, then move the first blocker to (11,0) and verify a valid path.
- **Route oracle.** Use small reference grids with a unique straight path, a symmetric detour, a fully blocked partition, and a self-transition. Compare path cost to an independent exhaustive search in small grids and verify segments avoid obstacles. Run repeated-input cases and verify identical polyline points.
- **Mid-save failure.** Fail after inserting a revision and before updating the flow head. Verify from another connection that neither change committed. Retry after clearing the fault and verify one new version.
- **Two-tab conformance.** Open the same version in two browser contexts. Lose the first tab’s success response, commit a newer valid version, then replay the first request. Verify no duplicate, a preserved stale draft, and correct command version and current head in the response.
- **Load target.** Use a recorded fixture with 75 screens and up to 150 non-duplicate edges. Record route time, longest worker response, and any budget misses at the agreed host profile. Verify a keyboard edit is processed while a previous worker request is pending, then prove a late route result cannot overwrite the newer state. Establish the numeric performance bar from the first measured offline run.

### Delivery milestones

| Milestone | Depends on | Exit gate |
|---|---|---|
| M1 · Durable editable flow | none | Create one synthetic flow, change it through the browser, restart, and reopen the same version. Prove A1–A3. |
| M2 · Readable routing | M1 | Orthogonal routes update and surface blocked edges. Prove A4–A5 with route oracle and browser evidence. |
| M3 · Scenario review | M1 | Reveal and fix exact fixture findings. Prove A6–A7 with independent graph tests and text findings in Chrome. |
| M4 · Revision recovery and handoff | M1–M3 | Prove stale conflict handling, rollback, replay, SVG and JSON round-trip, and one complete offline browser run. A8–A11. |

### Decisions and review boundaries

This specification proposes one author, a fixed-size grid, one arrow per ordered pair, and explicit manual saves. They keep the first delivery focused on diagnosing flows. Variable screen sizes, concurrent editing, and multiple connectors between the same pair are future scope. Failure of routing leaves the user’s graph editable and the analysis meaningful.

The local runtime and performance targets are design choices. Confirm the actual hosted Chrome and runtime versions before the first implementation pass. Run the fixtures and record direct observations. See the README for the working baseline and verified checks.

### Implementation status

| Item | Status |
|---|---|
| M1 · Durable editable flow (A1–A3) | Implemented in the baseline. Automated checks are in `tests/`; browser verification is recorded in the README only once it has been run. |
| M2 · Readable routing (A4–A5) | Remaining. The baseline draws straight connectors. |
| M3 · Scenario review (A6–A7) | Remaining. The baseline stores and preserves scenarios and `enabledIn` but does not display or analyze them. |
| M4 · Revision recovery and handoff (A8–A11) | Remaining. The baseline already implements the save, replay and conflict contract on the server and in the editor. History, restore, export and import are not built. |

Baseline decisions and ambiguities:

- **Several flows per data directory.** The spec says one flow per project, while the collection route and project list imply many. The baseline allows many flows in one data directory and lists them in the navigator. Tightening this later is a policy change, not a schema change.
- **No pan or zoom in M1.** The toolbar Pan and Zoom controls are deferred to the routing work (UFM-03). The baseline canvas scrolls inside its pane.
- **No-op saves.** A save always appends a revision, even when the graph is unchanged. The editor disables Save when there is nothing to save.
- **Create body.** `POST /api/v1/flows` accepts either `title` (empty flow) or a full `graph` (used by the opt-in demo and, later, by import).
- **Extra error codes.** Host and Origin rejections return 403 (`bad_host`, `bad_origin`), which the status list above does not name.
- **Start rules.** A start screen must be a non-exit screen. Converting the start screen to an exit is refused until the start is moved.
