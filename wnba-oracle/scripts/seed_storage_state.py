"""Materialize the Playwright storage_state.json from a base64+gzip env var.

The cron container reads `REALSPORTS_STORAGE_STATE_B64GZ` from the process
environment and writes `scraper/storage_state.json` before Playwright starts.
The derived session is written atomically with mode 0600.

If the env var is empty, the script no-ops with exit 0. An invalid configured
payload fails closed because scripted Real Sports login is not a recovery path.
"""

from __future__ import annotations

import base64
import gzip
import json
import os
import pathlib
import sys
import tempfile


def main() -> int:
    b64 = os.environ.get("REALSPORTS_STORAGE_STATE_B64GZ", "").strip()
    target = pathlib.Path(__file__).resolve().parents[1] / "scraper" / "storage_state.json"
    if not b64:
        print("seed_storage_state: derived session is not configured")
        return 0
    try:
        raw = gzip.decompress(base64.b64decode(b64, validate=True))
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get("origins"), list):
            raise ValueError("invalid storage-state structure")
    except (ValueError, OSError, json.JSONDecodeError):
        print("seed_storage_state: configured derived session is invalid", file=sys.stderr)
        return 78

    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    target.parent.chmod(0o700)
    temp_name: str | None = None
    try:
        descriptor, temp_name = tempfile.mkstemp(prefix=".storage-state-", dir=target.parent)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, target)
        target.chmod(0o600)
    finally:
        if temp_name is not None:
            pathlib.Path(temp_name).unlink(missing_ok=True)
    print("seed_storage_state: derived session materialized with mode 0600")
    return 0


if __name__ == "__main__":
    sys.exit(main())
