# Email Management Utility

A Python utility to automatically manage Gmail and Outlook emails with intelligent filtering, archiving, and calendar integration.

## Current Recommended Workflow

The most current and safest path in this repository is the dry-run CLI:

```bash
python3 -m email_core.run_daily_review
```

It supports:

- `--provider sample` for local fixture-backed testing
- `--provider gmail` for Gmail metadata review using read-only OAuth access

The Gmail dry-run CLI is intentionally limited:

- Reads Gmail message metadata only
- Does not modify labels or messages
- Does not archive, trash, delete, send, or batch modify mail
- Does not fetch full bodies or download attachments
- Does not create calendar events
- Always writes a Markdown report and JSONL audit log instead of changing the mailbox

Outputs:

- `reports/daily-review.md`
- `runs/audit-log.jsonl`

### Gmail Dry-Run Quick Start

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Create a Google Cloud Desktop app OAuth client for the Gmail API and save the downloaded file as `gmail_credentials.json` in the project root.

3. Run the dry-run CLI:

```bash
python3 -m email_core.run_daily_review \
  --provider gmail \
  --policy fixtures/sample_policy.json \
  --report reports/daily-review.md \
  --audit runs/audit-log.jsonl \
  --max-results 20 \
  --user-email your-email@example.com
```

Optional Gmail flags:

- `--query "label:inbox"` to narrow the mailbox slice
- `--user-id me` to target the default Gmail account

The first Gmail run creates `gmail_readonly_token.pickle`, which is ignored by git.

### Sample Dry-Run Quick Start

```bash
python3 -m email_core.run_daily_review \
  --provider sample \
  --emails fixtures/sample_emails.json \
  --policy fixtures/sample_policy.json \
  --report reports/daily-review.md \
  --audit runs/audit-log.jsonl
```

## Current Phase 2 Features

The current `email_core.run_daily_review` path supports:

- provider-neutral policy evaluation through `NormalizedEmail`
- fixture-backed sample runs with `--provider sample`
- Gmail metadata dry runs with `--provider gmail`
- Markdown review output in `reports/daily-review.md`
- JSONL audit output in `runs/audit-log.jsonl`
- read-only Gmail OAuth using `gmail.readonly`

## Safety Boundaries

The current recommended workflow is intentionally limited:

- no label changes
- no archive, trash, delete, send, or batch modify actions
- no full-body retrieval
- no attachment downloads
- no calendar creation
- no Outlook integration in the Phase 2 CLI

If you need setup details for the current Gmail dry-run path, use [SETUP_GUIDE.md](/Users/shola/Documents/Inbox Organiser/SETUP_GUIDE.md).

## Current Project Layout

```text
email_core/
  models.py              Provider-neutral email model
  policy_loader.py       Policy parsing and loading
  policy_engine.py       Policy evaluation
  report_writer.py       Markdown report rendering
  audit_log.py           JSONL audit rendering
  gmail_adapter.py       Read-only Gmail metadata normalization
  gmail_service.py       Read-only Gmail OAuth/service helper
  run_daily_review.py    Current dry-run CLI entry point
fixtures/
  sample_emails.json
  sample_policy.json
tests/
  test_models.py
  test_policy_loader.py
  test_policy_engine.py
  test_report_writer.py
  test_audit_log.py
  test_gmail_adapter.py
  test_gmail_service.py
  test_run_daily_review.py
```

## Verification

Run the current automated checks with:

```bash
python3 -m unittest discover -s tests
python3 -m compileall email_core tests
```

## Archived Legacy Live Workflow

This repository still contains older experimental/live-management code such as:

- `email_manager.py`
- `gmail_handler.py`
- `outlook_handler.py`

That legacy path is not the recommended Phase 2 workflow.

Important differences from the current dry-run CLI:

- it was designed around broader mailbox-management behavior
- it includes Gmail modify/calendar concepts that do not apply to the current read-only CLI
- it can imply live mailbox actions that are intentionally out of scope for Phase 2

If you need that historical context, treat it as archived reference material rather than the current product path.

## Contributing

Changes that preserve the current dry-run, read-only safety model are the best fit for this repository’s current direction.

## License

MIT License.
