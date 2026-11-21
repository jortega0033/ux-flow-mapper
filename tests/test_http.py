import json
import tempfile
import unittest

from tests.support import RunningServer, clone, demo_graph, new_id, small_graph, uid


class HttpTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.server = RunningServer(self._tmp.name)
        self.addCleanup(self._stop_if_running)

    def _stop_if_running(self):
        if self.server is not None:
            self.server.stop()
            self.server = None

    def restart(self):
        self.server.stop()
        self.server = RunningServer(self._tmp.name)

    def create(self, title="Scratch flow", flow_id=None):
        flow_id = flow_id or new_id()
        status, _, body = self.server.request("POST", "/api/v1/flows", {"id": flow_id, "requestId": new_id(), "title": title})
        self.assertEqual(status, 201, body)
        return flow_id, body

    def save(self, flow_id, base, graph, request_id=None):
        return self.server.request(
            "POST",
            f"/api/v1/flows/{flow_id}/revisions",
            {"requestId": request_id or new_id(), "baseVersion": base, "op": "save", "graph": graph},
        )


class ApiBasicsTests(HttpTestCase):
    def test_health(self):
        status, _, body = self.server.request("GET", "/api/v1/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")

    def test_security_headers_on_api_and_static(self):
        for path in ["/api/v1/health", "/"]:
            status, resp, _ = self.server.request("GET", path)
            self.assertEqual(status, 200, path)
            self.assertEqual(resp.getheader("Cache-Control"), "no-store")
            self.assertEqual(resp.getheader("X-Content-Type-Options"), "nosniff")
            csp = resp.getheader("Content-Security-Policy")
            self.assertIn("default-src 'self'", csp)
            self.assertIn("script-src 'self'", csp)

    def test_empty_storage_lists_no_flows(self):
        status, _, body = self.server.request("GET", "/api/v1/flows")
        self.assertEqual((status, body), (200, {"flows": []}))

    def test_server_binds_loopback_only(self):
        self.assertEqual(self.server.httpd.server_address[0], "127.0.0.1")

    def test_unknown_route_and_method(self):
        status, _, body = self.server.request("GET", "/api/v1/nope")
        self.assertEqual((status, body["error"]["code"]), (404, "not_found"))
        status, resp, body = self.server.request("DELETE", "/api/v1/flows")
        self.assertEqual((status, body["error"]["code"]), (405, "method_not_allowed"))
        self.assertTrue(resp.getheader("Allow"))

    def test_unknown_flow_is_404(self):
        for path in [f"/api/v1/flows/{new_id()}", "/api/v1/flows/not-a-uuid", f"/api/v1/flows/{new_id()}/revisions"]:
            status, _, body = self.server.request("GET", path)
            self.assertEqual((status, body["error"]["code"]), (404, "not_found"), path)


