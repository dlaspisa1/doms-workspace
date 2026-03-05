"""
BTC Price Alert - Modal

Alert logic:
- First alert: when price drops 5%+ from 24h high
- Subsequent alerts: only when price drops 5%+ from LAST ALERTED PRICE
- OR: after 24 hours have passed (resets the baseline)

This prevents spam from rolling 24h high changes.

Setup:
  modal secret create gmail-token GMAIL_TOKEN="$(cat token.json)"
  modal deploy execution/modal_btc_alert.py

Reset state (if needed):
  modal run execution/modal_btc_alert.py::reset_state
"""

import modal
import json
import os

app = modal.App("btc-price-alert")
state = modal.Dict.from_name("btc-alert-state", create_if_missing=True)
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "requests", "google-api-python-client", "google-auth"
)

MMS = "8478092948@vzwpix.com"  # Verizon MMS gateway (more reliable than SMS)
EMAIL = "dlaspisa1@gmail.com"
INCREMENT = 5  # Alert every 5%


def send_alert(subject, message):
    """Send alert via MMS and email."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    import base64
    from email.mime.text import MIMEText

    token = os.environ.get("GMAIL_TOKEN")
    if not token:
        raise ValueError("GMAIL_TOKEN not set")

    service = build('gmail', 'v1', credentials=Credentials.from_authorized_user_info(json.loads(token)))

    # Send MMS (text message)
    mms = MIMEText(message)
    mms["to"] = MMS
    mms["subject"] = ""
    raw = base64.urlsafe_b64encode(mms.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    print(f"MMS sent: {message[:50]}...")

    # Send email backup
    email = MIMEText(message)
    email["to"] = EMAIL
    email["subject"] = subject
    raw = base64.urlsafe_b64encode(email.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    print(f"Email sent: {subject}")


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("gmail-token")],
    schedule=modal.Cron("*/15 * * * *"),  # Every 15 min
)
def check_btc():
    import requests
    from datetime import datetime
    import time

    # Get current price
    data = requests.get(
        "https://api.coingecko.com/api/v3/coins/bitcoin",
        params={"localization": "false", "tickers": "false", "community_data": "false", "developer_data": "false"},
        timeout=10
    ).json()["market_data"]

    price = data["current_price"]["usd"]
    high_24h = data["high_24h"]["usd"]

    # Get state: last alerted price and timestamp
    last_alerted_price = state.get("last_alerted_price")
    last_alert_time = state.get("last_alert_time", 0)

    now = time.time()
    hours_since_alert = (now - last_alert_time) / 3600 if last_alert_time else float('inf')

    # Calculate drop from last alerted price (if exists)
    drop_from_alerted = 0
    if last_alerted_price:
        drop_from_alerted = (last_alerted_price - price) / last_alerted_price * 100

    # Calculate drop from 24h high (for reference)
    drop_from_high = (high_24h - price) / high_24h * 100 if high_24h > 0 else 0

    print(f"BTC: ${price:,.0f} | 24h High: ${high_24h:,.0f} | Drop from high: {drop_from_high:.1f}%")
    print(f"Last alerted: ${(last_alerted_price or 0):,.0f} | Drop from alerted: {drop_from_alerted:.1f}% | Hours since alert: {hours_since_alert:.1f}h")

    should_alert = False
    alert_reason = ""

    # Case 1: First alert ever - use 24h high as baseline, alert if 5%+ drop
    if last_alerted_price is None:
        if drop_from_high >= INCREMENT:
            should_alert = True
            alert_reason = f"Initial alert: -{drop_from_high:.1f}% from 24h high"

    # Case 2: Price dropped 5%+ from last alerted price
    elif drop_from_alerted >= INCREMENT:
        should_alert = True
        alert_reason = f"New drop: -{drop_from_alerted:.1f}% from last alert (${last_alerted_price:,.0f})"

    # Case 3: 24+ hours since last alert and significant drop from 24h high
    elif hours_since_alert >= 24 and drop_from_high >= INCREMENT:
        should_alert = True
        alert_reason = f"Daily alert: -{drop_from_high:.1f}% from 24h high (24h+ since last alert)"

    if should_alert:
        send_alert(
            f"BTC Alert: ${price:,.0f}",
            f"BTC: ${price:,.0f}\n{alert_reason}"
        )
        state["last_alerted_price"] = price
        state["last_alert_time"] = now
        print(f"ALERT SENT: {alert_reason}")
    else:
        print("No alert needed")


@app.function(image=image, secrets=[modal.Secret.from_name("gmail-token")])
def test_alert():
    """Send a test alert (MMS + email)."""
    send_alert("BTC Test Alert", "BTC Alert Test - Modal setup working")
    print("Test alert sent (MMS + email)")


@app.function(image=image)
def reset_state():
    """Reset alert state to start fresh."""
    state.pop("last_alerted_price", None)
    state.pop("last_alert_time", None)
    state.pop("threshold", None)  # Clean up old key
    print("State reset. Next check will use 24h high as baseline.")


@app.local_entrypoint()
def main():
    check_btc.remote()
