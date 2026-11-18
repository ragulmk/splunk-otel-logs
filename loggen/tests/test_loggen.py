import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from loggen import Generator  # noqa: E402

REQUIRED = {"timestamp", "level", "service", "msg", "trace_id"}


class LoggenTests(unittest.TestCase):
    def lines(self, gen, n=500):
        return [json.loads(l) for _ in range(n) for l in gen.request()]

    def test_lines_are_valid_json_with_required_fields(self):
        for event in self.lines(Generator(None)):
            self.assertTrue(REQUIRED <= event.keys(), event)
            self.assertIn(event["level"], {"INFO", "WARN", "ERROR"})
            self.assertTrue(event["timestamp"].endswith("Z"))

    def test_trace_id_links_gateway_and_backend(self):
        gen = Generator(None)
        backend, gateway = [json.loads(l) for l in gen.request()]
        self.assertEqual(backend["trace_id"], gateway["trace_id"])
        self.assertEqual(gateway["service"], "web-gateway")

    def test_payment_outage_incident_produces_errors(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "payment_outage"), "w") as f:
                f.write(str(time.time() + 60))
            events = self.lines(Generator(d), 1500)
            errors = [e for e in events if e["service"] == "payment-service" and e["status"] == 502]
            self.assertGreater(len(errors), 10)

    def test_expired_incident_is_ignored_and_removed(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "slow_db")
            with open(path, "w") as f:
                f.write(str(time.time() - 1))
            self.assertFalse(Generator(d).incident("slow_db"))
            self.assertFalse(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
