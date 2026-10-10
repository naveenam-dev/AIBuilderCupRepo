---
id: conf-oncall-handbook
title: On-call handbook
url: https://acmepay.atlassian.net/wiki/spaces/SRE/pages/900/oncall-handbook
author: Priya Sharma
updated_at: 2026-07-01
acl: engineering
---
# On-call handbook

- Primary on-call acknowledges pages within 5 minutes; secondary is paged after 10 minutes.
- Every incident gets a Jira ticket in project **INC** with fields: summary, severity, service, impact, timeline.
- Always look for prior incidents and known issues (Jira, #inc-* Slack channels) before debugging from scratch. Most incidents are repeats.
- Hand off at 09:00 local time with a written summary in `#sre-handoff`.
- If you need a service owner and they are in a meeting, page them anyway for Sev1/Sev2.
