You are generating a daily work report from a local collector JSON.

Inputs:
- Collector JSON path: {CONTEXT_JSON}
- Report date: {REPORT_DATE}
- Report output path: {REPORT_MD}

Read the collector JSON from disk. Use it as evidence. Do not re-run expensive
global scans unless the JSON is missing or malformed.

Rules:
- Distinguish confirmed evidence from inference.
- Do not include secrets, raw auth URLs, private transcript paths, or tokens.
- Prefer colloquial project names from `project_names`.
- Use `project_kanban` only as project status/context; do not invent work from it.

Write only the Markdown report to `{REPORT_MD}`. Do not send email from this
step; the runner sends email after deploy.
