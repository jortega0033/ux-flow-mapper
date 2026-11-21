// UX Flow Mapper browser client (M1 baseline). No dependencies; all user text goes through textContent.

const CELL = 10;
const MAX_X = 94;
const MAX_Y = 67;
const SCREEN_W = 6;
const SCREEN_H = 3;
const MAX_SCREENS = 80;
const MAX_TRANSITIONS = 160;
const SVG_NS = 'http://www.w3.org/2000/svg';
const KINDS = ['screen', 'success_exit', 'alternate_exit'];
const KIND_NAMES = { screen: 'Screen', success_exit: 'Success exit', alternate_exit: 'Alternate exit' };

const $ = (id) => document.getElementById(id);

const state = {
  flows: [],
  flowId: null,
  base: null, // { revision, graph } as last saved on the server
  draft: null, // working graph
  selectedId: null,
  pending: null, // frozen save request { flowId, requestId, baseVersion, graph }
  saving: false,
  failMsg: '',
  conflict: null, // { latest }
  loadSeq: 0,
  creating: false,
  createReq: null, // { key, id, requestId, title }
  demoReq: null, // { id, requestId, graph }
  preview: null, // { id, x, y } while dragging
};

const remove = { target: null, initiator: null, confirmed: false };
let drag = null;

// ---------- helpers ----------

function uuid() {
  if (globalThis.crypto && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = Array.from(b, (v) => v.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

const clone = (v) => JSON.parse(JSON.stringify(v));

function mk(tag, attrs, text) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
  if (text !== undefined) el.textContent = text;
  return el;
}

function svg(tag, attrs, text) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, String(v));
  if (text !== undefined) el.textContent = text;
  return el;
}

function setVal(el, value) {
  const v = String(value);
  if (el.value !== v) el.value = v;
}

// Rebuild a list while keeping keyboard focus on the item with the same key.
function rebuild(container, attr, build) {
  const active = document.activeElement;
  const key = active && container.contains(active) ? active.getAttribute(attr) : null;
  container.replaceChildren();
  build();
  if (key !== null) {
    const node = container.querySelector(`[${attr}="${CSS.escape(key)}"]`);
    if (node) node.focus();
  }
}

