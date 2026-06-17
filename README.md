# Daily Summarization Job

Reusable procedure for a local daily work summarization job.

This public repo intentionally contains only scripts, prompts, and setup notes.
Keep generated reports, browser history dumps, transcript extracts, secrets,
access pins, and local logs in a private repo.

## Flow

1. Collect local evidence into `out/YYYY-MM-DD/context.json`.
2. Ask a coding agent to write `out/YYYY-MM-DD/report.md` from that JSON.
3. Build the static updates site from generated reports.
4. Commit generated report artifacts in the private report repo.
5. Deploy the site.
6. Send the email after deploy so date-specific links are live before delivery.

## Private Inputs

Configure these in your private repo or environment:

- Transcript source paths for your agents.
- Browser history source paths.
- Project-name mapping.
- Optional kanban/project board path.
- Deployment command.
- Email connector or mail adapter.

## Public Hygiene

Do not commit:

- `out/`
- `logs/`
- `.env`
- generated report markdown
- generated frontend JSON
- raw browser history
- raw transcript excerpts
- access pins, tokens, or recipient lists

Copy the script shapes from your private implementation only after replacing
machine-specific paths and private domains with documented config.
