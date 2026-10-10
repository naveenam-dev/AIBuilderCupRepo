---
id: slack-payments-eng-ledger-flag
title: #payments-eng thread: ledger_async_writes flag causing timeouts
url: https://acmepay.slack.com/archives/C05PAYENG/p1726000000
author: Sofia Martins
updated_at: 2026-09-10
acl: engineering
channel: payments-eng
---
**Sofia Martins:** Heads-up, when `ledger_async_writes` is enabled during peak, the ledger queue consumer falls behind and p99 jumps to ~3s. payments-api then hits its 2s timeout and the gateway serves 502s.
**Alex Chen:** Should we just raise the payments-api timeout?
**Sofia Martins:** No, that only moves the problem. Fix is in PAY-1287 (batching in the consumer). Until then: if you see 502s with ledger p99 > 2s, flip the flag off: `flagctl set ledger_async_writes false --env prod`. Takes effect in ~1 minute.
**Marcus Okafor:** Added to the ledger runbook. Please page #ledger-oncall when you flip it so they can drain the queue.