function canon(g) {
  const byId = (a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
  const t = (s) => String(s).trim().normalize('NFC');
  return JSON.stringify({
    schemaVersion: g.schemaVersion,
    title: t(g.title),
    startId: g.startId,
    scenarios: [...g.scenarios].sort(byId).map((s) => ({ id: s.id, label: t(s.label) })),
    screens: [...g.screens].sort(byId).map((s) => ({ id: s.id, label: t(s.label), kind: s.kind, x: s.x, y: s.y })),
    transitions: [...g.transitions].sort(byId).map((x) => ({
      id: x.id,
      source: x.source,
      target: x.target,
      label: t(x.label),
      enabledIn: x.enabledIn == null ? null : [...x.enabledIn].sort(),
    })),
  });
}

const isDirty = () => !!(state.draft && state.base && canon(state.draft) !== canon(state.base.graph));
const hasUnsaved = () => isDirty() || !!state.pending;
const screenById = (id) => (state.draft ? state.draft.screens.find((s) => s.id === id) : undefined);
const selectedScreen = () => (state.selectedId ? screenById(state.selectedId) : undefined);

function clearErrors() {
  $('errors').replaceChildren();
}

function showError(messages) {
  const list = Array.isArray(messages) ? messages : [messages];
  const box = $('errors');
  box.replaceChildren();
  for (const m of list) box.append(mk('p', {}, String(m)));
}

function announce(msg) {
  $('live').textContent = msg;
}

function fail(msg) {
  showError(msg);
  announce(msg);
}

// ---------- API ----------

class ApiFailure extends Error {
  constructor({ network = false, status = 0, code = '', message, details }) {
    super(message);
    this.network = network;
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function api(method, path, body) {
  let res;
  try {
    const init = { method, cache: 'no-store' };
    if (body !== undefined) {
      init.headers = { 'Content-Type': 'application/json' };
      init.body = JSON.stringify(body);
    }
    res = await fetch(`/api/v1${path}`, init);
  } catch (_err) {
    throw new ApiFailure({ network: true, message: 'Network error: could not reach the server' });
  }
  let data = null;
  try {
    data = await res.json();
  } catch (_err) {
    data = null;
  }
  if (!res.ok) {
    const e = data && data.error ? data.error : {};
    throw new ApiFailure({
      status: res.status,
      code: e.code || '',
      message: e.message || `Request failed (HTTP ${res.status})`,
      details: e.details,
    });
  }
  if (data === null) {
    throw new ApiFailure({ status: res.status, message: 'The server sent an unreadable response' });
  }
  return data;
}

function errorMessages(e) {
  if (e && e.code === 'invalid_graph' && Array.isArray(e.details) && e.details.length) {
    return e.details.map((d) => (d && d.path ? `${d.path}: ${d.message}` : String(d && d.message)));
  }
  return [e && e.message ? e.message : 'Unexpected error'];
}

const isTransient = (e) => e.network || e.status >= 500;

// ---------- demo fixture ----------

function demoGraph() {
  const sid = (n) => `00000000-0000-4000-8000-0000000000a${n}`;
  const tid = (n) => `00000000-0000-4000-8000-0000000000b${n}`;
  const online = '00000000-0000-4000-8000-0000000000c1';
  const offline = '00000000-0000-4000-8000-0000000000c2';
  const screens = [
    ['Cart', 'screen', 2, 4],
    ['Shipping', 'screen', 15, 4],
    ['Order placed', 'success_exit', 31, 4],
    ['Offline notice', 'screen', 15, 14],
    ['Payment retry', 'screen', 31, 14],
    ['Card details', 'screen', 45, 14],
    ['Unused tips', 'screen', 45, 26],
    ['Cancelled', 'alternate_exit', 31, 26],
  ].map(([label, kind, x, y], i) => ({ id: sid(i + 1), label, kind, x, y }));
  const edges = [
    [1, 1, 2, 'Continue', null],
    [2, 2, 8, 'Cancel', null],
    [3, 2, 3, 'Pay', [online]],
    [4, 2, 5, 'Retry payment', [online]],
    [5, 5, 6, 'Edit card', [online]],
    [6, 6, 5, 'Re-enter', [online]],
    [7, 2, 4, 'Work offline', [offline]],
  ].map(([n, s, t, label, enabledIn]) => ({ id: tid(n), source: sid(s), target: sid(t), label, enabledIn }));
  return {
    schemaVersion: 1,
    title: 'Demo: checkout journey',
    startId: sid(1),
    scenarios: [
      { id: online, label: 'Online' },
      { id: offline, label: 'Offline' },
    ],
    screens,
    transitions: edges,
  };
}

// ---------- rendering ----------

function renderAll() {
  renderFlows();
  renderStatus();
  renderEditor();
}

function renderFlows() {
  $('flow-empty').hidden = state.flows.length > 0;
  rebuild($('flow-list'), 'data-id', () => {
    for (const f of state.flows) {
      const li = mk('li');
      const btn = mk('button', { type: 'button', class: 'list-btn', 'data-id': f.id }, `${f.title} · revision ${f.revision}`);
      if (f.id === state.flowId) btn.setAttribute('aria-current', 'true');
      li.append(btn);
      $('flow-list').append(li);
    }
  });
}

function statusText() {
  if (!state.flowId) return '';
  if (state.conflict) {
    return `Conflict: revision ${state.conflict.latest} exists, your draft is based on revision ${state.base.revision}`;
  }
  if (state.saving) return 'Saving…';
  if (state.pending && state.failMsg) return `Save failed: ${state.failMsg} (retry with Save)`;
  if (isDirty()) return 'Unsaved changes';
  return `Saved · revision ${state.base.revision}`;
}

function renderStatus() {
  $('save-state').textContent = statusText();
  $('save-btn').disabled = !state.flowId || state.saving || !!state.conflict || !(isDirty() || state.pending);
  $('conflict-bar').hidden = !state.conflict;
  $('add-flow-btn').disabled = state.creating;
  $('demo-btn').disabled = state.creating;
}

function renderEditor() {
  const has = !!(state.flowId && state.draft);
  $('editor').hidden = !has;
  $('placeholder').hidden = has;
  if (!has) return;
  if (state.selectedId && !screenById(state.selectedId)) state.selectedId = null;
  setVal($('flow-title'), state.draft.title);
  renderScreenList();
  renderInspector();
  renderTransitionForm();
  renderTransitionList();
  renderCanvas();
}

function renderScreenList() {
  rebuild($('screen-list'), 'data-id', () => {
    for (const s of state.draft.screens) {
      const li = mk('li');
      const btn = mk('button', { type: 'button', class: 'list-btn', 'data-id': s.id }, `${s.label} (${s.x}, ${s.y})`);
      if (s.id === state.selectedId) btn.setAttribute('aria-current', 'true');
      li.append(btn);
      $('screen-list').append(li);
    }
  });
}

function renderInspector() {
  const s = selectedScreen();
  $('no-selection').hidden = !!s;
  $('inspector').hidden = !s;
  if (!s) return;
  setVal($('screen-label'), s.label);
  setVal($('screen-kind'), s.kind);
  setVal($('screen-x'), s.x);
  setVal($('screen-y'), s.y);
  $('screen-start').checked = state.draft.startId === s.id;
}

function syncSelect(sel, screens, fallbackIndex) {
  const sig = screens.map((s) => `${s.id}\u0000${s.label}`).join('\u0001');
  if (sel.dataset.sig === sig) return;
  const prev = sel.value;
  sel.replaceChildren();
  for (const s of screens) sel.append(mk('option', { value: s.id }, s.label));
  if (screens.some((s) => s.id === prev)) sel.value = prev;
  else if (screens.length) sel.value = screens[Math.min(fallbackIndex, screens.length - 1)].id;
  sel.dataset.sig = sig;
}

function renderTransitionForm() {
  syncSelect($('transition-source'), state.draft.screens, 0);
  syncSelect($('transition-target'), state.draft.screens, 1);
}

function renderTransitionList() {
  const name = (id) => {
    const s = screenById(id);
    return s ? s.label : id;
  };
  rebuild($('transition-list'), 'data-id', () => {
    for (const t of state.draft.transitions) {
      const src = name(t.source);
      const tgt = name(t.target);
      const li = mk('li', { class: 'transition-item' });
      li.append(mk('span', {}, `${src} → ${tgt}: ${t.label}`));
      li.append(mk('button', { type: 'button', 'data-id': t.id, 'aria-label': `Delete transition ${src} to ${tgt}` }, 'Delete'));
      $('transition-list').append(li);
    }
  });
}

function borderPoint(cx, cy, dx, dy) {
  const tx = dx !== 0 ? (SCREEN_W * CELL / 2) / Math.abs(dx) : Infinity;
  const ty = dy !== 0 ? (SCREEN_H * CELL / 2) / Math.abs(dy) : Infinity;
  const t = Math.min(tx, ty);
  return [cx + dx * t, cy + dy * t];
}

function renderCanvas() {
  const g = state.draft;
  const pos = new Map();
  for (const s of g.screens) {
    const p = state.preview && state.preview.id === s.id ? state.preview : s;
    pos.set(s.id, { x: p.x, y: p.y });
  }
  const pairs = new Set(g.transitions.map((t) => `${t.source}>${t.target}`));
  const edges = $('edges');
  edges.replaceChildren();
  const hw = (SCREEN_W * CELL) / 2;
  const hh = (SCREEN_H * CELL) / 2;

  for (const t of g.transitions) {
    const a = pos.get(t.source);
    const b = pos.get(t.target);
    if (!a || !b) continue;
    const ax = a.x * CELL + hw;
    const ay = a.y * CELL + hh;
    const bx = b.x * CELL + hw;
    const by = b.y * CELL + hh;
    const group = svg('g', {
      class: 'edge',
      'data-transition-id': t.id,
      role: 'img',
      'aria-label': `${screenById(t.source)?.label ?? ''} → ${screenById(t.target)?.label ?? ''}: ${t.label}`,
    });
    let lx;
    let ly;
    if (t.source === t.target) {
      const dir = a.x >= 88 ? -1 : 1;
      const sx = ax + dir * hw;
      group.append(
        svg('path', {
          d: `M ${sx} ${ay - 8} C ${sx + dir * 36} ${ay - 26}, ${sx + dir * 36} ${ay + 26}, ${sx} ${ay + 8}`,
          'marker-end': 'url(#arrow)',
        }),
      );
      lx = sx + dir * 22;
      ly = ay - 24;
    } else {
      const dx = bx - ax;
      const dy = by - ay;
      const len = Math.hypot(dx, dy) || 1;
      let ox = 0;
      let oy = 0;
      if (pairs.has(`${t.target}>${t.source}`)) {
        ox = (-dy / len) * 7;
        oy = (dx / len) * 7;
      }
      const [x1, y1] = borderPoint(ax + ox, ay + oy, dx, dy);
      const [x2, y2] = borderPoint(bx + ox, by + oy, -dx, -dy);
      group.append(svg('line', { x1, y1, x2, y2, 'marker-end': 'url(#arrow)' }));
      lx = (x1 + x2) / 2;
      ly = (y1 + y2) / 2 - 5;
    }
    group.append(svg('text', { class: 'edge-label', x: lx, y: ly, 'text-anchor': 'middle' }, t.label));
    edges.append(group);
  }

  rebuild($('nodes'), 'data-screen-id', () => {
    for (const s of g.screens) {
      const p = pos.get(s.id);
      const isStart = g.startId === s.id;
      const kind = KINDS.includes(s.kind) ? s.kind : 'screen';
      const cls = ['screen', `kind-${kind.replace(/_/g, '-')}`];
      if (s.id === state.selectedId) cls.push('selected');
      const node = svg('g', {
        class: cls.join(' '),
        role: 'button',
        tabindex: '0',
        'aria-label': `${s.label}, x ${s.x}, y ${s.y}, ${s.kind}${isStart ? ', start' : ''}`,
        'data-screen-id': s.id,
      });
      const px = p.x * CELL;
      const py = p.y * CELL;
      node.append(svg('rect', { class: 'box', x: px, y: py, width: SCREEN_W * CELL, height: SCREEN_H * CELL, rx: 4 }));
      const clip = svg('svg', { x: px, y: py, width: SCREEN_W * CELL, height: SCREEN_H * CELL });
      clip.append(svg('text', { class: 'screen-label', x: hw, y: 14 }, s.label));
      const sub = [isStart ? 'Start' : '', kind !== 'screen' ? KIND_NAMES[kind] : ''].filter(Boolean).join(' · ');
      if (sub) clip.append(svg('text', { class: 'screen-sub', x: hw, y: 25 }, sub));
      node.append(clip);
      $('nodes').append(node);
    }
  });
}

// ---------- draft edits ----------

function overlapOrBounds(id, nx, ny) {
  if (nx < 0 || nx > MAX_X || ny < 0 || ny > MAX_Y) return 'be outside the grid';
  for (const o of state.draft.screens) {
    if (o.id !== id && Math.abs(o.x - nx) < SCREEN_W && Math.abs(o.y - ny) < SCREEN_H) return `overlap ${o.label}`;
  }
  return null;
}

function moveScreen(id, nx, ny) {
  const s = screenById(id);
  if (!s) return false;
  if (nx === s.x && ny === s.y) {
    renderAll();
    return true;
  }
  const problem = overlapOrBounds(id, nx, ny);
  if (problem) {
    fail(`Cannot move: ${s.label} would ${problem}`);
    renderAll();
    return false;
  }
  s.x = nx;
  s.y = ny;
  clearErrors();
  announce(`Moved ${s.label} to x ${nx}, y ${ny}`);
  renderAll();
  return true;
}

function selectScreen(id) {
  state.selectedId = id;
  renderAll();
}

function addScreen() {
  if (!state.draft) return;
  if (state.draft.screens.length >= MAX_SCREENS) {
    fail(`Cannot add screen: a flow can have at most ${MAX_SCREENS} screens`);
    return;
  }
  let spot = null;
  for (let y = 0; y < 68 && !spot; y += 4) {
    for (let x = 0; x < 95; x += 8) {
      if (!overlapOrBounds(null, x, y)) {
        spot = { x, y };
        break;
      }
    }
  }
  if (!spot) {
    fail('Cannot add screen: no free position on the grid');
    return;
  }
  const s = { id: uuid(), label: 'New screen', kind: 'screen', x: spot.x, y: spot.y };
  state.draft.screens.push(s);
  state.selectedId = s.id;
  clearErrors();
  announce(`Added screen at x ${s.x}, y ${s.y}`);
  renderAll();
  $('screen-label').focus();
  $('screen-label').select();
}

function setKind(value) {
  const s = selectedScreen();
  if (!s || !KINDS.includes(value)) return;
  if (value !== 'screen') {
    if (state.draft.startId === s.id) {
      fail(`Cannot change kind: ${s.label} is the start screen`);
      renderAll();
      return;
    }
    if (state.draft.transitions.some((t) => t.source === s.id)) {
      fail(`Cannot change kind: ${s.label} has outgoing transitions`);
      renderAll();
      return;
    }
  }
  s.kind = value;
  clearErrors();
  announce(`${s.label} is now ${KIND_NAMES[value]}`);
  renderAll();
}

function setStart(checked) {
  const s = selectedScreen();
  if (!s) return;
  if (checked && s.kind !== 'screen') {
    fail(`Cannot set start: ${s.label} is an exit`);
    renderAll();
    return;
  }
  state.draft.startId = checked ? s.id : null;
  clearErrors();
  announce(checked ? `${s.label} is the start screen` : `${s.label} is no longer the start screen`);
  renderAll();
}

function addTransition() {
  const g = state.draft;
  const source = $('transition-source').value;
  const target = $('transition-target').value;
  const label = $('transition-label').value.trim();
  const src = screenById(source);
  const tgt = screenById(target);
  if (!src || !tgt) return fail('Choose a source and a target screen');
  if (src.kind !== 'screen') return fail(`Cannot add transition: ${src.label} is an exit and cannot be a source`);
  if (!label) return fail('Enter a transition label');
  if (g.transitions.some((t) => t.source === source && t.target === target)) {
    return fail(`${src.label} → ${tgt.label} already exists`);
  }
  if (g.transitions.length >= MAX_TRANSITIONS) {
    return fail(`Cannot add transition: a flow can have at most ${MAX_TRANSITIONS} transitions`);
  }
  g.transitions.push({ id: uuid(), source, target, label, enabledIn: null });
  clearErrors();
  announce(`Added transition ${src.label} → ${tgt.label}: ${label}`);
  $('transition-label').value = 'Continue';
  renderAll();
}

function deleteTransition(id) {
  const g = state.draft;
  const idx = g.transitions.findIndex((t) => t.id === id);
  if (idx < 0) return;
  const t = g.transitions[idx];
  const src = screenById(t.source)?.label ?? t.source;
  const tgt = screenById(t.target)?.label ?? t.target;
  g.transitions.splice(idx, 1);
  clearErrors();
  announce(`Deleted transition ${src} → ${tgt}`);
  renderAll();
  const buttons = $('transition-list').querySelectorAll('button');
  const next = buttons[Math.min(idx, buttons.length - 1)];
  (next || $('transition-label')).focus();
}

// ---------- remove dialog ----------

function openRemove(id, initiator) {
  const s = screenById(id);
  const dlg = $('remove-dialog');
  if (!s || dlg.open) return;
  const n = state.draft.transitions.filter((t) => t.source === id || t.target === id).length;
  let text = `Remove "${s.label}" and its ${n} connected transition${n === 1 ? '' : 's'}?`;
  if (state.draft.startId === id) text += ' It is the start screen, so the flow will have no start.';
  $('remove-desc').textContent = text;
  remove.target = id;
  remove.initiator = initiator;
  remove.confirmed = false;
  dlg.showModal();
  $('remove-cancel').focus();
}

function onRemoveClosed() {
  const id = remove.target;
  const init = remove.initiator;
  remove.target = null;
  if (!id) return;
  if (!remove.confirmed) {
    announce('Removal cancelled');
    const node =
      init && init.type === 'canvas'
        ? $('nodes').querySelector(`[data-screen-id="${CSS.escape(init.id)}"]`)
        : $('remove-screen-btn');
    if (node && !node.closest('[hidden]')) node.focus();
    return;
  }
  const g = state.draft;
  const idx = g.screens.findIndex((s) => s.id === id);
  if (idx < 0) return;
  const label = g.screens[idx].label;
  g.screens.splice(idx, 1);
  g.transitions = g.transitions.filter((t) => t.source !== id && t.target !== id);
  if (g.startId === id) g.startId = null;
  if (state.selectedId === id) state.selectedId = null;
  clearErrors();
  announce(`Removed ${label}`);
  renderAll();
  const next = g.screens[Math.min(idx, g.screens.length - 1)];
  const nextBtn = next ? $('screen-list').querySelector(`[data-id="${CSS.escape(next.id)}"]`) : null;
  (nextBtn || $('add-screen-btn')).focus();
}

// ---------- flows ----------

async function loadFlows(quiet) {
  try {
    const data = await api('GET', '/flows');
    state.flows = data.flows;
    renderFlows();
  } catch (e) {
    if (!quiet) showError(errorMessages(e));
  }
}

function parseHash() {
  const m = /^#flow=([0-9a-f-]{36})$/.exec(location.hash);
  return m ? m[1] : null;
}

function restoreHash() {
  const want = state.flowId ? `#flow=${state.flowId}` : '';
  if (location.hash !== want) history.replaceState(null, '', location.pathname + location.search + want);
}

function installFlow(data) {
  state.flowId = data.id;
  state.base = { revision: data.revision, graph: data.graph };
  state.draft = clone(data.graph);
  state.selectedId = null;
  state.pending = null;
  state.failMsg = '';
  state.conflict = null;
  state.preview = null;
  clearErrors();
  if (location.hash !== `#flow=${data.id}`) location.hash = `flow=${data.id}`;
  renderAll();
}

async function selectFlow(id) {
  if (state.saving) {
    showError('Wait for the current save to finish before switching flows.');
    restoreHash();
    return false;
  }
  if (id === state.flowId) return true;
  if (state.flowId && hasUnsaved() && !window.confirm('Discard your unsaved changes to the current flow?')) {
    restoreHash();
    return false;
  }
  const seq = ++state.loadSeq;
  try {
    const data = await api('GET', `/flows/${id}`);
    if (seq !== state.loadSeq) return false;
    installFlow(data);
    announce(`Opened ${data.graph.title}, revision ${data.revision}`);
    return true;
  } catch (e) {
    if (seq !== state.loadSeq) return false;
    showError(errorMessages(e));
    restoreHash();
    return false;
  }
}

async function runCreate(req, onDone) {
  if (state.creating) return;
  state.creating = true;
  clearErrors();
  renderStatus();
  try {
    const body = { id: req.id, requestId: req.requestId };
    if (req.graph) body.graph = req.graph;
    else body.title = req.title;
    await api('POST', '/flows', body);
    onDone();
    await loadFlows(true);
    state.creating = false;
    renderStatus();
    await selectFlow(req.id);
  } catch (e) {
    if (!isTransient(e)) onDone(true);
    showError(isTransient(e) ? [...errorMessages(e), 'Submit again to retry the same request.'] : errorMessages(e));
  } finally {
    state.creating = false;
    renderStatus();
  }
}

function onAddFlow(ev) {
  ev.preventDefault();
  const title = $('new-flow-title').value.trim();
  if (!title) return fail('Enter a title for the new flow');
  if ([...title].length > 120) return fail('The flow title can be at most 120 characters');
  const key = title.normalize('NFC');
  if (!state.createReq || state.createReq.key !== key) {
    state.createReq = { key, id: uuid(), requestId: uuid(), title };
  }
  const req = state.createReq;
  runCreate(req, (failedPermanently) => {
    if (failedPermanently) {
      state.createReq = null;
    } else {
      state.createReq = null;
      $('new-flow-title').value = '';
    }
  });
}

function onDemo() {
  if (!state.demoReq) state.demoReq = { id: uuid(), requestId: uuid(), graph: demoGraph() };
  runCreate(state.demoReq, () => {
    state.demoReq = null;
  });
}

// ---------- saving ----------

async function save() {
  if (state.saving || state.conflict || !state.flowId) return;
  let req = state.pending;
  if (!req) {
    if (!isDirty()) return;
    req = state.pending = {
      flowId: state.flowId,
      requestId: uuid(),
      baseVersion: state.base.revision,
      graph: clone(state.draft),
    };
  }
  const seq = state.loadSeq;
  state.saving = true;
  state.failMsg = '';
  clearErrors();
  renderStatus();
  try {
    const res = await api('POST', `/flows/${req.flowId}/revisions`, {
      requestId: req.requestId,
      baseVersion: req.baseVersion,
      op: 'save',
      graph: req.graph,
    });
    if (seq !== state.loadSeq) return;
    state.pending = null;
    state.base = { revision: res.commitVersion, graph: res.graph };
    if (res.head && res.head.version > res.commitVersion) {
      state.conflict = { latest: res.head.version };
      fail(`Revision ${res.head.version} exists on the server. Your draft is preserved.`);
    } else {
      announce(`Saved revision ${res.commitVersion}`);
    }
    loadFlows(true);
  } catch (e) {
    if (seq !== state.loadSeq) return;
    if (isTransient(e)) {
      state.failMsg = e.message;
      showError(`Save failed: ${e.message}. Press Save to retry.`);
    } else if (e.status === 409 && e.code === 'version_conflict') {
      state.pending = null;
      const latest = e.details && e.details.latest ? e.details.latest.version : '?';
      state.conflict = { latest };
      showError('Another revision was saved first. Reload the latest or download your draft.');
    } else {
      state.pending = null;
      showError(errorMessages(e));
    }
  } finally {
    state.saving = false;
    renderStatus();
    renderFlows();
  }
}

async function reloadLatest() {
  if (state.saving || !state.flowId) return;
  if (!window.confirm('Reload the latest revision and discard your draft? This cannot be undone.')) return;
  const seq = ++state.loadSeq;
  try {
    const data = await api('GET', `/flows/${state.flowId}`);
    if (seq !== state.loadSeq) return;
    installFlow(data);
    announce(`Reloaded revision ${data.revision}; your draft was discarded`);
    loadFlows(true);
  } catch (e) {
    showError(errorMessages(e));
  }
}

function downloadDraft() {
  if (!state.draft) return;
  const blob = new Blob([JSON.stringify(state.draft, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = mk('a', { href: url, download: `flow-draft-${state.flowId}.json` });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
  announce('Draft JSON downloaded');
}

// ---------- events ----------

$('flow-list').addEventListener('click', (ev) => {
  const btn = ev.target.closest('button[data-id]');
  if (btn) selectFlow(btn.getAttribute('data-id'));
});

$('new-flow-form').addEventListener('submit', onAddFlow);
$('demo-btn').addEventListener('click', onDemo);
$('save-btn').addEventListener('click', save);
$('reload-btn').addEventListener('click', reloadLatest);
$('download-btn').addEventListener('click', downloadDraft);

$('flow-title').addEventListener('input', (ev) => {
  state.draft.title = ev.target.value;
  renderStatus();
});

$('add-screen-btn').addEventListener('click', addScreen);

$('screen-list').addEventListener('click', (ev) => {
  const btn = ev.target.closest('button[data-id]');
  if (btn) selectScreen(btn.getAttribute('data-id'));
});

$('screen-label').addEventListener('input', (ev) => {
  const s = selectedScreen();
  if (!s) return;
  s.label = ev.target.value;
  renderAll();
});

$('screen-kind').addEventListener('change', (ev) => setKind(ev.target.value));
$('screen-start').addEventListener('change', (ev) => setStart(ev.target.checked));

function onCoordChange() {
  const s = selectedScreen();
  if (!s) return;
  const raw = [$('screen-x').value, $('screen-y').value];
  const [nx, ny] = raw.map((v) => (v.trim() === '' ? NaN : Number(v)));
  if (!Number.isInteger(nx) || !Number.isInteger(ny)) {
    fail(`Cannot move: ${s.label} needs whole-number X and Y values`);
    renderAll();
    return;
  }
  moveScreen(s.id, nx, ny);
}
$('screen-x').addEventListener('change', onCoordChange);
$('screen-y').addEventListener('change', onCoordChange);

for (const [id, dx, dy] of [
  ['move-left', -1, 0],
  ['move-right', 1, 0],
  ['move-up', 0, -1],
  ['move-down', 0, 1],
]) {
  $(id).addEventListener('click', () => {
    const s = selectedScreen();
    if (s) moveScreen(s.id, s.x + dx, s.y + dy);
  });
}

$('remove-screen-btn').addEventListener('click', () => {
  if (state.selectedId) openRemove(state.selectedId, { type: 'button' });
});

$('remove-cancel').addEventListener('click', () => $('remove-dialog').close());
$('remove-confirm').addEventListener('click', () => {
  remove.confirmed = true;
  $('remove-dialog').close();
});
$('remove-dialog').addEventListener('close', onRemoveClosed);

$('transition-form').addEventListener('submit', (ev) => {
  ev.preventDefault();
  addTransition();
});

$('transition-list').addEventListener('click', (ev) => {
  const btn = ev.target.closest('button[data-id]');
  if (btn) deleteTransition(btn.getAttribute('data-id'));
});

// Canvas keyboard and pointer input.
$('nodes').addEventListener('keydown', (ev) => {
  const node = ev.target.closest('[data-screen-id]');
  if (!node || ev.target !== node) return;
  const id = node.getAttribute('data-screen-id');
  const s = screenById(id);
  if (!s) return;
  const arrows = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
  if (arrows[ev.key]) {
    ev.preventDefault();
    const step = ev.shiftKey ? 5 : 1;
    state.selectedId = id;
    moveScreen(id, s.x + arrows[ev.key][0] * step, s.y + arrows[ev.key][1] * step);
  } else if (ev.key === 'Delete' || ev.key === 'Backspace') {
    ev.preventDefault();
    state.selectedId = id;
    renderAll();
    openRemove(id, { type: 'canvas', id });
  } else if (ev.key === 'Enter' || ev.key === ' ') {
    ev.preventDefault();
    selectScreen(id);
  }
});

const canvas = $('canvas');

canvas.addEventListener('pointerdown', (ev) => {
  if (ev.button !== 0) return;
  const node = ev.target.closest('[data-screen-id]');
  if (!node) return;
  ev.preventDefault();
  const id = node.getAttribute('data-screen-id');
  const s = screenById(id);
  if (!s) return;
  drag = { id, pointerId: ev.pointerId, startX: ev.clientX, startY: ev.clientY, ox: s.x, oy: s.y };
  state.selectedId = id;
  renderAll();
  const fresh = $('nodes').querySelector(`[data-screen-id="${CSS.escape(id)}"]`);
  if (fresh) fresh.focus();
  try {
    canvas.setPointerCapture(ev.pointerId);
  } catch (_err) {
    // Capture is best effort; window-level moves still reach the canvas while over it.
  }
});

canvas.addEventListener('pointermove', (ev) => {
  if (!drag || ev.pointerId !== drag.pointerId) return;
  const unit = canvas.getBoundingClientRect().width / 100;
  if (!unit) return;
  const nx = drag.ox + Math.round((ev.clientX - drag.startX) / unit);
  const ny = drag.oy + Math.round((ev.clientY - drag.startY) / unit);
  const cur = state.preview;
  if (cur && cur.x === nx && cur.y === ny) return;
  if (!cur && nx === drag.ox && ny === drag.oy) return;
  state.preview = { id: drag.id, x: nx, y: ny };
  renderCanvas();
});

function endDrag(ev, commit) {
  if (!drag || ev.pointerId !== drag.pointerId) return;
  const d = drag;
  const p = state.preview;
  drag = null;
  state.preview = null;
  try {
    canvas.releasePointerCapture(ev.pointerId);
  } catch (_err) {
    // Already released.
  }
  if (commit && p && (p.x !== d.ox || p.y !== d.oy)) moveScreen(d.id, p.x, p.y);
  else renderCanvas();
}
canvas.addEventListener('pointerup', (ev) => endDrag(ev, true));
canvas.addEventListener('pointercancel', (ev) => endDrag(ev, false));

window.addEventListener('beforeunload', (ev) => {
  if (hasUnsaved()) {
    ev.preventDefault();
    ev.returnValue = '';
  }
});

window.addEventListener('hashchange', () => {
  const id = parseHash();
  if (id && id !== state.flowId) selectFlow(id);
});

// ---------- start ----------

async function boot() {
  renderAll();
  await loadFlows(false);
  const id = parseHash();
  if (id) await selectFlow(id);
}

boot();
