---
id: conf-postmortem-2026-03-mtls
title: [RESTRICTED] Postmortem: payments-api 502s from expired mTLS certificate (March 2026)
url: https://acmepay.atlassian.net/wiki/spaces/SEC/pages/77/pm-mtls
author: Rahul Iyer
updated_at: 2026-03-30
acl: sre, security
---
# Postmortem: payments-api 502s caused by expired mTLS client certificate

**Restricted: SRE and Security only** (contains details of internal PKI).

## Summary
On 2026-03-18, payments-api returned 502s for 47 minutes. Its mTLS client certificate for ledger-service had expired because automated rotation in Vault (`pki/acme-int-ca/issue/payments-api`) failed silently after a policy change.

## Detection signal to remember
TLS handshake errors (`x509: certificate has expired`) in payments-api logs while ledger-service itself looked healthy. Latency was normal; requests failed fast.

## Mitigation
`certctl renew payments-api --target ledger-service` followed by a rolling restart. Check `certctl status payments-api` during any 502 incident where ledger-service is healthy.

## Action items
SEC-77: alert on certificates expiring within 7 days (in progress).
