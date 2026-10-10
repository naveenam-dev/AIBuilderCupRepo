---
id: conf-ledger-runbook
title: ledger-service operations runbook
url: https://acmepay.atlassian.net/wiki/spaces/LED/pages/3300/ledger-runbook
author: Sofia Martins
updated_at: 2026-09-12
acl: engineering
---
# ledger-service operations runbook

ledger-service is the system of record for balances. payments-api calls it synchronously on every capture unless `ledger_async_writes` is enabled, in which case writes go through a queue.

## High latency
- Normal p99 is 250 ms. Above 2 s, upstream callers (payments-api) start timing out at their 2 s client timeout and api-gateway returns 502.
- Most common cause: the async write queue backs up when `ledger_async_writes` is turned on during peak traffic (see PAY-1287). Mitigation: disable the flag with `flagctl set ledger_async_writes false --env prod`.
- Second cause: long-running reconciliation jobs. Check `ledgerctl jobs --running`.

## Escalation
Ledger team primary on-call (PagerDuty schedule "ledger-primary"). Team lead: Sofia Martins.
