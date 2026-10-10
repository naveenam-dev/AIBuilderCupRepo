---
id: conf-severity-levels
title: Incident severity levels
url: https://acmepay.atlassian.net/wiki/spaces/OPS/pages/10/severity
author: Dana Whitfield
updated_at: 2026-01-15
acl: all
---
# Incident severity levels

- **Sev1** - Customer-facing outage of checkout or payments, or data integrity risk. Exec notification within 15 minutes. All hands.
- **Sev2** - Degraded customer experience (elevated errors > 2%, latency SLO breach). On-call owns; team lead informed.
- **Sev3** - Internal-only impact or minor degradation. Handle in business hours.

Anyone who suspects an incident should page the SRE on-call through `/page sre` in chat. Contractors and non-engineers must not attempt mitigation themselves; they should page on-call and share what they observed.
