"""Send locally recorded spans to an OTLP/HTTP endpoint, such as Confident AI.

    CONFIDENT_API_KEY=... python replay_spans.py [--in .eval/default/traces] [--endpoint URL] [--dry-run]

Use this when moving from a local track to Confident AI so your trace history
comes with you. Each line of ``spans-*.jsonl`` is already an OTLP/JSON export
request, so it is posted as-is. Replaying the same files twice sends
duplicates; move replayed files aside afterwards.

Part of eval-skills (Apache-2.0). Standard library only.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_ENDPOINT = os.getenv("CONFIDENT_OTEL_ENDPOINT", "https://otel.confident-ai.com/v1/traces")


def post(endpoint: str, body: bytes, api_key: str, attempts: int = 4) -> None:
    for attempt in range(attempts):
        request = urllib.request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "x-confident-api-key": api_key},
        )
        try:
            with urllib.request.urlopen(request, timeout=30):
                return
        except urllib.error.HTTPError as err:
            if err.code not in (429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise
        except urllib.error.URLError:
            if attempt == attempts - 1:
                raise
        time.sleep(2**attempt)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--in", dest="src", default=".eval/default/traces")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = os.getenv("CONFIDENT_API_KEY", "")
    if not api_key and not args.dry_run:
        sys.exit("Set CONFIDENT_API_KEY first (the user adds it to .env).")

    sent = 0
    for path in sorted(Path(args.src).glob("spans-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            if not args.dry_run:
                post(args.endpoint, line.encode("utf-8"), api_key)
            sent += 1
    verb = "Would send" if args.dry_run else "Sent"
    print(f"{verb} {sent} export batches to {args.endpoint}")


if __name__ == "__main__":
    main()
