import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "flow_mapper", "static")

REQUIRED_NAMES = [
    "New flow title", "Add flow", "Create demo flow", "Flow list", "Flow title", "Add screen", "Screen list",
    "Screen label", "Screen kind", "Move left", "Move right", "Move up", "Move down", "Start screen",
    "Remove screen", "Transition source", "Transition target", "Transition label", "Add transition",
    "Transition list", "Save", "Flow canvas", "Cancel",
]


def read_static():
    out = {}
    for name in sorted(os.listdir(STATIC)):
        path = os.path.join(STATIC, name)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                out[name] = fh.read()
    return out


class StaticAssetLintTests(unittest.TestCase):
    """Cheap structural checks that hold regardless of a browser being available."""

    def setUp(self):
        self.files = read_static()

    def test_expected_entry_files_exist(self):
        for name in ["index.html", "style.css", "app.js"]:
            self.assertIn(name, self.files)

    def test_no_external_urls(self):
        allowed = {"http://www.w3.org/2000/svg"}
        for name, text in self.files.items():
            for url in re.findall(r"https?://[^\s\"'`)<>]+", text):
                self.assertIn(url, allowed, f"{name} references {url}")

    def test_no_inline_script_style_or_handlers(self):
        html = self.files["index.html"]
        for match in re.finditer(r"<script\b([^>]*)>(.*?)</script>", html, re.S | re.I):
            self.assertIn("src=", match.group(1))
            self.assertEqual(match.group(2).strip(), "")
        self.assertNotRegex(html, r"<style\b")
        for name, text in self.files.items():
            if name.endswith(".html"):
                self.assertNotRegex(text, r"\sstyle\s*=", name)
                self.assertNotRegex(text, r"\son[a-z]+\s*=", name)
            if name.endswith(".js"):
                self.assertNotRegex(text, r"setAttribute\(\s*['\"]style['\"]", name)

    def test_user_text_is_never_assigned_through_html_sinks(self):
        for name, text in self.files.items():
            if name.endswith(".js"):
                for sink in ["innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("]:
                    self.assertNotIn(sink, text, f"{name} uses {sink}")

    def test_required_accessible_names_are_present(self):
        combined = "\n".join(self.files.values())
        for name in REQUIRED_NAMES:
            self.assertIn(name, combined, name)

    def test_live_and_error_regions_declared(self):
        html = self.files["index.html"]
        self.assertIn('id="live"', html)
        self.assertIn('id="errors"', html)
        self.assertIn('id="save-state"', html)


# Ignore any system proxy so loopback requests stay on loopback.
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class CliTests(unittest.TestCase):
    def start(self, data_dir, port):
        proc = subprocess.Popen(
            [sys.executable, "-m", "flow_mapper", "--data-dir", data_dir, "--port", str(port)],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.addCleanup(self.stop, proc)
        deadline = time.time() + 15
        url = f"http://127.0.0.1:{port}/api/v1/health"
        while time.time() < deadline:
            if proc.poll() is not None:
                self.fail(f"server exited early: {proc.stderr.read()}")
            try:
                with OPENER.open(url, timeout=1) as resp:
                    if resp.status == 200:
                        return proc
            except OSError:
                time.sleep(0.1)
        self.fail("server did not become ready")

    @staticmethod
    def stop(proc):
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        for stream in (proc.stdout, proc.stderr):
            if stream:
                stream.close()

    def test_cli_serves_from_empty_data_dir_and_creates_database(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)  # registered first, so it runs after the server stops
        data_dir = os.path.join(tmp.name, "nested", "data")
        port = free_port()
        self.start(data_dir, port)
        self.assertTrue(os.path.exists(os.path.join(data_dir, "flow_mapper.sqlite3")))
        with OPENER.open(f"http://127.0.0.1:{port}/api/v1/flows", timeout=5) as resp:
            self.assertEqual(json.loads(resp.read().decode("utf-8")), {"flows": []})

    def test_cli_requires_data_dir(self):
        proc = subprocess.run([sys.executable, "-m", "flow_mapper", "--port", "0"], cwd=ROOT,
                              capture_output=True, text=True, timeout=15)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("--data-dir", proc.stderr)


if __name__ == "__main__":
    unittest.main()
