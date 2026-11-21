"""Graph envelope validation and normalization (schemaVersion 1)."""

import re
import unicodedata
import uuid

SCHEMA_VERSION = 1
MAX_DETAILS = 50

_ID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_TOP_KEYS = ("schemaVersion", "title", "startId", "scenarios", "screens", "transitions")
_SCENARIO_KEYS = ("id", "label")
_SCREEN_KEYS = ("id", "label", "kind", "x", "y")
_TRANSITION_KEYS = ("id", "source", "target", "label", "enabledIn")
_KINDS = ("screen", "success_exit", "alternate_exit")
_EXIT_KINDS = ("success_exit", "alternate_exit")
_BAD_CATEGORIES = ("Cc", "Cs", "Zl", "Zp")

MAX_X = 94
MAX_Y = 67
FOOTPRINT_W = 6
FOOTPRINT_H = 3


class GraphError(ValueError):
    """Raised when a graph fails validation; details lists every problem found."""

    def __init__(self, details):
        super().__init__("invalid graph")
        self.details = details


class _Errors:
    def __init__(self):
        self.items = []

    def add(self, path, message):
        if len(self.items) < MAX_DETAILS:
            self.items.append({"path": path, "message": message})

    def __bool__(self):
        return bool(self.items)


def is_id(value):
    return isinstance(value, str) and _ID_RE.fullmatch(value) is not None


def default_scenario_id(flow_id):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "flow-mapper:" + flow_id + ":default"))


def empty_graph(flow_id, title):
    errs = _Errors()
    norm_title = _label(title, "title", 120, errs)
    if errs:
        raise GraphError(errs.items)
    return validate_graph(
        {
            "schemaVersion": SCHEMA_VERSION,
            "title": norm_title,
            "startId": None,
            "scenarios": [{"id": default_scenario_id(flow_id), "label": "Default"}],
            "screens": [],
            "transitions": [],
        }
    )


def _join(path, key):
    return path + "." + key if path else key


def _label(value, path, max_len, errs):
    if not isinstance(value, str):
        errs.add(path, "must be a string")
        return None
    text = unicodedata.normalize("NFC", value.strip())
    if any(unicodedata.category(ch) in _BAD_CATEGORIES for ch in text):
        errs.add(path, "must not contain control characters or line breaks")
        return None
    if not 1 <= len(text) <= max_len:
        errs.add(path, "must be 1 to %d characters" % max_len)
        return None
    return text


def _object(value, path, keys, errs):
    """Check that value is an object with exactly the given keys."""
    if not isinstance(value, dict):
        errs.add(path, "must be an object")
        return False
    ok = True
    for key in value:
        if key not in keys:
            errs.add(_join(path, str(key)), "unknown key")
            ok = False
    for key in keys:
        if key not in value:
            errs.add(_join(path, key), "is required")
            ok = False
    return ok


def _id(value, path, seen, errs):
    if not isinstance(value, str):
        errs.add(path, "must be a string")
        return None
    if not _ID_RE.fullmatch(value):
        errs.add(path, "must be a lowercase UUID")
        return None
    if value in seen:
        errs.add(path, "duplicate id")
    seen.add(value)
    return value


def _int(value, path, hi, errs):
    if isinstance(value, bool) or not isinstance(value, int):
        errs.add(path, "must be an integer")
        return None
    if not 0 <= value <= hi:
        errs.add(path, "must be between 0 and %d" % hi)
        return None
    return value


def _array(obj, key, max_len, min_len, errs):
    value = obj.get(key)
    if not isinstance(value, list):
        errs.add(key, "must be an array")
        return []
    if not min_len <= len(value) <= max_len:
        errs.add(key, "must contain %d to %d items" % (min_len, max_len))
    return value


def validate_graph(obj):
    errs = _Errors()
    out = _validate(obj, errs)
    if errs:
        raise GraphError(errs.items)
    return out