class RequestGuardTests(HttpTestCase):
    def test_foreign_host_is_rejected(self):
        for host in ["evil.example", "evil.example:80", f"127.0.0.1.evil.example:{self.server.port}", "127.0.0.1:1"]:
            status, _, body = self.server.request("GET", "/api/v1/health", host=host)
            self.assertEqual((status, body["error"]["code"]), (403, "bad_host"), host)
        status, _, _ = self.server.request("GET", "/api/v1/health", host=f"localhost:{self.server.port}")
        self.assertEqual(status, 200)

    def test_foreign_host_cannot_read_static_files_either(self):
        status, _, _ = self.server.request("GET", "/", host="evil.example")
        self.assertEqual(status, 403)

    def test_write_requires_same_origin(self):
        payload = {"id": new_id(), "requestId": new_id(), "title": "Scratch flow"}
        for origin in [None, "http://evil.example", "http://127.0.0.1:1", "null"]:
            hdrs = {}
            if origin is not None:
                hdrs["Origin"] = origin
            status, _, body = self.server.request("POST", "/api/v1/flows", payload, headers=hdrs, origin=False)
            self.assertEqual((status, body["error"]["code"]), (403, "bad_origin"), origin)
        status, _, body = self.server.request("GET", "/api/v1/flows")
        self.assertEqual(body["flows"], [])

    def test_malformed_and_non_object_json(self):
        status, _, body = self.server.request("POST", "/api/v1/flows", raw_body=b"{not json")
        self.assertEqual((status, body["error"]["code"]), (400, "bad_json"))
        status, _, body = self.server.request("POST", "/api/v1/flows", raw_body=b"[1,2]")
        self.assertEqual((status, body["error"]["code"]), (400, "bad_json"))

    def test_wrong_content_type(self):
        status, _, body = self.server.request(
            "POST", "/api/v1/flows", raw_body=b"{}", headers={"Content-Type": "text/plain"}
        )
        self.assertEqual((status, body["error"]["code"]), (400, "bad_request"))

    def test_oversized_body_is_413(self):
        status, _, body = self.server.request(
            "POST", "/api/v1/flows", headers={"Content-Type": "application/json"}, declared_length=512 * 1024 + 1
        )
        self.assertEqual((status, body["error"]["code"]), (413, "payload_too_large"))

    def test_invalid_request_shapes_are_422(self):
        for payload in [{}, {"id": "x", "requestId": new_id(), "title": "t"},
                        {"id": new_id(), "requestId": "x", "title": "t"},
                        {"id": new_id(), "requestId": new_id(), "title": "t", "extra": 1}]:
            status, _, body = self.server.request("POST", "/api/v1/flows", payload)
            self.assertEqual(status, 422, payload)
            self.assertIn(body["error"]["code"], ("invalid_request", "invalid_graph"))

    def test_error_bodies_never_include_tracebacks(self):
        status, _, body = self.server.request("POST", "/api/v1/flows", raw_body=b"{nope")
        text = json.dumps(body)
        self.assertNotIn("Traceback", text)
        self.assertNotIn(".py", text)


class StaticTests(HttpTestCase):
    def test_index_and_assets_are_served(self):
        status, resp, body = self.server.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", resp.getheader("Content-Type"))
        self.assertIn(b"/static/app.js", body)
        for path in ["/static/app.js", "/static/style.css"]:
            status, _, _ = self.server.request("GET", path)
            self.assertEqual(status, 200, path)

    def test_traversal_and_unknown_files_are_404(self):
        for path in ["/static/../server.py", "/static/%2e%2e/server.py", "/static/missing.js", "/static/.hidden",
                     "/static/sub/app.js", "/static/..%5Cserver.py", "/server.py"]:
            status, _, _ = self.server.request("GET", path)
            self.assertEqual(status, 404, path)


