import importlib.util
import tempfile
import threading
import time
import unittest
from pathlib import Path


API_PATH = Path(__file__).with_name("api.py")
spec = importlib.util.spec_from_file_location("palctl_api", API_PATH)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class EnsureLatestImageTests(unittest.TestCase):
    def test_updates_only_the_managed_palworld_image(self):
        with tempfile.TemporaryDirectory() as temp:
            compose = Path(temp) / "compose.yaml"
            compose.write_text(
                "services:\n"
                "  palworld-server:\n"
                "    image: ghcr.io/pocketpairjp/palserver:v1.0.0.100427\n"
                "    container_name: palworld-server\n"
                "  sidecar:\n"
                "    image: example/sidecar:1\n",
                encoding="utf-8",
            )
            original = api.COMPOSE_PATH
            try:
                api.COMPOSE_PATH = compose
                result = api.ensure_latest_image()
            finally:
                api.COMPOSE_PATH = original

            self.assertTrue(result["ok"])
            self.assertTrue(result["changed"])
            content = compose.read_text(encoding="utf-8")
            self.assertIn("image: ghcr.io/pocketpairjp/palserver:latest", content)
            self.assertIn("image: example/sidecar:1", content)


class UpdateJobTests(unittest.TestCase):
    def test_start_returns_before_the_update_workflow_finishes(self):
        workflow_started = threading.Event()
        release_workflow = threading.Event()

        def slow_workflow():
            workflow_started.set()
            release_workflow.wait(timeout=2)
            return {"ok": True, "stage": "complete"}

        started_at = time.monotonic()
        result = api.start_update_job(slow_workflow)
        elapsed = time.monotonic() - started_at

        try:
            self.assertTrue(result["ok"])
            self.assertEqual("running", result["status"])
            self.assertLess(elapsed, 0.25)
            self.assertTrue(workflow_started.wait(timeout=1))
            self.assertEqual("running", api.get_update_state()["status"])
        finally:
            release_workflow.set()

        deadline = time.monotonic() + 1
        while time.monotonic() < deadline and api.get_update_state()["status"] == "running":
            time.sleep(0.01)
        self.assertEqual("complete", api.get_update_state()["status"])


if __name__ == "__main__":
    unittest.main()
