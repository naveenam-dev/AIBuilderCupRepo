---
id: conf-deploy-rollback
title: Deploy rollback procedure
url: https://acmepay.atlassian.net/wiki/spaces/ENG/pages/2040/deploy-rollback
author: Marcus Okafor
updated_at: 2026-06-02
acl: engineering
---
# Deploy rollback procedure

Rollbacks are always safe for stateless services (payments-api, api-gateway, fraud-scorer). For ledger-service, check with the Ledger team first because schema migrations may not be backward compatible.

## Steps
1. Find the previous good release: `deployctl history <service> --limit 5`.
2. Roll back: `deployctl rollback <service> --to <version> --reason "<incident link>"`.
3. Watch the error rate for 10 minutes. Canary traffic shifts 10% -> 50% -> 100% automatically.
4. Freeze further deploys of the service: `deployctl freeze <service> --hours 24`.
5. Record the rollback in the incident ticket.

Only engineers in the `deployer` group can run rollbacks. On-call SREs are always members.
