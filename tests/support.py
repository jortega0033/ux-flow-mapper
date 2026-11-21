"""Shared fixtures and helpers for the baseline tests. All data is fictional."""

import copy
import http.client
import json
import threading
import uuid

from flow_mapper.server import create_server


def uid(kind, n):
    """Stable fixture id: kind is 'a' (screen), 'b' (transition) or 'c' (scenario)."""
    return f"00000000-0000-4000-8000-0000000000{kind}{n}"


ONLINE = uid("c", 1)
OFFLINE = uid("c", 2)

_SCREENS = [
    ("Cart", "screen", 2, 4),
    ("Shipping", "screen", 15, 4),
    ("Order placed", "success_exit", 31, 4),
    ("Offline notice", "screen", 15, 14),
    ("Payment retry", "screen", 31, 14),
    ("Card details", "screen", 45, 14),
    ("Unused tips", "screen", 45, 26),
    ("Cancelled", "alternate_exit", 31, 26),
]

# (alias source, alias target, label, enabledIn)
_EDGES = [
    (1, 2, "Continue", None),
    (2, 8, "Cancel", None),
    (2, 3, "Pay", [ONLINE]),
    (2, 5, "Retry payment", [ONLINE]),
    (5, 6, "Edit card", [ONLINE]),
    (6, 5, "Re-enter", [ONLINE]),
    (2, 4, "Work offline", [OFFLINE]),
]


def demo_graph():
    return {
        "schemaVersion": 1,
        "title": "Demo: checkout journey",
        "startId": uid("a", 1),
        "scenarios": [
            {"id": ONLINE, "label": "Online"},
            {"id": OFFLINE, "label": "Offline"},
        ],
        "screens": [
            {"id": uid("a", i + 1), "label": label, "kind": kind, "x": x, "y": y}
            for i, (label, kind, x, y) in enumerate(_SCREENS)
        ],
        "transitions": [
            {
                "id": uid("b", i + 1),
                "source": uid("a", s),
                "target": uid("a", t),
                "label": label,
                "enabledIn": enabled,
            }
            for i, (s, t, label, enabled) in enumerate(_EDGES)
        ],
    }


def small_graph(title="Scratch flow"):
    """Two screens and one transition, built from the demo fixture."""
    g = demo_graph()
    g["title"] = title
    keep = {uid("a", 1), uid("a", 2)}
    g["screens"] = [s for s in g["screens"] if s["id"] in keep]
    g["transitions"] = [t for t in g["transitions"] if t["id"] == uid("b", 1)]
    return g


def clone(obj):
    return copy.deepcopy(obj)


def new_id():
    return str(uuid.uuid4())


class RunningServer:
    """Real loopback HTTP server on an ephemeral port over a given data directory."""

    def __init__(self, data_dir):
        self.httpd = create_server(data_dir, port=0)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def origin(self):
        return f"http://127.0.0.1:{self.port}"

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def request(self, method, path, body=None, headers=None, raw_body=None, origin=True, host=None,
                declared_length=None):
        """Returns (status, headers, parsed_json_or_bytes).

        declared_length sends that Content-Length without any body bytes, for size-cap checks.
        """
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            hdrs = dict(headers or {})
            data = raw_body
            if body is not None:
                data = json.dumps(body).encode("utf-8")
            if data is not None:
                hdrs.setdefault("Content-Type", "application/json")
            if method == "POST" and origin is True:
                hdrs.setdefault("Origin", self.origin)
            elif isinstance(origin, str):
                hdrs["Origin"] = origin
            conn.putrequest(method, path, skip_host=host is not None)
            if host is not None:
                conn.putheader("Host", host)
            for key, value in hdrs.items():
                conn.putheader(key, value)
            if declared_length is not None:
                conn.putheader("Content-Length", str(declared_length))
                conn.endheaders()
            else:
                if data is not None:
                    conn.putheader("Content-Length", str(len(data)))
                conn.endheaders(data)
            resp = conn.getresponse()
            payload = resp.read()
            ctype = resp.getheader("Content-Type", "")
            if "json" in ctype:
                payload = json.loads(payload.decode("utf-8"))
            return resp.status, resp, payload
        finally:
            conn.close()
