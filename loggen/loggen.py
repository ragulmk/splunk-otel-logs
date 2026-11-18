#!/usr/bin/env python3
"""
Realistic JSON log generator for a small e-commerce system.

Services: web-gateway, auth-service, orders-service, payment-service.
Every request shares a trace_id across services so it can be followed end to end.

Incidents can be switched on at runtime by creating a file in the control dir
(see scripts/incident.sh):  payment_outage | brute_force | slow_db
The file contains a Unix timestamp; the incident runs until that time.
"""
import argparse
import json
import os
import random
import sys
import time
import uuid
from datetime import datetime, timezone

PATHS = [
    ("GET", "/api/products", "orders-service", 0.35),
    ("GET", "/api/orders", "orders-service", 0.20),
    ("POST", "/api/orders", "orders-service", 0.10),
    ("POST", "/api/payments", "payment-service", 0.15),
    ("POST", "/api/login", "auth-service", 0.20),
]
USERS = [f"user{n:03d}" for n in range(1, 201)]
CLIENT_IPS = [f"10.20.{random.randint(0, 9)}.{n}" for n in range(1, 120)]
ATTACKER_IPS = ["203.0.113.45", "198.51.100.23"]
PROVIDERS = ["razorpay", "stripe", "paytm"]


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Generator:
    def __init__(self, control_dir):
        self.control_dir = control_dir

    def incident(self, name):
        if not self.control_dir:
            return False
        path = os.path.join(self.control_dir, name)
        try:
            with open(path) as f:
                until = float(f.read().strip() or 0)
        except (FileNotFoundError, ValueError):
            return False
        if time.time() > until:
            try:
                os.remove(path)
            except OSError:
                pass
            return False
        return True

    def request(self):
        """Yield the log lines for one user request (gateway + backend service)."""
        method, path, service, _ = random.choices(PATHS, weights=[p[3] for p in PATHS])[0]
        trace_id = uuid.uuid4().hex
        user = random.choice(USERS)
        ip = random.choice(CLIENT_IPS)
        slow_db = self.incident("slow_db")
        status, level, extra = 200, "INFO", {}
        duration = random.lognormvariate(3.8, 0.5)  # ~45ms median

        if service == "orders-service":
            if slow_db:
                duration += random.uniform(600, 2500)
            msg = "order created" if method == "POST" else "orders fetched"
            if method == "POST":
                status = 201
                extra["order_id"] = random.randint(10000, 99999)
            if random.random() < 0.003:
                status, level, msg = 500, "ERROR", "unexpected error"
                extra["error"] = "NullPointerException in OrderMapper"
            elif duration > 1000:
                level = "WARN"
                extra["db_query_ms"] = int(duration * 0.9)
                msg = "slow database query"

        elif service == "payment-service":
            amount = round(random.uniform(199, 25000), 2)
            extra.update(amount=amount, currency="INR", provider=random.choice(PROVIDERS))
            outage = self.incident("payment_outage")
            if outage and extra["provider"] == "razorpay" and random.random() < 0.8:
                status, level, msg = 502, "ERROR", "payment provider error"
                extra["error"] = "upstream timeout after 5000ms"
                duration = random.uniform(4900, 5100)
            elif random.random() < 0.01:
                status, level, msg = 402, "WARN", "payment declined"
                extra["decline_reason"] = random.choice(["insufficient_funds", "card_expired", "do_not_honor"])
            else:
                msg = "payment captured"

        else:  # auth-service
            if random.random() < 0.05:
                status, level, msg = 401, "WARN", "login failed"
                extra["reason"] = "invalid_password"
            else:
                msg = "login succeeded"
            extra["event"] = "login"
            extra["client_ip"] = ip
            extra["outcome"] = "success" if status == 200 else "failure"

        duration = int(duration)
        yield self._line(service, level, msg, trace_id, user=user, method=method, path=path,
                         status=status, duration_ms=max(1, duration - random.randint(1, 5)), **extra)
        yield self._line("web-gateway", "ERROR" if status >= 500 else "INFO", "request completed", trace_id,
                         method=method, path=path, status=status, duration_ms=duration,
                         client_ip=ip, user=user, user_agent=random.choice(["Mozilla/5.0", "okhttp/4.12", "curl/8.5"]))

    def brute_force(self):
        ip = random.choice(ATTACKER_IPS)
        trace_id = uuid.uuid4().hex
        user = random.choice(["admin", "root", "test", random.choice(USERS)])
        yield self._line("auth-service", "WARN", "login failed", trace_id, user=user, method="POST",
                         path="/api/login", status=401, duration_ms=random.randint(20, 60),
                         client_ip=ip, event="login", outcome="failure", reason="invalid_password")
        yield self._line("web-gateway", "INFO", "request completed", trace_id, method="POST", path="/api/login",
                         status=401, duration_ms=random.randint(25, 70), client_ip=ip, user=user,
                         user_agent="python-requests/2.32")

    @staticmethod
    def _line(service, level, msg, trace_id, **fields):
        return json.dumps({"timestamp": now_iso(), "level": level, "service": service,
                           "msg": msg, "trace_id": trace_id, **fields}, separators=(",", ":"))


class RotatingWriter:
    def __init__(self, path, max_bytes):
        self.path, self.max_bytes = path, max_bytes
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.f = open(path, "a", buffering=1)

    def write(self, line):
        self.f.write(line + "\n")
        if self.f.tell() > self.max_bytes:
            self.f.close()
            os.replace(self.path, self.path + ".1")
            self.f = open(self.path, "a", buffering=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default=os.environ.get("LOG_FILE", "/logs/app.log"),
                    help="file to write, or '-' for stdout")
    ap.add_argument("--rps", type=float, default=float(os.environ.get("RPS", "5")))
    ap.add_argument("--count", type=int, default=0, help="stop after N requests (0 = run forever)")
    ap.add_argument("--control-dir", default=os.environ.get("CONTROL_DIR", "/control"))
    ap.add_argument("--max-bytes", type=int, default=50 * 1024 * 1024)
    args = ap.parse_args()

    gen = Generator(args.control_dir)
    out = sys.stdout if args.output == "-" else RotatingWriter(args.output, args.max_bytes)
    write = (lambda l: print(l, flush=True)) if args.output == "-" else out.write

    sent = 0
    while args.count == 0 or sent < args.count:
        for line in gen.request():
            write(line)
        if gen.incident("brute_force"):
            for _ in range(5):
                for line in gen.brute_force():
                    write(line)
        sent += 1
        if args.count == 0:
            time.sleep(random.expovariate(args.rps))


if __name__ == "__main__":
    main()
