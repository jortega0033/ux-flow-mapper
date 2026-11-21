"""SQLite persistence for flows and their revisions."""

import contextlib
import datetime
import hashlib
import json
import os
import sqlite3

from .errors import ApiError
from .graph import GraphError, empty_graph, is_id, validate_graph

USER_VERSION = 1
DB_NAME = "flow_mapper.sqlite3"

_DDL = (
    """CREATE TABLE IF NOT EXISTS flow(
        id TEXT PRIMARY KEY,
        revision INTEGER NOT NULL,
        title TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS revision(
        flow_id TEXT NOT NULL REFERENCES flow(id),
        version INTEGER NOT NULL,
        graph_json TEXT NOT NULL,
        request_id TEXT NOT NULL,
        request_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        restored_from INTEGER,
        PRIMARY KEY(flow_id, version),
        UNIQUE(flow_id, request_id))""",
)


class StorageVersionError(RuntimeError):
    """The database was written by a newer version of this program."""


def _now():
    dt = datetime.datetime.now(datetime.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (dt.microsecond // 1000)


def _dump(graph):
    return json.dumps(graph, separators=(",", ":"), ensure_ascii=False)


def _hash(doc):
    text = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _graph_api_error(exc):
    return ApiError(422, "invalid_graph", "The graph is not valid", exc.details)


def _not_found(what="Flow"):
    return ApiError(404, "not_found", what + " not found")


def _busy_error(exc):
    text = str(exc).lower()
    if "locked" in text or "busy" in text:
        return ApiError(503, "database_busy", "The database is busy; try again")
    return None


def _rollback(conn):
    try:
        conn.execute("ROLLBACK")
    except sqlite3.Error:
        pass


class Store:
    def __init__(self, data_dir, busy_timeout_ms=1000, fault_hook=None):
        self._busy_ms = int(busy_timeout_ms)
        self.fault_hook = fault_hook
        os.makedirs(data_dir, exist_ok=True)
        self.path = os.path.join(os.fspath(data_dir), DB_NAME)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=self._busy_ms / 1000.0, isolation_level=None)
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        conn = self._connect()
        try:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version > USER_VERSION:
                raise StorageVersionError(
                    "Database %s has schema version %d, but this program only supports up to %d. "
                    "Upgrade the program or use a different data directory."
                    % (self.path, version, USER_VERSION)
                )
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("BEGIN IMMEDIATE")
            try:
                version = conn.execute("PRAGMA user_version").fetchone()[0]
                if version > USER_VERSION:
                    raise StorageVersionError(
                        "Database %s has schema version %d, but this program only supports up to %d."
                        % (self.path, version, USER_VERSION)
                    )
                if version < 1:
                    for stmt in _DDL:
                        conn.execute(stmt)
                    conn.execute("PRAGMA user_version=%d" % USER_VERSION)
                conn.execute("COMMIT")
            except BaseException:
                _rollback(conn)
                raise
        finally:
            conn.close()

    @contextlib.contextmanager
    def _txn(self, immediate):
        try:
            conn = self._connect()
        except sqlite3.OperationalError as exc:
            err = _busy_error(exc)
            if err:
                raise err from exc
            raise
        try:
            try:
                conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
                try:
                    yield conn
                    conn.execute("COMMIT")
                except BaseException:
                    _rollback(conn)
                    raise
            except sqlite3.OperationalError as exc:
                err = _busy_error(exc)
                if err:
                    raise err from exc
                raise
        finally:
            conn.close()

    def health(self):
        with self._txn(False) as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ok", "schemaVersion": 1, "storage": "ready"}

    def list_flows(self):
        with self._txn(False) as conn:
            rows = conn.execute(
                "SELECT id, title, revision, updated_at FROM flow ORDER BY updated_at DESC, id"
            ).fetchall()
        return {
            "flows": [
                {"id": r[0], "title": r[1], "revision": r[2], "updatedAt": r[3]} for r in rows
            ]
        }

    def create_flow(self, flow_id, request_id, title=None, graph=None):
        if not is_id(flow_id):
            raise ApiError(422, "invalid_request", "id must be a lowercase UUID")
        if not is_id(request_id):
            raise ApiError(422, "invalid_request", "requestId must be a lowercase UUID")
        if (title is None) == (graph is None):
            raise ApiError(422, "invalid_request", "Provide exactly one of title or graph")
        try:
            if graph is not None:
                norm = validate_graph(graph)
                doc_graph, doc_title = norm, None
            else:
                norm = empty_graph(flow_id, title)
                doc_graph, doc_title = None, norm["title"]
        except GraphError as exc:
            raise _graph_api_error(exc) from exc
        req_hash = _hash(
            {"op": "create", "flowId": flow_id, "graph": doc_graph, "title": doc_title}
        )

        with self._txn(True) as conn:
            exists = conn.execute("SELECT 1 FROM flow WHERE id=?", (flow_id,)).fetchone()
            if exists is None:
                now = _now()
                conn.execute(
                    "INSERT INTO flow(id, revision, title, created_at, updated_at) "
                    "VALUES (?, 1, ?, ?, ?)",
                    (flow_id, norm["title"], now, now),
                )
                conn.execute(
                    "INSERT INTO revision(flow_id, version, graph_json, request_id, "
                    "request_hash, created_at, restored_from) VALUES (?, 1, ?, ?, ?, ?, NULL)",
                    (flow_id, _dump(norm), request_id, req_hash, now),
                )
                body = {
                    "id": flow_id,
                    "revision": 1,
                    "updatedAt": now,
                    "graph": norm,
                    "replayed": False,
                }
                return body, True
            row = conn.execute(
                "SELECT version, graph_json, request_hash, created_at FROM revision "
                "WHERE flow_id=? AND request_id=?",
                (flow_id, request_id),
            ).fetchone()
            if row is None:
                raise ApiError(409, "flow_exists", "A flow with this id already exists")
            if row[2] != req_hash:
                raise ApiError(
                    409, "request_conflict", "This request id was already used for a different request"
                )
            body = {
                "id": flow_id,
                "revision": row[0],
                "updatedAt": row[3],
                "graph": json.loads(row[1]),
                "replayed": True,
            }
            return body, False

    def get_flow(self, flow_id):
        if not is_id(flow_id):
            raise _not_found()
        with self._txn(False) as conn:
            row = conn.execute(
                "SELECT f.revision, f.updated_at, r.graph_json FROM flow f "
                "JOIN revision r ON r.flow_id = f.id AND r.version = f.revision WHERE f.id=?",
                (flow_id,),
            ).fetchone()
        if row is None:
            raise _not_found()
        return {
            "id": flow_id,
            "revision": row[0],
            "updatedAt": row[1],
            "graph": json.loads(row[2]),
        }

    def save_revision(self, flow_id, request_id, base_version, graph):
        if not is_id(flow_id):
            raise _not_found()
        if not is_id(request_id):
            raise ApiError(422, "invalid_request", "requestId must be a lowercase UUID")
        if isinstance(base_version, bool) or not isinstance(base_version, int) or base_version < 1:
            raise ApiError(422, "invalid_request", "baseVersion must be an integer >= 1")

        with self._txn(False) as conn:
            if conn.execute("SELECT 1 FROM flow WHERE id=?", (flow_id,)).fetchone() is None:
                raise _not_found()
        try:
            norm = validate_graph(graph)
        except GraphError as exc:
            raise _graph_api_error(exc) from exc
        req_hash = _hash({"baseVersion": base_version, "graph": norm, "op": "save"})

        with self._txn(True) as conn:
            flow = conn.execute(
                "SELECT revision, title, updated_at FROM flow WHERE id=?", (flow_id,)
            ).fetchone()
            if flow is None:
                raise _not_found()
            head_version, head_title, head_updated = flow

            row = conn.execute(
                "SELECT version, graph_json, request_hash FROM revision "
                "WHERE flow_id=? AND request_id=?",
                (flow_id, request_id),
            ).fetchone()
            if row is not None:
                if row[2] != req_hash:
                    raise ApiError(
                        409,
                        "request_conflict",
                        "This request id was already used for a different request",
                    )
                body = {
                    "id": flow_id,
                    "commitVersion": row[0],
                    "head": {
                        "version": head_version,
                        "title": head_title,
                        "updatedAt": head_updated,
                    },
                    "graph": json.loads(row[1]),
                    "replayed": True,
                }
                return body, False

            if base_version != head_version:
                raise ApiError(
                    409,
                    "version_conflict",
                    "The flow was changed by a newer revision",
                    {"latest": {"version": head_version, "updatedAt": head_updated}},
                )

            now = _now()
            version = head_version + 1
            conn.execute(
                "INSERT INTO revision(flow_id, version, graph_json, request_id, "
                "request_hash, created_at, restored_from) VALUES (?, ?, ?, ?, ?, ?, NULL)",
                (flow_id, version, _dump(norm), request_id, req_hash, now),
            )
            if self.fault_hook is not None:
                self.fault_hook("after_revision_insert")
            conn.execute(
                "UPDATE flow SET revision=?, title=?, updated_at=? WHERE id=?",
                (version, norm["title"], now, flow_id),
            )
            body = {
                "id": flow_id,
                "commitVersion": version,
                "head": {"version": version, "title": norm["title"], "updatedAt": now},
                "graph": norm,
                "replayed": False,
            }
            return body, True

    def list_revisions(self, flow_id):
        if not is_id(flow_id):
            raise _not_found()
        with self._txn(False) as conn:
            if conn.execute("SELECT 1 FROM flow WHERE id=?", (flow_id,)).fetchone() is None:
                raise _not_found()
            rows = conn.execute(
                "SELECT version, created_at, restored_from FROM revision "
                "WHERE flow_id=? ORDER BY version",
                (flow_id,),
            ).fetchall()
        return {
            "id": flow_id,
            "revisions": [
                {"version": r[0], "createdAt": r[1], "restoredFrom": r[2]} for r in rows
            ],
        }

    def get_revision(self, flow_id, version):
        if not is_id(flow_id):
            raise _not_found()
        if (
            isinstance(version, bool)
            or not isinstance(version, int)
            or not 1 <= version < 2**62
        ):
            raise _not_found("Revision")
        with self._txn(False) as conn:
            row = conn.execute(
                "SELECT created_at, graph_json FROM revision WHERE flow_id=? AND version=?",
                (flow_id, version),
            ).fetchone()
        if row is None:
            raise _not_found("Revision")
        return {
            "id": flow_id,
            "version": version,
            "createdAt": row[0],
            "graph": json.loads(row[1]),
        }
