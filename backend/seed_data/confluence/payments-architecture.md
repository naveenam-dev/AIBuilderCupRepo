---
id: conf-payments-architecture
title: Payments platform architecture overview
url: https://acmepay.atlassian.net/wiki/spaces/PAY/pages/120/architecture
author: Alex Chen
updated_at: 2026-05-20
acl: engineering
---
# Payments platform architecture

Request path: client -> **api-gateway** -> **payments-api** -> (**fraud-scorer**, **ledger-service**) -> **payments-db** (Postgres).

- api-gateway: Envoy; returns 502 when the upstream resets or fails, and 504 when it exceeds the 3 s route timeout.
- payments-api: Go service, 2 s client timeout towards ledger-service, connection pool to payments-db configured via `DB_POOL_MAX` (default 50).
- fraud-scorer: Python model service; fails open after 300 ms.
- ledger-service: Java; system of record. Calls are mTLS-authenticated using certificates issued by internal CA `acme-int-ca`.
