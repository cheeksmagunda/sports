---
name: redeploy
description: Redeploy a Railway service for this project via GraphQL (rwgql.sh). Use when a service needs a restart or to pick up new env vars.
---

# Redeploy a Railway service

Redeploy $ARGUMENTS (or the service the user named).

Workspace-token CLI mutations do not work; always go through GraphQL:

```bash
scripts/rwgql.sh 'mutation { serviceInstanceDeployV2(serviceId: "SERVICE_ID", environmentId: "d57a759e-e189-439b-a612-bd220ef59c39") }'
```

Service IDs (production env `d57a759e-e189-439b-a612-bd220ef59c39`):

| Service | ID |
|---|---|
| api | `f4750eda-fd6c-432b-b6f5-34254013c271` |
| frontend | `d56dccf4-85b3-4ba0-acaf-58ef0cced58c` |
| cron-job1 | `2e110589-9527-4541-a754-41c4719515ba` |
| cron-job1-late | `2b0cd5aa-8793-45a5-bca0-e81c6d8455ff` |
| cron-job2 | `4a511ed2-10ad-441f-bf9a-3748c1e6b929` |
| cron-dayclose | `606d950d-7d7d-4f5a-a049-b9fa69799169` |
| postgres | `5e827da3-6df6-4349-97ad-a800ece2716d` |
| redis | `bb131bec-4edd-4809-accd-e09e09aacbf6` |

Never redeploy postgres or redis without explicit operator confirmation.
After deploying, confirm the new deployment went live (deployment status via
GraphQL or `railway logs`).
