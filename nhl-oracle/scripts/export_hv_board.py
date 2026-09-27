"""NHL HV board export stub (issue #526).

NHL uses contest draftStats for contract/boost audit only; there is no durable
HV board corpus path yet. Fail closed. Layout contract:
``oracle_core.hv_board_corpus``.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "export_hv_board: FAIL_CLOSED nhl-oracle has no durable HV board corpus yet "
        "(draftStats used for contract audit only). Scaffold only. Refs #526.",
        file=sys.stderr,
    )
    return 78


if __name__ == "__main__":
    raise SystemExit(main())