class JourneyTests(HttpTestCase):
    def test_a1_create_save_restart_reopen(self):
        flow_id, created = self.create("Checkout review")
        self.assertEqual(created["revision"], 1)
        graph = clone(created["graph"])
        graph["screens"] = [
            {"id": uid("a", 1), "label": "Cart", "kind": "screen", "x": 2, "y": 4},
            {"id": uid("a", 2), "label": "Shipping", "kind": "screen", "x": 15, "y": 4},
        ]
        graph["startId"] = uid("a", 1)
        status, _, saved = self.save(flow_id, 1, graph)
        self.assertEqual((status, saved["commitVersion"]), (201, 2))
        self.restart()
        status, _, listing = self.server.request("GET", "/api/v1/flows")
        self.assertEqual([(f["id"], f["title"], f["revision"]) for f in listing["flows"]],
                         [(flow_id, "Checkout review", 2)])
        status, _, reopened = self.server.request("GET", f"/api/v1/flows/{flow_id}")
        self.assertEqual(reopened["revision"], 2)
        self.assertEqual(reopened["graph"], saved["graph"])
        self.assertEqual([(s["label"], s["x"], s["y"]) for s in reopened["graph"]["screens"]],
                         [("Cart", 2, 4), ("Shipping", 15, 4)])

    def test_create_replay_over_http(self):
        flow_id, request_id = new_id(), new_id()
        payload = {"id": flow_id, "requestId": request_id, "graph": demo_graph()}
        status, _, first = self.server.request("POST", "/api/v1/flows", payload)
        self.assertEqual(status, 201)
        status, _, again = self.server.request("POST", "/api/v1/flows", payload)
        self.assertEqual(status, 200)
        self.assertTrue(again["replayed"])
        status, _, listing = self.server.request("GET", "/api/v1/flows")
        self.assertEqual(len(listing["flows"]), 1)
        status, _, body = self.server.request(
            "POST", "/api/v1/flows", {"id": flow_id, "requestId": new_id(), "title": "Another"}
        )
        self.assertEqual((status, body["error"]["code"]), (409, "flow_exists"))

    def test_a3_overlap_save_rejected_and_nothing_committed(self):
        flow_id, _ = self.create()
        graph = small_graph()
        graph["screens"][1].update(x=graph["screens"][0]["x"] + 2, y=graph["screens"][0]["y"])
        status, _, body = self.save(flow_id, 1, graph)
        self.assertEqual((status, body["error"]["code"]), (422, "invalid_graph"))
        self.assertTrue(any("overlap" in d["message"].lower() for d in body["error"]["details"]))
        status, _, flow = self.server.request("GET", f"/api/v1/flows/{flow_id}")
        self.assertEqual(flow["revision"], 1)

    def test_a3_delete_with_incident_edges_saves_in_one_revision(self):
        flow_id, _ = self.create()
        status, _, first = self.save(flow_id, 1, demo_graph())
        self.assertEqual(status, 201)
        edited = clone(demo_graph())
        removed = uid("a", 1)  # the start screen
        edited["screens"] = [s for s in edited["screens"] if s["id"] != removed]
        edited["transitions"] = [t for t in edited["transitions"] if removed not in (t["source"], t["target"])]
        edited["startId"] = None
        status, _, second = self.save(flow_id, 2, edited)
        self.assertEqual((status, second["commitVersion"]), (201, 3))
        graph = second["graph"]
        self.assertIsNone(graph["startId"])
        self.assertEqual(len(graph["screens"]), 7)
        self.assertEqual(len(graph["transitions"]), 6)

    def test_conflict_response_reports_latest_revision(self):
        flow_id, _ = self.create()
        self.save(flow_id, 1, small_graph(title="Tab A"))
        status, _, body = self.save(flow_id, 1, small_graph(title="Tab B"))
        self.assertEqual((status, body["error"]["code"]), (409, "version_conflict"))
        self.assertEqual(body["error"]["details"]["latest"]["version"], 2)

    def test_replay_after_lost_response(self):
        flow_id, _ = self.create()
        request_id = new_id()
        status, _, first = self.save(flow_id, 1, small_graph(title="Tab A"), request_id)
        self.assertEqual(status, 201)
        self.save(flow_id, 2, small_graph(title="Newer"))
        status, _, replay = self.save(flow_id, 1, small_graph(title="Tab A"), request_id)
        self.assertEqual(status, 200)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["commitVersion"], 2)
        self.assertEqual(replay["head"]["version"], 3)

    def test_unsupported_operation_and_unknown_keys(self):
        flow_id, _ = self.create()
        status, _, body = self.server.request(
            "POST", f"/api/v1/flows/{flow_id}/revisions",
            {"requestId": new_id(), "baseVersion": 1, "op": "restore", "graph": small_graph()},
        )
        self.assertEqual((status, body["error"]["code"]), (422, "invalid_request"))

    def test_revision_history_routes(self):
        flow_id, created = self.create()
        self.save(flow_id, 1, small_graph(title="Second"))
        status, _, history = self.server.request("GET", f"/api/v1/flows/{flow_id}/revisions")
        self.assertEqual([r["version"] for r in history["revisions"]], [1, 2])
        status, _, rev1 = self.server.request("GET", f"/api/v1/flows/{flow_id}/revisions/1")
        self.assertEqual(rev1["graph"], created["graph"])
        for bad in ["0", "3", "abc"]:
            status, _, _ = self.server.request("GET", f"/api/v1/flows/{flow_id}/revisions/{bad}")
            self.assertEqual(status, 404, bad)

    def test_user_text_is_stored_verbatim_and_returned_as_json(self):
        flow_id, _ = self.create()
        graph = small_graph(title="<img src=x onerror=alert(1)>")
        graph["screens"][0]["label"] = "<script>alert('x')</script> & \"quotes\""
        status, resp, saved = self.save(flow_id, 1, graph)
        self.assertEqual(status, 201)
        self.assertIn("application/json", resp.getheader("Content-Type"))
        self.assertEqual(saved["graph"]["title"], "<img src=x onerror=alert(1)>")


if __name__ == "__main__":
    unittest.main()
