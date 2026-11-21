import os
import sqlite3
import tempfile
import unittest

from flow_mapper.errors import ApiError
from flow_mapper.storage import Store
from tests.support import clone, demo_graph, new_id, small_graph, uid


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name
        self.store = Store(self.dir)

    def db_path(self):
        return os.path.join(self.dir, "flow_mapper.sqlite3")

    def make_flow(self, title="Scratch flow"):
        flow_id = new_id()
        body, created = self.store.create_flow(flow_id, new_id(), title=title)
        self.assertTrue(created)
        return flow_id, body

    def assert_api_error(self, status, code, fn, *args, **kwargs):
        with self.assertRaises(ApiError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual((ctx.exception.status, ctx.exception.code), (status, code))
        return ctx.exception


class CreateAndListTests(StoreTestCase):
    def test_empty_storage_lists_nothing(self):
        self.assertEqual(self.store.list_flows(), {"flows": []})
        self.assertEqual(self.store.health()["status"], "ok")

    def test_create_makes_revision_one(self):
        flow_id, body = self.make_flow()
        self.assertEqual(body["revision"], 1)
        self.assertFalse(body["replayed"])
        listing = self.store.list_flows()["flows"]
        self.assertEqual([(f["id"], f["title"], f["revision"]) for f in listing], [(flow_id, "Scratch flow", 1)])
        self.assertEqual(self.store.get_flow(flow_id)["graph"], body["graph"])

    def test_create_with_graph(self):
        flow_id = new_id()
        body, created = self.store.create_flow(flow_id, new_id(), graph=demo_graph())
        self.assertTrue(created)
        self.assertEqual(body["graph"]["title"], "Demo: checkout journey")
        self.assertEqual(len(body["graph"]["screens"]), 8)

    def test_title_xor_graph(self):
        self.assert_api_error(422, "invalid_request", self.store.create_flow, new_id(), new_id())
        self.assert_api_error(
            422, "invalid_request", self.store.create_flow, new_id(), new_id(), title="x", graph=small_graph()
        )

    def test_invalid_title_and_graph_rejected_without_writing(self):
        self.assert_api_error(422, "invalid_graph", self.store.create_flow, new_id(), new_id(), title="   ")
        bad = small_graph()
        bad["screens"][1].update(x=bad["screens"][0]["x"], y=bad["screens"][0]["y"])
        self.assert_api_error(422, "invalid_graph", self.store.create_flow, new_id(), new_id(), graph=bad)
        self.assertEqual(self.store.list_flows(), {"flows": []})

    def test_create_replay_and_conflicts(self):
        flow_id, request_id = new_id(), new_id()
        first, created = self.store.create_flow(flow_id, request_id, title="Scratch flow")
        self.assertTrue(created)
        replay, created = self.store.create_flow(flow_id, request_id, title="Scratch flow")
        self.assertFalse(created)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["graph"], first["graph"])
        self.assertEqual(len(self.store.list_flows()["flows"]), 1)
        self.assert_api_error(409, "request_conflict", self.store.create_flow, flow_id, request_id, title="Other")
        self.assert_api_error(409, "flow_exists", self.store.create_flow, flow_id, new_id(), title="Scratch flow")

    def test_unknown_flow_is_404(self):
        self.assert_api_error(404, "not_found", self.store.get_flow, new_id())
        self.assert_api_error(404, "not_found", self.store.get_flow, "not-a-uuid")
        self.assert_api_error(404, "not_found", self.store.list_revisions, new_id())


