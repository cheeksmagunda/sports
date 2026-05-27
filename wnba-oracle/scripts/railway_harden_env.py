"""Idempotent Railway env hardening (one-shot).

Best-practice cleanup applied to the production environment:

1. Promote non-secret operational vars (ENV, LOG_LEVEL, PYTHONUNBUFFERED,
   TZ, PAYOUT_REGIME, WNBA_ORACLE_MODEL_ARTIFACT_SHA) to environment-level
   shared variables so they're set once and all services inherit them.

2. Convert hard-coded ``DATABASE_URL`` + ``REDIS_URL`` on api / cron-job1 /
   cron-job2 to service references (``${{Postgres.DATABASE_URL}}``,
   ``${{Redis.REDIS_URL}}``). Credential rotations on the DB / Redis side
   propagate automatically.

3. Convert frontend's ``VITE_API_URL`` to a public-domain reference
   (``https://${{api.RAILWAY_PUBLIC_DOMAIN}}``) so a domain rotation on
   the api auto-rebuilds the frontend bundle.

4. Drop unused secrets from each service so the runtime container does
   not carry credentials it cannot consume:

   * api: REAL_SPORTS_*, REALSPORTS_STORAGE_STATE_B64GZ, WNBA_DEVICE_*,
     ODDS_API_KEY, CONTRARIAN_*, OPTIMIZER_MAX_PER_TEAM, GITHUB_TOKEN,
     RAILWAY_TOKEN.
   * cron-job1: CONTRARIAN_*, OPTIMIZER_MAX_PER_TEAM, GITHUB_TOKEN,
     RAILWAY_TOKEN.
   * cron-job2: REAL_SPORTS_*, REALSPORTS_STORAGE_STATE_B64GZ,
     WNBA_DEVICE_*, ODDS_API_KEY, GITHUB_TOKEN, RAILWAY_TOKEN.
   * After promotion to shared (step 1), the per-service copies of the
     promoted keys are also removed.

Re-runnable: each variableUpsert / variableDelete is idempotent.

Usage:
    set -a && source .env && set +a && python3 scripts/railway_harden_env.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys


PROJECT = "ab83f44c-0bbc-4a58-931c-37d9fbfda73a"
ENV = "d57a759e-e189-439b-a612-bd220ef59c39"

SERVICES = {
    "api":       "f4750eda-fd6c-432b-b6f5-34254013c271",
    "cron-job1": "2e110589-9527-4541-a754-41c4719515ba",
    "cron-job2": "4a511ed2-10ad-441f-bf9a-3748c1e6b929",
    "frontend":  "d56dccf4-85b3-4ba0-acaf-58ef0cced58c",
}

# Operational config promoted to environment-level (shared).
SHARED_KEYS = [
    "ENV",
    "LOG_LEVEL",
    "PYTHONUNBUFFERED",
    "TZ",
    "PAYOUT_REGIME",
    "WNBA_ORACLE_MODEL_ARTIFACT_SHA",
]

# Reference paths.
DATABASE_URL_REF = "${{postgres.DATABASE_URL}}"
REDIS_URL_REF = "${{redis.REDIS_URL}}"
VITE_API_URL_REF = "https://${{api.RAILWAY_PUBLIC_DOMAIN}}"

# Unused per-service vars to delete (after the shared step).
UNUSED_PER_SERVICE: dict[str, list[str]] = {
    "api": [
        "REAL_SPORTS_USERNAME", "REAL_SPORTS_PASSWORD",
        "REALSPORTS_STORAGE_STATE_B64GZ",
        "WNBA_DEVICE_UUID", "WNBA_DEVICE_NAME",
        "ODDS_API_KEY",
        "CONTRARIAN_STRENGTH", "CONTRARIAN_ENABLED",
        "OPTIMIZER_MAX_PER_TEAM",
        "GITHUB_TOKEN", "RAILWAY_TOKEN",
    ],
    "cron-job1": [
        "CONTRARIAN_STRENGTH", "CONTRARIAN_ENABLED",
        "OPTIMIZER_MAX_PER_TEAM",
        "GITHUB_TOKEN", "RAILWAY_TOKEN",
    ],
    "cron-job2": [
        "REAL_SPORTS_USERNAME", "REAL_SPORTS_PASSWORD",
        "REALSPORTS_STORAGE_STATE_B64GZ",
        "WNBA_DEVICE_UUID", "WNBA_DEVICE_NAME",
        "ODDS_API_KEY",
        "GITHUB_TOKEN", "RAILWAY_TOKEN",
    ],
    "frontend": [],
}


def _post(payload: dict) -> dict:
    token = os.environ.get("RAILWAY_TOKEN")
    if not token:
        sys.exit("RAILWAY_TOKEN env var not set; source .env first")
    r = subprocess.run(
        [
            "curl", "-sS",
            "https://backboard.railway.com/graphql/v2",
            "-H", f"Authorization: Bearer {token}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps(payload),
        ],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(r.stdout)
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], indent=2))
    return data["data"]


def read_vars(service_id: str | None = None) -> dict[str, str]:
    """Read env vars at service-scope (service_id given) or env-scope (None)."""
    variables: dict = {"projectId": PROJECT, "environmentId": ENV}
    if service_id:
        variables["serviceId"] = service_id
    query = (
        "query($projectId: String!, $environmentId: String!, $serviceId: String){"
        " variables(projectId: $projectId, environmentId: $environmentId, serviceId: $serviceId) }"
    )
    return _post({"query": query, "variables": variables})["variables"]


def upsert_var(name: str, value: str, service_id: str | None = None) -> None:
    inp: dict = {
        "projectId": PROJECT,
        "environmentId": ENV,
        "name": name,
        "value": value,
    }
    if service_id:
        inp["serviceId"] = service_id
    _post({
        "query": "mutation($input: VariableUpsertInput!){ variableUpsert(input: $input) }",
        "variables": {"input": inp},
    })


def delete_var(name: str, service_id: str | None = None) -> bool:
    inp: dict = {
        "projectId": PROJECT,
        "environmentId": ENV,
        "name": name,
    }
    if service_id:
        inp["serviceId"] = service_id
    try:
        _post({
            "query": "mutation($input: VariableDeleteInput!){ variableDelete(input: $input) }",
            "variables": {"input": inp},
        })
        return True
    except RuntimeError as e:
        # Already absent is fine.
        if "not found" in str(e).lower() or "does not exist" in str(e).lower():
            return False
        raise


def main() -> None:
    print(">>> Step 1: promote shared operational vars to env scope")
    api_vars = read_vars(SERVICES["api"])
    shared_existing = read_vars(service_id=None)
    for key in SHARED_KEYS:
        if key in shared_existing:
            print(f"    {key}: already shared, skipping")
            continue
        # Use the api service's current value as the source of truth, falling
        # back to cron-job2 if absent (e.g. CONTRARIAN_* style — but those
        # aren't in SHARED_KEYS anyway).
        value = api_vars.get(key)
        if value is None:
            value = read_vars(SERVICES["cron-job1"]).get(key)
        if value is None:
            print(f"    {key}: not set on any service, skipping (set manually if needed)")
            continue
        upsert_var(key, value, service_id=None)
        print(f"    {key}: promoted to shared")

    print(">>> Step 2: convert DATABASE_URL + REDIS_URL to service references")
    for svc_name in ("api", "cron-job1", "cron-job2"):
        sid = SERVICES[svc_name]
        cur = read_vars(sid)
        if cur.get("DATABASE_URL") != DATABASE_URL_REF:
            upsert_var("DATABASE_URL", DATABASE_URL_REF, sid)
            print(f"    {svc_name}.DATABASE_URL -> Postgres ref")
        else:
            print(f"    {svc_name}.DATABASE_URL: already a ref")
        if cur.get("REDIS_URL") != REDIS_URL_REF:
            upsert_var("REDIS_URL", REDIS_URL_REF, sid)
            print(f"    {svc_name}.REDIS_URL -> Redis ref")
        else:
            print(f"    {svc_name}.REDIS_URL: already a ref")

    print(">>> Step 3: convert frontend VITE_API_URL to api domain reference")
    fe = read_vars(SERVICES["frontend"])
    if fe.get("VITE_API_URL") != VITE_API_URL_REF:
        upsert_var("VITE_API_URL", VITE_API_URL_REF, SERVICES["frontend"])
        print("    frontend.VITE_API_URL -> api.RAILWAY_PUBLIC_DOMAIN ref")
    else:
        print("    frontend.VITE_API_URL: already a ref")

    print(">>> Step 4: drop per-service copies of newly-shared keys")
    for svc_name, sid in SERVICES.items():
        if svc_name == "frontend":
            continue
        cur = read_vars(sid)
        for key in SHARED_KEYS:
            if key in cur:
                delete_var(key, sid)
                print(f"    {svc_name}.{key}: removed (now inherited from env scope)")

    print(">>> Step 5: drop unused secrets from each service")
    for svc_name, unused in UNUSED_PER_SERVICE.items():
        sid = SERVICES[svc_name]
        cur = read_vars(sid)
        for key in unused:
            if key in cur:
                delete_var(key, sid)
                print(f"    {svc_name}.{key}: deleted (unused at runtime)")

    print(">>> Done. Trigger a redeploy of api / cron services to pick up the new env.")


if __name__ == "__main__":
    main()
