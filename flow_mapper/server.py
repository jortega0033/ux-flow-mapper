"""Loopback-only HTTP server: JSON API plus static assets."""

import json
import re
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .errors import ApiError
from .storage import Store

MAX_BODY = 512 * 1024
STATIC_DIR = Path(__file__).resolve().parent / "static"
_STATIC_NAME = re.compile(r"[A-Za-z0-9_.-]+")
_JSON_TYPE = "application/json; charset=utf-8"
_MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": _JSON_TYPE,
}
_SECURITY_HEADERS = (
    ("Cache-Control", "no-store"),
    ("X-Content-Type-Options", "nosniff"),
    (
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
    ),
    ("Referrer-Policy", "no-referrer"),
)
_ROUTES = (
    (re.compile(r"/"), "index", ("GET",)),
    (re.compile(r"/index\.html"), "index", ("GET",)),
    (re.compile(r"/static/([^/]+)"), "static", ("GET",)),
    (re.compile(r"/api/v1/health"), "health", ("GET",)),
    (re.compile(r"/api/v1/flows"), "flows", ("GET", "POST")),
    (re.compile(r"/api/v1/flows/([^/]+)"), "flow", ("GET",)),
    (re.compile(r"/api/v1/flows/([^/]+)/revisions"), "revisions", ("GET", "POST")),
    (re.compile(r"/api/v1/flows/([^/]+)/revisions/([^/]+)"), "revision", ("GET",)),
)
_CREATE_KEYS = {"id", "requestId", "title", "graph"}
_SAVE_KEYS = {"requestId", "baseVersion", "op", "graph"}


class _Server(ThreadingHTTPServer):
    # On Windows SO_REUSEADDR would let another process bind the same port. On POSIX it is needed
    # to restart on the same port while old connections sit in TIME_WAIT.
    allow_reuse_address = sys.platform != "win32"
    daemon_threads = True


def create_server(data_dir, port=0, store=None):
    if store is None:
        store = Store(data_dir)
    server = _Server(("127.0.0.1", port), _Handler)
    server.store = store
    return server


def _reject_constant(name):
    raise ValueError("non-finite number")


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


