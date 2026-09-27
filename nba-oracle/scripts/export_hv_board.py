"""NBA HV board export stub (issue #526).

NBA has no Real Sports contest / draftStats ingest yet. Fail closed until a
sport-owned scrape path exists. Durable layout is defined in
``oracle_core.hv_board_corpus``.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "export_hv_board: FAIL_CLOSED nba-oracle has no HV / draftStats ingest yet. "
        "Scaffold only. Refs #526.",
        file=sys.stderr,
    )
    return 78


if __name__ == "__main__":
    raise SystemExit(main())
