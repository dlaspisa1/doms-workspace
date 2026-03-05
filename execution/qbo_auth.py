#!/usr/bin/env python3
"""
QuickBooks Online OAuth 2.0 Authentication
Handles the OAuth flow to get access and refresh tokens
"""

import os
import json
from dotenv import load_dotenv
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs

load_dotenv()

# Configuration
CLIENT_ID = os.getenv('QBO_CLIENT_ID')
CLIENT_SECRET = os.getenv('QBO_CLIENT_SECRET')
REDIRECT_URI = os.getenv('QBO_REDIRECT_URI', 'http://localhost:8080/callback')
ENVIRONMENT = os.getenv('QBO_ENVIRONMENT', 'sandbox')  # 'sandbox' or 'production'
TOKEN_FILE = os.path.expanduser('~/.qbo_tokens.json')

class AuthHandler(http.server.SimpleHTTPRequestHandler):
    """Handle OAuth callback"""
    auth_code = None
    realm_id = None

    def do_GET(self):
        """Handle the OAuth callback"""
        if '/callback' in self.path:
            # Parse the callback URL
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            AuthHandler.auth_code = params.get('code', [None])[0]
            AuthHandler.realm_id = params.get('realmId', [None])[0]

            # Send success response
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()

            html = """
            <html>
            <body>
                <h1>Authorization Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
                <p><strong>Realm ID:</strong> {}</p>
            </body>
            </html>
            """.format(AuthHandler.realm_id)

            self.wfile.write(html.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress log messages"""
        pass


def get_authorization_url():
    """Generate authorization URL for user to visit"""
    auth_client = AuthClient(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        environment=ENVIRONMENT,
    )

    scopes = [
        Scopes.ACCOUNTING,
    ]

    auth_url = auth_client.get_authorization_url(scopes)
    return auth_client, auth_url


def exchange_code_for_tokens(auth_client, auth_code, realm_id):
    """Exchange authorization code for access and refresh tokens"""
    auth_client.get_bearer_token(auth_code, realm_id=realm_id)

    tokens = {
        'access_token': auth_client.access_token,
        'refresh_token': auth_client.refresh_token,
        'realm_id': realm_id,
        'token_type': 'Bearer',
        'expires_in': auth_client.expires_in,
    }

    return tokens


def save_tokens(tokens):
    """Save tokens to file"""
    with open(TOKEN_FILE, 'w') as f:
        json.dump(tokens, f, indent=2)
    print(f"\n✓ Tokens saved to {TOKEN_FILE}")


def load_tokens():
    """Load tokens from file"""
    if not os.path.exists(TOKEN_FILE):
        return None

    with open(TOKEN_FILE, 'r') as f:
        return json.load(f)


def refresh_tokens():
    """Refresh access token using refresh token"""
    tokens = load_tokens()
    if not tokens or 'refresh_token' not in tokens:
        print("No refresh token found. Please re-authenticate.")
        return None

    auth_client = AuthClient(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        environment=ENVIRONMENT,
    )

    auth_client.refresh(refresh_token=tokens['refresh_token'])

    new_tokens = {
        'access_token': auth_client.access_token,
        'refresh_token': auth_client.refresh_token,
        'realm_id': tokens['realm_id'],
        'token_type': 'Bearer',
        'expires_in': auth_client.expires_in,
    }

    save_tokens(new_tokens)
    print("✓ Tokens refreshed successfully")
    return new_tokens


def get_valid_tokens():
    """Get valid tokens, refreshing if necessary"""
    tokens = load_tokens()

    if not tokens:
        print("No tokens found. Please authenticate first.")
        return None

    # Try to refresh tokens (QuickBooks tokens expire after 1 hour)
    try:
        return refresh_tokens()
    except Exception as e:
        print(f"Error refreshing tokens: {e}")
        print("Please re-authenticate.")
        return None


def main():
    """Main authentication flow"""
    print("QuickBooks Online OAuth 2.0 Authentication\n")

    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: QBO_CLIENT_ID and QBO_CLIENT_SECRET must be set in .env")
        print("\nSetup instructions:")
        print("1. Go to https://developer.intuit.com")
        print("2. Create an app (or use existing)")
        print("3. Get Client ID and Client Secret")
        print("4. Add to .env file")
        return

    print(f"Environment: {ENVIRONMENT}")
    print(f"Redirect URI: {REDIRECT_URI}\n")

    # Check if tokens already exist
    existing_tokens = load_tokens()
    if existing_tokens:
        print(f"✓ Existing tokens found for Realm ID: {existing_tokens.get('realm_id')}")
        choice = input("\nRefresh tokens (r) or Re-authenticate (a)? [r/a]: ").lower()

        if choice == 'r':
            refresh_tokens()
            return

    # Start OAuth flow
    auth_client, auth_url = get_authorization_url()

    print("Step 1: Open this URL in your browser:")
    print(f"\n{auth_url}\n")

    print("Step 2: Sign in and authorize the app")
    print("Step 3: Starting callback server on http://localhost:8080\n")

    # Start local server to receive callback
    PORT = 8080
    with socketserver.TCPServer(("", PORT), AuthHandler) as httpd:
        print(f"Waiting for callback on port {PORT}...")
        print("(The browser will redirect here after authorization)\n")

        # Handle one request (the callback)
        httpd.handle_request()

    if AuthHandler.auth_code and AuthHandler.realm_id:
        print(f"\n✓ Authorization successful!")
        print(f"✓ Realm ID: {AuthHandler.realm_id}")
        print(f"\nExchanging authorization code for tokens...")

        tokens = exchange_code_for_tokens(auth_client, AuthHandler.auth_code, AuthHandler.realm_id)
        save_tokens(tokens)

        print(f"\n{'='*60}")
        print("SUCCESS! QuickBooks authentication complete.")
        print(f"{'='*60}")
        print(f"\nYour Realm ID: {tokens['realm_id']}")
        print(f"\nAdd this to your .env file:")
        print(f"QBO_REALM_ID={tokens['realm_id']}")
        print(f"\nTokens are valid and will auto-refresh for 100 days.")
        print(f"{'='*60}\n")
    else:
        print("\n✗ Authorization failed. Please try again.")


if __name__ == '__main__':
    main()
