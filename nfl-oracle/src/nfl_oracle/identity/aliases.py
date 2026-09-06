"""Alias / dedup reconciliation for Real-primary identity maps (offline).

Merges external id aliases (gsis, espn, sleeper, etc.) and reports display-name
and *normalized*-name collisions beyond naive first+last composition. Does not
auto-merge distinct Real ids (unsafe without human review). Observation only.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from nfl_oracle.identity.map import IdentityMap, IdentityRecord

_SUFFIX_RE = re.compile(
    r"\b(jr\.?|sr\.?|ii|iii|iv|v|vi|vii|viii|ix|x)\b\.?",
    re.IGNORECASE,
)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")
_WS_RE = re.compile(r"\s+")

# Common nickname ↔ formal first-name groups (offline stub; not exhaustive).
_NICKNAME_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"robert", "bob", "bobby", "rob", "robbie"}),
    frozenset({"william", "will", "bill", "billy", "liam"}),
    frozenset({"richard", "rick", "ricky", "dick", "rich"}),
    frozenset({"michael", "mike", "mikey"}),
    frozenset({"james", "jim", "jimmy", "jamie"}),
    frozenset({"john", "jack", "johnny", "jon"}),
    frozenset({"joseph", "joe", "joey"}),
    frozenset({"thomas", "tom", "tommy"}),
    frozenset({"christopher", "chris", "kit"}),
    frozenset({"alexander", "alex", "xander"}),
    frozenset({"benjamin", "ben", "benny"}),
    frozenset({"anthony", "tony"}),
    frozenset({"andrew", "andy", "drew"}),
    frozenset({"matthew", "matt"}),
    frozenset({"joshua", "josh"}),
    frozenset({"nicholas", "nick", "nicky"}),
    frozenset({"jonathan", "jon", "johnny"}),
    frozenset({"charles", "charlie", "chuck"}),
    frozenset({"edward", "ed", "eddie", "ted", "teddy"}),
    frozenset({"stephen", "steven", "steve"}),
    frozenset({"patrick", "pat", "paddy"}),
    frozenset({"timothy", "tim", "timmy"}),
    frozenset({"gregory", "greg"}),
    frozenset({"ronald", "ron", "ronnie"}),
    frozenset({"lawrence", "larry", "lorenzo"}),
    frozenset({"samuel", "sam", "sammy"}),
    frozenset({"daniel", "dan", "danny"}),
    frozenset({"david", "dave", "davey"}),
)


def normalize_alias_key(namespace: str, value: str) -> str:
    return f"{namespace.strip().lower()}:{value.strip().lower()}"


def normalize_display_name(name: str | None) -> str | None:
    """Normalize a display name beyond first+last composition.

    Strips generational suffixes (Jr/Sr/II/III/…), punctuation, and collapses
    whitespace. Used for collision detection — does not rewrite stored names.
    """

    if not name:
        return None
    text = name.strip().lower()
    text = _SUFFIX_RE.sub(" ", text)
    text = _NON_ALNUM_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text or None


def _first_last(normalized: str) -> tuple[str | None, str | None]:
    parts = normalized.split()
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[-1]


def _nickname_canonical(first: str | None) -> str | None:
    if not first:
        return None
    for group in _NICKNAME_GROUPS:
        if first in group:
            return sorted(group)[0]
    return first


def name_match_keys(display_name: str | None) -> tuple[str, ...]:
    """Keys for soft matching beyond exact first+last equality.

    Includes:
    - full normalized name
    - last|first
    - last|nickname_canonical_first (Bob↔Robert)
    - last|first_initial
    """

    normalized = normalize_display_name(display_name)
    if not normalized:
        return ()
    first, last = _first_last(normalized)
    keys: list[str] = [f"full:{normalized}"]
    if last and first:
        keys.append(f"last_first:{last}|{first}")
        canon = _nickname_canonical(first)
        if canon:
            keys.append(f"last_nick:{last}|{canon}")
        keys.append(f"last_initial:{last}|{first[0]}")
    elif last:
        keys.append(f"last_only:{last}")
    elif first:
        keys.append(f"first_only:{first}")
    # Deduplicate while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for key in keys:
        if key not in seen:
            seen.add(key)
            out.append(key)
    return tuple(out)


def merge_external_ids(*maps: dict[str, str]) -> dict[str, str]:
    """Last-write-wins merge of alias namespaces → external ids."""

    out: dict[str, str] = {}
    for m in maps:
        for key, val in m.items():
            ns = str(key).strip()
            vv = str(val).strip()
            if ns and vv:
                out[ns] = vv
    return out


def upsert_with_aliases(
    identity: IdentityMap,
    record: IdentityRecord,
    *,
    prefer_existing_name: bool = True,
) -> IdentityRecord:
    """Upsert record, merging external_ids with any existing row."""

    existing = identity.get(record.real_player_id)
    if existing is None:
        identity.upsert(record)
        return record
    merged_ids = merge_external_ids(existing.external_ids, record.external_ids)
    display: str | None
    if prefer_existing_name and existing.display_name:
        display = existing.display_name
    else:
        display = record.display_name or existing.display_name
    position = existing.position or record.position
    team_id = existing.team_id if existing.team_id is not None else record.team_id
    merged = IdentityRecord(
        real_player_id=record.real_player_id,
        display_name=display,
        position=position,
        team_id=team_id,
        external_ids=merged_ids,
    )
    identity.upsert(merged)
    return merged


def reconcile_alias_collisions(identity: IdentityMap) -> dict[str, Any]:
    """Report alias / display-name / normalized-name collisions across Real ids.

    Does not auto-merge distinct Real ids (unsafe without human review).
    """

    by_alias: dict[str, list[int]] = defaultdict(list)
    by_name: dict[str, list[int]] = defaultdict(list)
    by_normalized: dict[str, list[int]] = defaultdict(list)
    by_soft_key: dict[str, list[int]] = defaultdict(list)
    n_with_alias = 0
    for pid in identity.player_ids():
        rec = identity.get(pid)
        if rec is None:
            continue
        if rec.external_ids:
            n_with_alias += 1
        if rec.display_name:
            by_name[rec.display_name.strip().lower()].append(pid)
            normalized = normalize_display_name(rec.display_name)
            if normalized:
                by_normalized[normalized].append(pid)
            for key in name_match_keys(rec.display_name):
                # Soft keys that are too coarse (last_initial alone) still useful
                # for review when they collide across distinct Real ids.
                by_soft_key[key].append(pid)
        for ns, val in rec.external_ids.items():
            by_alias[normalize_alias_key(ns, val)].append(pid)

    alias_collisions = {k: v for k, v in sorted(by_alias.items()) if len(set(v)) > 1}
    name_collisions = {k: v for k, v in sorted(by_name.items()) if len(set(v)) > 1}
    normalized_collisions = {k: v for k, v in sorted(by_normalized.items()) if len(set(v)) > 1}
    # Soft key collisions: only report last_nick / last_first / full — skip
    # last_initial (too many false positives at roster scale).
    soft_collisions = {
        k: v
        for k, v in sorted(by_soft_key.items())
        if len(set(v)) > 1
        and (k.startswith("full:") or k.startswith("last_first:") or k.startswith("last_nick:"))
    }
    return {
        "contest_entry": False,
        "observation_only": True,
        "n_identities": len(identity),
        "n_with_external_alias": n_with_alias,
        "alias_collision_count": len(alias_collisions),
        "display_name_collision_count": len(name_collisions),
        "normalized_name_collision_count": len(normalized_collisions),
        "soft_name_collision_count": len(soft_collisions),
        "alias_collisions": {k: sorted(set(v)) for k, v in alias_collisions.items()},
        "display_name_collisions": {k: sorted(set(v)) for k, v in name_collisions.items()},
        "normalized_name_collisions": {k: sorted(set(v)) for k, v in normalized_collisions.items()},
        "soft_name_collisions": {k: sorted(set(v)) for k, v in soft_collisions.items()},
    }


def suggest_dedup_candidates(identity: IdentityMap) -> list[dict[str, Any]]:
    """Human-review candidates that share an external id or soft name key.

    Never merges — observation / research only.
    """

    report = reconcile_alias_collisions(identity)
    candidates: list[dict[str, Any]] = []
    for key, pids in report["alias_collisions"].items():
        candidates.append(
            {
                "kind": "external_alias",
                "key": key,
                "real_player_ids": pids,
                "auto_merge": False,
            }
        )
    for key, pids in report["normalized_name_collisions"].items():
        candidates.append(
            {
                "kind": "normalized_display_name",
                "key": key,
                "real_player_ids": pids,
                "auto_merge": False,
            }
        )
    for key, pids in report["soft_name_collisions"].items():
        # Skip if already covered by normalized full collision of same set.
        candidates.append(
            {
                "kind": "soft_name",
                "key": key,
                "real_player_ids": pids,
                "auto_merge": False,
            }
        )
    return candidates


def apply_alias_table(identity: IdentityMap, rows: list[dict[str, Any]]) -> int:
    """Apply offline alias rows. Returns number of rows applied."""

    applied = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        pid_raw = row.get("real_player_id") or row.get("playerId") or row.get("id")
        if pid_raw is None:
            continue
        try:
            pid = int(pid_raw)
        except (TypeError, ValueError):
            continue
        ext_raw = row.get("external_ids") or {}
        ext: dict[str, str] = {}
        if isinstance(ext_raw, dict):
            ext = {str(k): str(v) for k, v in ext_raw.items() if v is not None}
        for flat_key, ns in (
            ("gsis_id", "gsis"),
            ("espn_id", "espn"),
            ("sleeper_id", "sleeper"),
            ("pfr_id", "pfr"),
        ):
            if row.get(flat_key):
                ext[ns] = str(row[flat_key])
        existing = identity.get(pid)
        team_id = existing.team_id if existing is not None else None
        if row.get("team_id") is not None:
            try:
                team_id = int(row["team_id"])
            except (TypeError, ValueError):
                pass
        display = str(row["display_name"]) if row.get("display_name") else None
        position = str(row["position"]) if row.get("position") else None
        if existing is not None:
            display = display or existing.display_name
            position = position or existing.position
            ext = merge_external_ids(existing.external_ids, ext)
        record = IdentityRecord(
            real_player_id=pid,
            display_name=display,
            position=position,
            team_id=team_id,
            external_ids=ext,
        )
        upsert_with_aliases(identity, record)
        applied += 1
    return applied