def _validate(obj, errs):
    if not isinstance(obj, dict):
        errs.add("", "graph must be an object")
        return None
    _object(obj, "", _TOP_KEYS, errs)

    version = obj.get("schemaVersion")
    if isinstance(version, bool) or not isinstance(version, int) or version != SCHEMA_VERSION:
        errs.add("schemaVersion", "must be the integer 1")

    title = _label(obj.get("title"), "title", 120, errs)

    scenarios = []
    scenario_ids = set()
    label_keys = set()
    seen = set()
    for i, item in enumerate(_array(obj, "scenarios", 8, 1, errs)):
        path = "scenarios[%d]" % i
        if not _object(item, path, _SCENARIO_KEYS, errs):
            continue
        sid = _id(item["id"], path + ".id", seen, errs)
        label = _label(item["label"], path + ".label", 60, errs)
        if label is not None:
            key = unicodedata.normalize("NFC", label.casefold())
            if key in label_keys:
                errs.add(path + ".label", "duplicate scenario label")
            label_keys.add(key)
        if sid is not None:
            scenario_ids.add(sid)
        scenarios.append({"id": sid, "label": label})

    screens = []
    screen_kinds = {}
    placed = []
    seen = set()
    for i, item in enumerate(_array(obj, "screens", 80, 0, errs)):
        path = "screens[%d]" % i
        if not _object(item, path, _SCREEN_KEYS, errs):
            continue
        sid = _id(item["id"], path + ".id", seen, errs)
        label = _label(item["label"], path + ".label", 80, errs)
        kind = item["kind"]
        if not isinstance(kind, str) or kind not in _KINDS:
            errs.add(path + ".kind", "must be one of screen, success_exit, alternate_exit")
            kind = None
        x = _int(item["x"], path + ".x", MAX_X, errs)
        y = _int(item["y"], path + ".y", MAX_Y, errs)
        if sid is not None:
            screen_kinds[sid] = kind
        if x is not None and y is not None and len(placed) < 200:
            placed.append((i, x, y))
        screens.append({"id": sid, "label": label, "kind": kind, "x": x, "y": y})

    if len(placed) <= 80:
        for a in range(len(placed)):
            for b in range(a + 1, len(placed)):
                ia, xa, ya = placed[a]
                ib, xb, yb = placed[b]
                if abs(xa - xb) < FOOTPRINT_W and abs(ya - yb) < FOOTPRINT_H:
                    errs.add("screens[%d]" % ib, "overlaps screens[%d]" % ia)

    start = obj.get("startId")
    if start is not None:
        if not isinstance(start, str):
            errs.add("startId", "must be null or a screen id")
        elif start not in screen_kinds:
            errs.add("startId", "must reference an existing screen")
        elif screen_kinds[start] != "screen":
            errs.add("startId", "must reference a screen of kind 'screen'")

    transitions = []
    pairs = set()
    seen = set()
    for i, item in enumerate(_array(obj, "transitions", 160, 0, errs)):
        path = "transitions[%d]" % i
        if not _object(item, path, _TRANSITION_KEYS, errs):
            continue
        tid = _id(item["id"], path + ".id", seen, errs)
        ends = []
        for field in ("source", "target"):
            value = item[field]
            if not isinstance(value, str):
                errs.add(path + "." + field, "must be a string")
                ends.append(None)
            elif value not in screen_kinds:
                errs.add(path + "." + field, "must reference an existing screen")
                ends.append(None)
            else:
                ends.append(value)
        source, target = ends
        if source is not None and screen_kinds[source] in _EXIT_KINDS:
            errs.add(path + ".source", "must not be an exit screen")
        if source is not None and target is not None:
            if (source, target) in pairs:
                errs.add(path, "duplicate transition for this source and target")
            pairs.add((source, target))
        label = _label(item["label"], path + ".label", 120, errs)
        enabled = _enabled_in(item["enabledIn"], path + ".enabledIn", scenario_ids, errs)
        transitions.append(
            {"id": tid, "source": source, "target": target, "label": label, "enabledIn": enabled}
        )

    if errs:
        return None
    return {
        "schemaVersion": SCHEMA_VERSION,
        "title": title,
        "startId": start,
        "scenarios": sorted(scenarios, key=lambda s: s["id"]),
        "screens": sorted(screens, key=lambda s: s["id"]),
        "transitions": sorted(transitions, key=lambda t: t["id"]),
    }


def _enabled_in(value, path, scenario_ids, errs):
    if value is None:
        return None
    if not isinstance(value, list) or not value:
        errs.add(path, "must be null or a non-empty array")
        return None
    result = []
    ok = True
    for j, entry in enumerate(value):
        if not isinstance(entry, str) or entry not in scenario_ids:
            errs.add("%s[%d]" % (path, j), "must reference an existing scenario")
            ok = False
        elif entry in result:
            errs.add("%s[%d]" % (path, j), "duplicate scenario id")
            ok = False
        else:
            result.append(entry)
    return sorted(result) if ok else None
