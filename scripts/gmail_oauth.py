#!/usr/bin/env python3
"""
One-time Gmail OAuth2 setup.

Steps:
  1. Download OAuth2 credentials from Google Cloud Console (see instructions below)
  2. Save the file as credentials.json in the project root
  3. Run:  uv run python scripts/gmail_oauth.py
  4. A browser window will open – sign in and grant access
  5. Copy the printed GMAIL_REFRESH_TOKEN value into your .env

Instructions for Google Cloud Console:
  - Go to https://console.cloud.google.com/
  - Create or select a project
  - APIs & Services → Enable APIs → enable "Gmail API"
  - APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
    - Application type: Desktop app
    - Name: elderCRM
  - Download the JSON → save as credentials.json in the project root
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
CREDENTIALS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "credentials.json",
)


def main():
    if not os.path.exists(CREDENTIALS_FILE):
        print("ERROR: credentials.json not found in project root.")
        print("       Download it from Google Cloud Console (OAuth 2.0 Client ID).")
        sys.exit(1)

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    # Read client_id and client_secret from credentials.json
    with open(CREDENTIALS_FILE) as f:
        data = json.load(f)
    client_info = data.get("installed") or data.get("web", {})

    print("\n" + "=" * 60)
    print("Add these to your .env file:")
    print("=" * 60)
    print(f"GMAIL_CLIENT_ID={client_info.get('client_id', '')}")
    print(f"GMAIL_CLIENT_SECRET={client_info.get('client_secret', '')}")
    print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")
    print("=" * 60)
    print("\nAlso set the sender address:")
    print("GMAIL_USER=your_gmail@gmail.com")
    print()


if __name__ == "__main__":
    main()
