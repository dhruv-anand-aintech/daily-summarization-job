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

## Included Files

- `scripts/collect_daily_context.py` - configurable evidence collector.
- `scripts/run_daily_report.sh` - Codex/agent exec job runner.
- `scripts/build_reports.mjs` - static report JSON builder.
- `prompts/daily_report_prompt.md` - report generation prompt.
- `prompts/post_deploy_email_prompt.md` - post-deploy email prompt.
- `config.example.json` - copy to `config.json` and edit locally.
- `config/project_names.json` - editable project display-name mapping.
- `launchd/com.example.daily-summarization.plist.template` - macOS schedule template.

## Quick Start

```sh
cp config.example.json config.json
chmod +x scripts/run_daily_report.sh scripts/collect_daily_context.py
DRY_RUN=1 scripts/run_daily_report.sh "$(date +%F)"
```

Set `INCLUDE_RECENT_FILES=1` to include the heavier filesystem modified-file
scan. The default runner skips it so first dry-runs stay quick.
For dry-run smoke tests, set `INCLUDE_GIT=0` if your code root has many repos.

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

The included scripts are intentionally configurable rather than tied to one
machine or domain. Treat `config.json`, generated `out/`, and logs as private.
