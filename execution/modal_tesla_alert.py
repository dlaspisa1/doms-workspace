"""
Tesla Stock Alert - Modal

Alerts when TSLA drops 5%, 10%, 15%, etc. from 24h high.

Setup:
  modal secret create gmail-token GMAIL_TOKEN="$(cat token.json)"  # Already done
  modal deploy execution/modal_tesla_alert.py
"""

import modal
import json
import os

app = modal.App("tesla-price-alert")
state = modal.Dict.from_name("tesla-alert-state", create_if_missing=True)
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "requests", "yfinance", "google-api-python-client", "google-auth"
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
    schedule=modal.Cron("*/15 9-16 * * 1-5"),  # Every 15 min during market hours (9am-4pm ET, Mon-Fri)
)
def check_tesla():
    import yfinance as yf
    from datetime import datetime

    # Get Tesla stock data
    tsla = yf.Ticker("TSLA")
    data = tsla.history(period="1d")

    if data.empty:
        print("Market closed or no data")
        return

    price = data['Close'].iloc[-1]
    high = data['High'].max()
    drop = (high - price) / high * 100 if high > 0 else 0
    threshold = int(drop // INCREMENT) * INCREMENT

    # Get last alerted threshold
    last = state.get("threshold", 0)

    print(f"TSLA: ${price:.2f} | High: ${high:.2f} | Drop: {drop:.1f}% | Threshold: {threshold}% | Last: {last}%")

    # Alert if crossed new threshold
    if threshold >= INCREMENT and threshold > last:
        send_alert(
            f"TSLA Alert: -{drop:.1f}% (crossed {threshold}%)",
            f"TSLA: ${price:.2f} (-{drop:.1f}% from day high, crossed {threshold}%)"
        )
        state["threshold"] = threshold
        print("ALERT SENT")
    elif threshold < last:
        state["threshold"] = threshold  # Reset on recovery
        print("Price recovered, threshold reset")


@app.function(image=image, secrets=[modal.Secret.from_name("gmail-token")])
def test_alert():
    """Send a test alert (MMS + email)."""
    send_alert("TSLA Test Alert", "TSLA Alert Test - Modal setup working")
    print("Test alert sent (MMS + email)")


@app.local_entrypoint()
def main():
    check_tesla.remote()