class SaveTests(StoreTestCase):
    def test_save_increments_and_updates_listing(self):
        flow_id, created = self.make_flow()
        graph = small_graph(title="Renamed flow")
        body, committed = self.store.save_revision(flow_id, new_id(), 1, graph)
        self.assertTrue(committed)
        self.assertEqual(body["commitVersion"], 2)
        self.assertEqual(body["head"]["version"], 2)
        self.assertFalse(body["replayed"])
        listing = self.store.list_flows()["flows"][0]
        self.assertEqual((listing["title"], listing["revision"]), ("Renamed flow", 2))
        current = self.store.get_flow(flow_id)
        self.assertEqual(current["revision"], 2)
        self.assertEqual(current["graph"], body["graph"])
        self.assertEqual([r["version"] for r in self.store.list_revisions(flow_id)["revisions"]], [1, 2])
        self.assertEqual(self.store.get_revision(flow_id, 1)["graph"], created["graph"])

    def test_stale_base_conflicts_and_head_is_untouched(self):
        flow_id, _ = self.make_flow()
        self.store.save_revision(flow_id, new_id(), 1, small_graph(title="Tab A"))
        err = self.assert_api_error(
            409, "version_conflict", self.store.save_revision, flow_id, new_id(), 1, small_graph(title="Tab B")
        )
        self.assertEqual(err.details["latest"]["version"], 2)
        self.assertEqual(self.store.get_flow(flow_id)["graph"]["title"], "Tab A")
        self.assertEqual(len(self.store.list_revisions(flow_id)["revisions"]), 2)

    def test_replay_returns_original_commit_even_with_newer_head(self):
        flow_id, _ = self.make_flow()
        request_a = new_id()
        graph_a = small_graph(title="Tab A")
        first, _ = self.store.save_revision(flow_id, request_a, 1, graph_a)
        self.store.save_revision(flow_id, new_id(), 2, small_graph(title="Later"))
        replay, committed = self.store.save_revision(flow_id, request_a, 1, graph_a)
        self.assertFalse(committed)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["commitVersion"], first["commitVersion"])
        self.assertEqual(replay["head"]["version"], 3)
        self.assertEqual(replay["graph"]["title"], "Tab A")
        self.assertEqual(len(self.store.list_revisions(flow_id)["revisions"]), 3)

    def test_same_request_id_with_different_payload_conflicts(self):
        flow_id, _ = self.make_flow()
        request_id = new_id()
        self.store.save_revision(flow_id, request_id, 1, small_graph(title="One"))
        self.assert_api_error(
            409, "request_conflict", self.store.save_revision, flow_id, request_id, 1, small_graph(title="Two")
        )
        self.assertEqual(self.store.get_flow(flow_id)["revision"], 2)

    def test_replay_check_precedes_base_version_check(self):
        flow_id, _ = self.make_flow()
        request_id = new_id()
        graph = small_graph(title="One")
        self.store.save_revision(flow_id, request_id, 1, graph)
        replay, committed = self.store.save_revision(flow_id, request_id, 1, graph)
        self.assertFalse(committed)
        self.assertEqual(replay["commitVersion"], 2)

    def test_invalid_graph_commits_nothing(self):
        flow_id, _ = self.make_flow()
        bad = small_graph()
        bad["transitions"][0]["target"] = uid("a", 7)
        self.assert_api_error(422, "invalid_graph", self.store.save_revision, flow_id, new_id(), 1, bad)
        self.assertEqual(self.store.get_flow(flow_id)["revision"], 1)

    def test_unknown_flow_save_is_404(self):
        self.assert_api_error(404, "not_found", self.store.save_revision, new_id(), new_id(), 1, small_graph())

    def test_bad_base_version_is_rejected(self):
        flow_id, _ = self.make_flow()
        for bad in [0, -1, "1", None, True]:
            self.assert_api_error(
                422, "invalid_request", self.store.save_revision, flow_id, new_id(), bad, small_graph()
            )

    def test_removed_screen_with_dangling_references_is_rejected(self):
        flow_id, _ = self.make_flow()
        g = demo_graph()
        self.store.save_revision(flow_id, new_id(), 1, g)
        dangling = clone(g)
        dangling["screens"] = [s for s in dangling["screens"] if s["id"] != uid("a", 2)]
        self.assert_api_error(422, "invalid_graph", self.store.save_revision, flow_id, new_id(), 2, dangling)
        # The same removal done properly (incident transitions gone, start untouched) is accepted.
        ok = clone(dangling)
        ok["transitions"] = [t for t in ok["transitions"] if uid("a", 2) not in (t["source"], t["target"])]
        body, _ = self.store.save_revision(flow_id, new_id(), 2, ok)
        self.assertEqual(len(body["graph"]["screens"]), 7)


class DurabilityTests(StoreTestCase):
    def test_state_survives_reopening_the_store(self):
        flow_id, _ = self.make_flow()
        body, _ = self.store.save_revision(flow_id, new_id(), 1, demo_graph())
        reopened = Store(self.dir)
        flows = reopened.list_flows()["flows"]
        self.assertEqual([(f["id"], f["revision"]) for f in flows], [(flow_id, 2)])
        self.assertEqual(reopened.get_flow(flow_id)["graph"], body["graph"])

    def test_mid_save_failure_rolls_back_and_retry_commits_once(self):
        flow_id, _ = self.make_flow()
        state = {"fail": True}

        def hook(stage):
            if state["fail"] and stage == "after_revision_insert":
                raise RuntimeError("injected failure")

        faulty = Store(self.dir, fault_hook=hook)
        request_id = new_id()
        graph = small_graph(title="Retried")
        with self.assertRaises(Exception):
            faulty.save_revision(flow_id, request_id, 1, graph)
        conn = sqlite3.connect(self.db_path())
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM revision WHERE flow_id=?", (flow_id,)).fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT revision, title FROM flow WHERE id=?", (flow_id,)).fetchone(),
                             (1, "Scratch flow"))
        finally:
            conn.close()
        state["fail"] = False
        body, committed = faulty.save_revision(flow_id, request_id, 1, graph)
        self.assertTrue(committed)
        self.assertEqual(body["commitVersion"], 2)
        self.assertEqual(len(self.store.list_revisions(flow_id)["revisions"]), 2)

    def test_lock_contention_returns_database_busy(self):
        flow_id, _ = self.make_flow()
        impatient = Store(self.dir, busy_timeout_ms=50)
        blocker = sqlite3.connect(self.db_path(), isolation_level=None)
        try:
            blocker.execute("BEGIN IMMEDIATE")
            self.assert_api_error(
                503, "database_busy", impatient.save_revision, flow_id, new_id(), 1, small_graph()
            )
        finally:
            blocker.execute("ROLLBACK")
            blocker.close()
        body, committed = impatient.save_revision(flow_id, new_id(), 1, small_graph())
        self.assertTrue(committed)

    def test_future_schema_version_is_refused(self):
        conn = sqlite3.connect(self.db_path())
        conn.execute("PRAGMA user_version = 99")
        conn.commit()
        conn.close()
        with self.assertRaises(Exception):
            Store(self.dir)


if __name__ == "__main__":
    unittest.main()
