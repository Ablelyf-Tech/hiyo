"""Staging-only coordination load harness. Does not generate fake production evidence."""

import argparse
import concurrent.futures
import json
import statistics
import time
import urllib.request
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", required=True)
    p.add_argument(
        "--token-file",
        type=Path,
        required=True,
        help="JSON list of short-lived test-account Firebase ID tokens; never commit this file",
    )
    p.add_argument("--requests", type=int, default=1000)
    p.add_argument("--concurrency", type=int, default=40)
    p.add_argument("--confirm-staging-costs", action="store_true")
    args = p.parse_args()
    if not args.confirm_staging_costs:
        p.error("Explicit staging/load-test cost approval is required")
    if not args.host.startswith("https://"):
        p.error("Use an authorized HTTPS staging service")
    tokens = json.loads(args.token_file.read_text())
    timings = []
    failures = []

    def one(i):
        started = time.monotonic()
        try:
            req = urllib.request.Request(
                args.host.rstrip("/") + "/api/automation/state",
                headers={"Authorization": "Bearer " + tokens[i % len(tokens)]},
            )
            with urllib.request.urlopen(req, timeout=20) as r:
                r.read(1024 * 1024)
                return (time.monotonic() - started) * 1000, r.status
        except Exception:
            return (time.monotonic() - started) * 1000, 0

    with concurrent.futures.ThreadPoolExecutor(args.concurrency) as pool:
        for elapsed, status in pool.map(one, range(args.requests)):
            timings.append(elapsed)
            if status != 200:
                failures.append(status)
    timings.sort()
    print(
        json.dumps(
            {
                "requests": len(timings),
                "concurrency": args.concurrency,
                "failures": len(failures),
                "p50_ms": round(statistics.median(timings), 2),
                "p95_ms": round(timings[int(0.95 * (len(timings) - 1))], 2),
            },
            indent=2,
        )
    )
    raise SystemExit(bool(failures))


if __name__ == "__main__":
    main()
