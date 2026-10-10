---
id: slack-sre-gateway-timeouts
title: #sre thread: api-gateway 502 vs 504 and route timeouts
url: https://acmepay.slack.com/archives/C03SRE/p1720000000
author: Rahul Iyer
updated_at: 2026-07-22
acl: sre
channel: sre
---
**Rahul Iyer:** Reminder: api-gateway route timeout for /v1/payments is 3s. If payments-api is slower than that, Envoy returns 504, not 502. 502 means the upstream reset or failed fast, e.g. a crash loop, a client-side timeout inside payments-api, or a TLS failure.
**Priya Sharma:** Good distinction. So for 502s check pod restarts, downstream timeouts and TLS errors first; for 504s check gateway latency.
