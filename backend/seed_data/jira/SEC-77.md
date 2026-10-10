---
id: jira-SEC-77
title: SEC-77: Alert on internal mTLS certificates expiring within 7 days
url: https://acmepay.atlassian.net/browse/SEC-77
author: Rahul Iyer
updated_at: 2026-09-01
acl: security, sre
status: In Progress
assignee: Rahul Iyer
---
**Type:** Task  **Priority:** High  **Status:** In Progress

Follow-up from the March 2026 mTLS postmortem. Vault PKI rotation for payments-api failed silently. Add alerting for certificates under `pki/acme-int-ca` expiring in < 7 days. Until shipped, SRE should run `certctl status payments-api` during any 502 investigation.
