---
id: conf-runbook-payments-5xx
title: Runbook: payments-api 5xx / 502 errors
url: https://acmepay.atlassian.net/wiki/spaces/SRE/pages/1101/payments-api-5xx
author: Priya Sharma
updated_at: 2026-08-20
acl: engineering
---
# Runbook: payments-api 5xx / 502 errors

**Service:** payments-api (owner: Payments team). **Pager policy:** Sev2 if error rate > 2% for 5 min, Sev1 if > 10% or checkout fully down.

## 1. Triage (first 5 minutes)
1. Acknowledge the page in PagerDuty and open an incident channel `#inc-payments-<date>`.
2. Check the payments-api dashboard: error rate, p99 latency, and which status codes. 502s come from api-gateway when the payments-api upstream fails.
3. Check whether a deploy happened in the last 60 minutes (`deployctl history payments-api`).

## 2. Decision tree
- **Deploy in the last 30 minutes and error rate rising** -> roll back immediately (see "Deploy rollback procedure"). Do not debug forward during an active incident.
- **ledger-service p99 latency > 2s** -> payments-api times out on synchronous ledger writes. Disable the feature flag `ledger_async_writes` (known issue PAY-1287) and page the Ledger team.
- **DB connection errors in logs (`too many clients`, `pool exhausted`)** -> check `DB_POOL_MAX` in the latest config change. See the incident of 2026-08-14.
- **None of the above** -> escalate to the Payments team secondary on-call.

## 3. Communication
- Sev1/Sev2: post an update in `#incidents` every 30 minutes.
- Sev1: notify `#exec-incidents` within 15 minutes and follow the Customer communications policy.

## 4. After recovery
Create a Jira incident ticket in project INC with timeline, impact and suspected cause; schedule a postmortem within 5 business days.
