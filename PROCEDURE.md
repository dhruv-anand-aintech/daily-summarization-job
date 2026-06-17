# Procedure

## Scheduled Run

Use a single runner script as the source of truth.

```sh
scripts/run_daily_report.sh YYYY-MM-DD
```

The runner should:

1. Load a minimal login-shell environment.
2. Resolve binaries explicitly.
3. Collect context.
4. Generate the markdown report.
5. Build the site.
6. Commit generated report artifacts in the private repo.
7. Deploy.
8. Send email after deploy.

## Why Email Is Post-Deploy

If the email is sent before deploy, the day-specific link can point to a report
that is not live yet. Keep email delivery after deploy and treat deploy success
as a prerequisite for sending the link.

## Generated Report Commit Rule

Generated reports should be committed in the private report repo so the deployed
site can be traced back to git state. Stage explicit paths only:

```sh
git add out/YYYY-MM-DD/report.md src/generated/reports.json
git commit -m "Add daily report for YYYY-MM-DD"
git push
```
