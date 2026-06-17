Send the already-generated daily report email.

Inputs:
- Report date: {REPORT_DATE}
- Report markdown path: {REPORT_MD}
- Recipient: {REPORT_EMAIL_TO}
- Live report link: {REPORT_URL}

Read the markdown report from disk. Send via the configured email connector.
Start the body with the live report link, then include the full markdown report.
