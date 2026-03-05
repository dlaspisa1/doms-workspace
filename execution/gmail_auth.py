"""
Gmail OAuth2 Authentication
Handles authentication flow and token management for Gmail API
"""

import os
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Gmail API scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels',
    'https://www.googleapis.com/auth/gmail.send'
]

def get_gmail_service():
    """
    Authenticate and return Gmail API service object

    Returns:
        Gmail API service object
    """
    creds = None
    token_path = 'token.json'
    credentials_path = 'credentials.json'

    # Load existing token
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # Refresh or get new token
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"credentials.json not found. "
                    f"Download from Google Cloud Console and place in project root."
                )
            print("Starting OAuth flow...")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for future use
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
        print(f"Token saved to {token_path}")

    return build('gmail', 'v1', credentials=creds)

if __name__ == "__main__":
    # Test authentication
    try:
        service = get_gmail_service()
        profile = service.users().getProfile(userId='me').execute()
        print(f"✓ Successfully authenticated as: {profile['emailAddress']}")
        print(f"  Messages in account: {profile['messagesTotal']}")
    except Exception as e:
        print(f"✗ Authentication failed: {e}")
