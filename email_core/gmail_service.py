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

    Request, InstalledAppFlow, build = _load_google_client_modules()

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
                raise FileNotFoundError(_missing_credentials_message(credentials_path))
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path),
                [GMAIL_READONLY_SCOPE],
            )
            creds = flow.run_local_server(port=0)

        with token_path.open("wb") as token_handle:
            pickle.dump(creds, token_handle)

    return build("gmail", "v1", credentials=creds)


def _load_google_client_modules():
    try:
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ModuleNotFoundError as error:
        raise ImportError(
            "Gmail dry-run CLI requires Google API client libraries for gmail.readonly access. "
            "Install them with `pip install -r requirements.txt` "
            "(google-auth, google-auth-oauthlib, google-api-python-client)."
        ) from error

    return Request, InstalledAppFlow, build


def _missing_credentials_message(credentials_path: Path) -> str:
    return (
        "Gmail read-only mode requires a Desktop app OAuth client file. "
        f"Expected credentials at {credentials_path}. "
        "Download the credentials JSON from Google Cloud Console and save it as "
        "`gmail_credentials.json` before running `--provider gmail`."
    )
