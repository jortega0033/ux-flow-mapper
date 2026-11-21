import unittest

from flow_mapper.graph import GraphError, default_scenario_id, empty_graph, validate_graph
from tests.support import clone, demo_graph, new_id, small_graph, uid


def paths(err):
    return [d["path"] for d in err.exception.details]


class ValidateGraphTests(unittest.TestCase):
    def test_demo_fixture_is_valid_and_normalized(self):
        g = validate_graph(demo_graph())
        self.assertEqual(list(g), ["schemaVersion", "title", "startId", "scenarios", "screens", "transitions"])
        self.assertEqual([s["id"] for s in g["screens"]], sorted(s["id"] for s in g["screens"]))
        self.assertEqual(len(g["screens"]), 8)
        self.assertEqual(len(g["transitions"]), 7)

    def test_normalization_is_idempotent_and_order_independent(self):
        g = demo_graph()
        shuffled = clone(g)
        shuffled["screens"].reverse()
        shuffled["transitions"].reverse()
        self.assertEqual(validate_graph(g), validate_graph(shuffled))
        once = validate_graph(g)
        self.assertEqual(validate_graph(clone(once)), once)

    def test_labels_are_trimmed_and_nfc_normalized(self):
        g = small_graph(title="  Café flow  ")
        out = validate_graph(g)
        self.assertEqual(out["title"], "Café flow")

    def test_label_length_counts_code_points(self):
        g = small_graph()
        g["screens"][0]["label"] = "\U0001F600" * 80
        validate_graph(g)
        g["screens"][0]["label"] = "\U0001F600" * 81
        with self.assertRaises(GraphError) as err:
            validate_graph(g)
        self.assertIn("screens[0].label", paths(err))

    def test_control_characters_and_blank_labels_rejected(self):
        for bad in ["", "   ", "two\nlines", "tab\there", "nul\x00"]:
            g = small_graph()
            g["screens"][0]["label"] = bad
            with self.assertRaises(GraphError, msg=repr(bad)):
                validate_graph(g)

    def test_overlap_rejected_but_touching_allowed(self):
        g = small_graph()
        a, b = g["screens"][0], g["screens"][1]
        a["x"], a["y"], b["x"], b["y"] = 10, 10, 15, 12
        with self.assertRaises(GraphError):
            validate_graph(g)
        b["x"], b["y"] = 16, 10  # touches horizontally (distance 6)
        validate_graph(g)
        b["x"], b["y"] = 10, 13  # touches vertically (distance 3)
        validate_graph(g)
        b["x"], b["y"] = 10, 12  # one row of overlap
        with self.assertRaises(GraphError):
            validate_graph(g)

    def test_grid_bounds(self):
        for x, y, ok in [(94, 67, True), (95, 0, False), (0, 68, False), (-1, 0, False)]:
            g = small_graph()
            g["screens"][1].update(x=x, y=y)
            if ok:
                validate_graph(g)
            else:
                with self.assertRaises(GraphError, msg=(x, y)):
                    validate_graph(g)

    def test_boolean_and_float_coordinates_rejected(self):
        for bad in [True, 1.0, "3"]:
            g = small_graph()
            g["screens"][0]["x"] = bad
            with self.assertRaises(GraphError, msg=repr(bad)):
                validate_graph(g)

    def test_dangling_endpoints_and_start(self):
        g = small_graph()
        g["transitions"][0]["target"] = uid("a", 8)
        with self.assertRaises(GraphError) as err:
            validate_graph(g)
        self.assertIn("transitions[0].target", paths(err))
        g = small_graph()
        g["startId"] = uid("a", 8)
        with self.assertRaises(GraphError) as err:
            validate_graph(g)
        self.assertIn("startId", paths(err))

    def test_start_may_be_null(self):
        g = small_graph()
        g["startId"] = None
        self.assertIsNone(validate_graph(g)["startId"])

    def test_exit_rules(self):
        g = demo_graph()
        g["startId"] = uid("a", 3)  # success exit
        with self.assertRaises(GraphError):
            validate_graph(g)
        g = small_graph()
        g["screens"][1]["kind"] = "success_exit"
        g["transitions"].append(
            {"id": uid("b", 2), "source": uid("a", 2), "target": uid("a", 1), "label": "Back", "enabledIn": None}
        )
        with self.assertRaises(GraphError):
            validate_graph(g)

    def test_self_transition_allowed_duplicate_pair_rejected(self):
        g = small_graph()
        loop = {"id": uid("b", 2), "source": uid("a", 1), "target": uid("a", 1), "label": "Refresh", "enabledIn": None}
        g["transitions"].append(loop)
        validate_graph(g)
        dup = dict(loop, id=uid("b", 3), label="Again")
        g["transitions"].append(dup)
        with self.assertRaises(GraphError):
            validate_graph(g)

    def test_enabled_in_rules(self):
        for bad in [[], [uid("c", 9)], [uid("c", 1), uid("c", 1)], "all"]:
            g = demo_graph()
            g["transitions"][2]["enabledIn"] = bad
            with self.assertRaises(GraphError, msg=repr(bad)):
                validate_graph(g)

    def test_scenario_labels_unique_after_casefold(self):
        g = demo_graph()
        g["scenarios"][1]["label"] = "ONLINE"
        with self.assertRaises(GraphError):
            validate_graph(g)

    def test_scenario_count_limits(self):
        g = small_graph()
        g["scenarios"] = []
        with self.assertRaises(GraphError):
            validate_graph(g)
        g["scenarios"] = [{"id": uid("c", i), "label": f"S{i}"} for i in range(1, 10)]
        with self.assertRaises(GraphError):
            validate_graph(g)

    def test_unknown_keys_and_versions_rejected(self):
        g = small_graph()
        g["extra"] = 1
        with self.assertRaises(GraphError):
            validate_graph(g)
        g = small_graph()
        g["schemaVersion"] = 2
        with self.assertRaises(GraphError):
            validate_graph(g)
        g = small_graph()
        g["screens"][0]["color"] = "red"
        with self.assertRaises(GraphError):
            validate_graph(g)

    def test_non_object_rejected(self):
        for bad in [None, [], "x", 3]:
            with self.assertRaises(GraphError):
                validate_graph(bad)

    def test_ids_must_be_lowercase_uuid_and_unique(self):
        g = small_graph()
        g["screens"][0]["id"] = g["screens"][0]["id"].upper().replace("0000", "AAAA")
        with self.assertRaises(GraphError):
            validate_graph(g)
        g = small_graph()
        g["screens"][1]["id"] = g["screens"][0]["id"]
        with self.assertRaises(GraphError):
            validate_graph(g)

    def test_screen_limit(self):
        g = small_graph()
        g["screens"] = []
        g["transitions"] = []
        g["startId"] = None
        for i in range(81):
            g["screens"].append(
                {"id": "00000000-0000-4000-8000-%012x" % (i + 1), "label": f"S{i}", "kind": "screen",
                 "x": (i % 15) * 6, "y": (i // 15) * 3}
            )
        with self.assertRaises(GraphError):
            validate_graph(g)
        g["screens"].pop()
        validate_graph(g)

    def test_empty_graph_has_deterministic_default_scenario(self):
        flow_id = new_id()
        g = empty_graph(flow_id, " New flow ")
        self.assertEqual(g["title"], "New flow")
        self.assertIsNone(g["startId"])
        self.assertEqual(g["scenarios"], [{"id": default_scenario_id(flow_id), "label": "Default"}])
        self.assertEqual(empty_graph(flow_id, "New flow"), g)
        self.assertEqual(validate_graph(clone(g)), g)


if __name__ == "__main__":
    unittest.main()
