---
id: slack-inc-payments-2026-08-14
title: #inc-payments-2026-08-14 thread: 502s after payments-api v2.38 deploy
url: https://acmepay.slack.com/archives/C07INC0814
author: Alex Chen
updated_at: 2026-08-14
acl: engineering
channel: inc-payments-2026-08-14
---
**Priya Sharma (10:02):** payments-api 502 rate at 8% since 09:50. Deploy v2.38 went out at 09:41.
**Alex Chen (10:04):** v2.38 included a config change, DB_POOL_MAX went from 50 to 10 by mistake (typo in the Helm values).
**Priya Sharma (10:05):** Seeing `pool exhausted` in logs. Rolling back with `deployctl rollback payments-api --to v2.37`.
**Priya Sharma (10:14):** Error rate back to 0.1%. Deploys frozen 24h.
**Alex Chen (10:30):** Lesson: when 502s follow a deploy, roll back first and debug after. Took us 9 minutes, could have been 3. Ticket INC-431 filed.
