# uv run python scripts/authorize_gmail.py
"""One-time OAuth 2.0 authorization flow for Gmail API.

Run this script once locally to generate gmail_token.json.
The token is then used by the Gmail service to send emails without
requiring the user to re-authenticate.

Requirements:
- GMAIL_CREDENTIALS_FILE must point to the OAuth client secret JSON
  downloaded from Google Cloud Console.
- After running, GMAIL_TOKEN_FILE will be created in the project root.
"""

from __future__ import annotations

import os
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES: list[str] = ["https://www.googleapis.com/auth/gmail.send"]

CREDENTIALS_FILE = os.environ.get(
    "GMAIL_CREDENTIALS_FILE",
    "client_secret_868053446321-1pp3l52jagdf73stp16f8md9k545n5mq.apps.googleusercontent.com.json",
)
TOKEN_FILE = os.environ.get("GMAIL_TOKEN_FILE", "gmail_token.json")


def authorize() -> None:
    creds: Credentials | None = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if creds and creds.valid:
        print(f"[OK] Token already valid. File: {TOKEN_FILE}")
        return

    if creds and creds.expired and creds.refresh_token:
        print("[INFO] Refreshing expired token...")
        creds.refresh(Request())
    else:
        if not os.path.exists(CREDENTIALS_FILE):
            print(f"[ERROR] Credentials file not found: {CREDENTIALS_FILE}")
            sys.exit(1)

        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)  # type: ignore
        print("[OK] Authorization successful.")

    with open(TOKEN_FILE, "w") as token_file:
        token_file.write(creds.to_json())  # type: ignore

    print(f"[OK] Token saved to {TOKEN_FILE}")
    print("     Add this path to GMAIL_TOKEN_FILE in your .env file.")


if __name__ == "__main__":
    authorize()
