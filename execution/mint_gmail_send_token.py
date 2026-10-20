"""
Mint a gmail.send-only OAuth token and push it straight into the Modal `gmail-token` secret.

The token is never written to disk. Run when Modal jobs fail with `invalid_grant`:
    python3 execution/mint_gmail_send_token.py
A browser opens: sign in as dlaspisa1@gmail.com and click Allow.
"""

import os
import subprocess
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/gmail.send']
CREDENTIALS_PATH = 'credentials.json'

if __name__ == "__main__":
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    if not creds.refresh_token:
        sys.exit("No refresh token returned — Modal secret untouched")

    result = subprocess.run(
        ["modal", "secret", "create", "gmail-token", f"GMAIL_TOKEN={creds.to_json()}", "--force"],
        env={**os.environ, "MODAL_PROFILE": "dlaspisa1"},
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        output = result.stdout + result.stderr
        for secret in (creds.token, creds.refresh_token, creds.client_secret):
            if secret:
                output = output.replace(secret, "***")
        sys.exit(f"modal secret create failed:\n{output[-400:]}")
    print("✓ gmail-token updated in Modal (dlaspisa1). No redeploy needed.")