class _Handler(BaseHTTPRequestHandler):
    server_version = "FlowMapper"
    sys_version = ""
    timeout = 15

    def log_message(self, format, *args):
        pass

    # Every HTTP method goes through one dispatcher.
    def do_GET(self):
        self._handle()

    do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD = do_GET

    def send_error(self, code, message=None, explain=None):
        """Replace the stock HTML error page with the JSON error shape."""
        try:
            phrase = HTTPStatus(code).phrase
        except ValueError:
            phrase = "Error"
        self.close_connection = True
        self._send_error(code, "bad_request", phrase)

    def _handle(self):
        try:
            self._process()
        except ApiError as exc:
            self._send_error(exc.status, exc.code, exc.message, exc.details)
        except (BrokenPipeError, ConnectionError, TimeoutError):
            self.close_connection = True
        except Exception as exc:
            sys.stderr.write("internal error: %s\n" % type(exc).__name__)
            try:
                self._send_error(500, "internal_error", "Internal server error")
            except OSError:
                self.close_connection = True

    # Response helpers

    def _send(self, status, body, content_type, extra=()):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in _SECURITY_HEADERS:
            self.send_header(name, value)
        for name, value in extra:
            self.send_header(name, value)
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self._send(status, body, _JSON_TYPE)

    def _send_error(self, status, code, message, details=None, extra=()):
        error = {"code": code, "message": message}
        if details is not None:
            error["details"] = details
        extra = list(extra)
        if code == "database_busy":
            extra.append(("Retry-After", "1"))
        body = json.dumps({"error": error}).encode("utf-8")
        self._send(status, body, _JSON_TYPE, extra)

    # Request processing

    def _process(self):
        port = self.server.server_address[1]
        host = self.headers.get("Host")
        if host is None or host.lower() not in ("127.0.0.1:%d" % port, "localhost:%d" % port):
            raise ApiError(403, "bad_host", "Unexpected Host header")
        method = self.command
        if method == "POST":
            if self.headers.get("Origin") != "http://" + host:
                raise ApiError(403, "bad_origin", "Unexpected Origin header")

        path = self.path.split("?", 1)[0].split("#", 1)[0]
        name = groups = allowed = None
        for pattern, route, methods in _ROUTES:
            match = pattern.fullmatch(path)
            if match:
                name, groups, allowed = route, match.groups(), methods
                break
        if name is None:
            raise ApiError(404, "not_found", "Not found")
        if method not in allowed:
            self._send_error(
                405, "method_not_allowed", "Method not allowed", extra=[("Allow", ", ".join(allowed))]
            )
            return

        body = self._read_json() if method == "POST" else None

        if name == "index":
            self._send_static("index.html")
        elif name == "static":
            self._send_static(groups[0])
        elif name == "health":
            self._send_json(200, self.server.store.health())
        elif name == "flows":
            if method == "GET":
                self._send_json(200, self.server.store.list_flows())
            else:
                self._create_flow(body)
        elif name == "flow":
            self._send_json(200, self.server.store.get_flow(groups[0]))
        elif name == "revisions":
            if method == "GET":
                self._send_json(200, self.server.store.list_revisions(groups[0]))
            else:
                self._save(groups[0], body)
        else:
            version = groups[1]
            if not (version.isascii() and version.isdigit()) or len(version) > 18:
                raise ApiError(404, "not_found", "Revision not found")
            self._send_json(200, self.server.store.get_revision(groups[0], int(version)))

    def _read_json(self):
        ctype = self.headers.get("Content-Type") or ""
        if not ctype.lower().startswith("application/json"):
            raise ApiError(400, "bad_request", "Content-Type must be application/json")
        length = self.headers.get("Content-Length")
        if length is None or not (length.isascii() and length.isdigit()) or len(length) > 18:
            raise ApiError(400, "bad_request", "A valid Content-Length is required")
        length = int(length)
        if length > MAX_BODY:
            raise ApiError(413, "payload_too_large", "Request body is too large")
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise ApiError(400, "bad_request", "Request body was truncated")
        try:
            data = json.loads(
                raw.decode("utf-8"),
                parse_constant=_reject_constant,
                object_pairs_hook=_no_duplicates,
            )
        except (ValueError, RecursionError):
            raise ApiError(400, "bad_json", "Request body is not valid JSON") from None
        if not isinstance(data, dict):
            raise ApiError(400, "bad_json", "Request body must be a JSON object")
        return data

    def _create_flow(self, body):
        if not set(body) <= _CREATE_KEYS:
            raise ApiError(422, "invalid_request", "Unknown keys in request")
        result, created = self.server.store.create_flow(
            body.get("id"), body.get("requestId"), body.get("title"), body.get("graph")
        )
        self._send_json(201 if created else 200, result)

    def _save(self, flow_id, body):
        if not set(body) <= _SAVE_KEYS:
            raise ApiError(422, "invalid_request", "Unknown keys in request")
        missing = sorted(_SAVE_KEYS - set(body))
        if missing:
            raise ApiError(422, "invalid_request", "Missing keys: " + ", ".join(missing))
        if body["op"] != "save":
            raise ApiError(422, "invalid_request", "Only op 'save' is supported")
        result, committed = self.server.store.save_revision(
            flow_id, body["requestId"], body["baseVersion"], body["graph"]
        )
        self._send_json(201 if committed else 200, result)

    def _send_static(self, name):
        suffix = Path(name).suffix.lower()
        if (
            not _STATIC_NAME.fullmatch(name)
            or name.startswith(".")
            or suffix not in _MIME
        ):
            raise ApiError(404, "not_found", "Not found")
        target = STATIC_DIR / name
        try:
            data = target.read_bytes() if target.is_file() else None
        except OSError:
            data = None
        if data is None:
            raise ApiError(404, "not_found", "Not found")
        self._send(200, data, _MIME[suffix])
