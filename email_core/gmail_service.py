"""Read-only Gmail service factory for the dry-run CLI."""

from __future__ import annotations

import pickle
from pathlib import Path


GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


def build_gmail_readonly_service(
    credentials_path: str | Path = "gmail_credentials.json",
    token_path: str | Path = "gmail_readonly_token.pickle",
):
    """Build a Gmail API service using a dedicated read-only OAuth token."""

    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    credentials_path = Path(credentials_path)
    token_path = Path(token_path)
    creds = None

    if token_path.exists():
        with token_path.open("rb") as token_handle:
            creds = pickle.load(token_handle)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                raise FileNotFoundError(
                    f"Gmail credentials file not found: {credentials_path}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path),
                [GMAIL_READONLY_SCOPE],
            )
            creds = flow.run_local_server(port=0)

        with token_path.open("wb") as token_handle:
            pickle.dump(creds, token_handle)

    return build("gmail", "v1", credentials=creds)
