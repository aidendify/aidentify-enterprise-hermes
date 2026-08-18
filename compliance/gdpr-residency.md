# GDPR & Data Residency — Enterprise Agent Ops

## Why self-hosted matters
Enterprises processing personal data (employee attendance, timesheets, access logs,
daily reports) face GDPR art.5 (lawfulness/minimisation) and data-residency
requirements. Cloud AI tools that egress data to third-country model providers are
the pain point this platform removes.

## How the platform helps
- **Data stays in network:** `LLM_BASE_URL` defaults to an in-network endpoint;
  `ALLOW_EGRESS=false` blocks outbound model/tool calls. Model prompts/answers never
  leave the tenant boundary.
- **Lawful basis support:** the immutable audit log (`core/audit.py`) documents what
  processing happened, when, by whom, and who approved it — evidencing art.5(2)
  accountability and art.30 processing records.
- **Minimisation:** RBAC scopes limit each role to the data it needs; attendance/
  access data is scoped per-user.
- **Data subjects' rights:** stored data is per-user JSON; export/delete are
  implementable by filtering the datastore (see runbook) — with the audit log
  retained as the required processing record.

## Data inventory (typical)
| Data | Store | Retention guidance |
|------|-------|--------------------|
| Attendance check-in/out | `agents/store.py` `attendance.json` | Per HR policy |
| Daily activity digest | `_data/` activity | Per retention policy |
| Access/login events | `agents/access_tracker.py` | Security-event retention (e.g. 1 year) |
| Audit trail | `_data/audit.log` | Longer, immutable |
| Project tasks | `_data/tasks.json` | Business retention |

## To align with the GDPR controller's obligations
- Set a lawful basis + DPIA for employee monitoring use.
- Configure retention & erasure per policy; test export/delete in a sandbox first.
- Use an EU/in-region in-network model endpoint and record the sub-processor if any.
- Keep the audit log as your art.30 processing record (do not delete to satisfy a
  deletion request — anonymise/minimise instead).

*This is not legal advice. Engage your DPO / counsel.*