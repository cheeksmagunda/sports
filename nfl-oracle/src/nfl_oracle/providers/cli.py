"""CLI for provider/auth status (no secrets printed)."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from nfl_oracle.providers.auth_status import probe_realsports_auth
from nfl_oracle.providers.five_card import FiveCardProviderStub
from nfl_oracle.strategy.schema import FiveCardAction


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nfl-provider-status")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--preview-ids",
        type=str,
        default="",
        help="optional comma-separated five Real player ids for shadow preview",
    )
    args = parser.parse_args(argv)

    stub = FiveCardProviderStub()
    ready = stub.readiness()
    payload: dict[str, Any] = {
        "provider": ready.to_json_obj(),
        "auth": probe_realsports_auth().to_json_obj(),
    }

    if args.preview_ids.strip():
        parts = [p.strip() for p in args.preview_ids.split(",") if p.strip()]
        if len(parts) != 5:
            print("preview-ids requires exactly five comma-separated ints", file=sys.stderr)
            return 2
        action = FiveCardAction(player_ids=tuple(int(x) for x in parts))  # type: ignore[arg-type]
        payload["shadow_preview"] = stub.shadow_preview(action)

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        auth = payload["auth"]
        print(f"auth_usable={auth['usable']}")
        print(f"storage_state_exists={auth['storage_state_exists']}")
        print(f"provider_status={ready.status.value}")
        print(f"contest_entry={ready.contest_entry}")
        print(f"notes={','.join(auth['notes']) if auth['notes'] else '-'}")
        if "shadow_preview" in payload:
            sp = payload["shadow_preview"]
            print(f"shadow_structurally_valid={sp['structurally_valid']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
