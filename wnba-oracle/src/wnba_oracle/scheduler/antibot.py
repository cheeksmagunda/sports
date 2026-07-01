"""Anti-bot timing primitives.

Adapted from the MLB Oracle precedent. The targeting envelopes are identical
because the upstream platform (Real Sports) is the same.

- Truncated Gaussian inter-arrival (mean 5.0s, SD 1.5s, [1.0, 12.0]) for
  per-call delays.
- Full Jitter backoff (Marc Brooker, AWS) on 429/503: base 1s, cap 60s,
  uniform[0, capped] delay per retry, honor Retry-After.
- BLAKE2b daily seed when callers need a deterministic-per-slate shuffle.
"""

from __future__ import annotations

import asyncio
import random
import time as _time
from collections.abc import Sequence
from typing import TypeVar

from scipy.stats import truncnorm

T = TypeVar("T")


def truncated_gaussian_delay(
    rng: random.Random | None = None,
    *,
    mean: float = 5.0,
    sd: float = 1.5,
    lo: float = 1.0,
    hi: float = 12.0,
) -> float:
    if rng is None:
        rng = random.Random()
    a, b = (lo - mean) / sd, (hi - mean) / sd
    rv = truncnorm(a, b, loc=mean, scale=sd)
    return float(rv.rvs(random_state=rng.randint(0, 2**32 - 1)))


async def asleep_truncated_gaussian(rng: random.Random | None = None) -> None:
    await asyncio.sleep(truncated_gaussian_delay(rng))


def sleep_truncated_gaussian(rng: random.Random | None = None) -> None:
    _time.sleep(truncated_gaussian_delay(rng))


def full_jitter_backoff(attempt: int, *, cap: float = 60.0, base: float = 1.0) -> float:
    capped = min(cap, base * (2**attempt))
    return random.uniform(0.0, capped)


def shuffle_order(items: Sequence[T], rng: random.Random) -> list[T]:
    out = list(items)
    rng.shuffle(out)
    return out
