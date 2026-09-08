"""
Weekly Gmail security cleanup:
- Scan inbox for phishing/fraud risk
- Collect spam older than a threshold
- Move selected messages to Trash (recoverable for 30 days)
- Write a JSON report and optionally email it
"""

import argparse
import base64
import json
import os
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from detect_phishing_scams import PhishingDetector


def header_value(headers, name):
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def list_message_ids(service, query, limit):
    ids = []
    page_token = None

    while len(ids) < limit:
        remaining = limit - len(ids)
        response = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=min(500, remaining),
            pageToken=page_token,
        ).execute()

        ids.extend([message["id"] for message in response.get("messages", [])])
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return ids


def get_message_metadata(service, message_id):
    message = service.users().messages().get(
        userId="me",
        id=message_id,
        format="metadata",
        metadataHeaders=["From", "Subject", "Date"],
    ).execute()

    headers = message.get("payload", {}).get("headers", [])
    return {
        "id": message_id,
        "sender": header_value(headers, "From"),
        "subject": header_value(headers, "Subject"),
        "date": header_value(headers, "Date"),
        "snippet": message.get("snippet", "")[:160],
    }


def move_to_trash(service, message_ids, dry_run):
    if dry_run or not message_ids:
        return 0

    moved = 0
    for index in range(0, len(message_ids), 1000):
        batch = message_ids[index:index + 1000]
        service.users().messages().batchModify(
            userId="me",
            body={
                "ids": batch,
                "addLabelIds": ["TRASH"],
            },
        ).execute()
        moved += len(batch)

    return moved


def send_report_email(service, recipient, report_path, report):
    summary = report["summary"]
    subject = "Gmail Weekly Security Cleanup Report"
    body = (
        "Your Gmail security cleanup completed.\n\n"
        f"Timestamp: {report['timestamp']}\n"
        f"Dry run: {report['dry_run']}\n"
        f"Inbox scanned: {summary['inbox_scanned']}\n"
        f"Suspicious detected: {summary['suspicious_detected']}\n"
        f"High-risk detected: {summary['high_risk_detected']}\n"
        f"Spam detected: {summary['spam_detected']}\n"
        f"Unique messages selected: {summary['unique_messages_selected']}\n"
        f"Moved to Trash: {summary['unique_messages_moved_to_trash']}\n\n"
        "The full JSON report is attached."
    )

    message = MIMEMultipart()
    message["To"] = recipient
    message["From"] = recipient
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    attachment = MIMEBase("application", "json")
    with open(report_path, "rb") as file_handle:
        attachment.set_payload(file_handle.read())
    encoders.encode_base64(attachment)
    attachment.add_header(
        "Content-Disposition",
        f'attachment; filename="{os.path.basename(report_path)}"',
    )
    message.attach(attachment)

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    result = service.users().messages().send(
        userId="me",
        body={"raw": raw_message},
    ).execute()
    return result.get("id")


def run_cleanup(args):
    print("Connecting to Gmail API...")
    detector = PhishingDetector()
    service = detector.service

    print(f"Scanning inbox (max {args.max_inbox})...")
    inbox_ids = list_message_ids(service, "in:inbox", args.max_inbox)

    suspicious = []
    high_risk = []

    for index, message_id in enumerate(inbox_ids, start=1):
        if index % 50 == 0:
            print(f"  processed {index}/{len(inbox_ids)} inbox messages")

        try:
            metadata = get_message_metadata(service, message_id)
            risk_score, reasons = detector._calculate_risk_score(
                metadata["sender"],
                metadata["subject"],
                metadata["snippet"],
            )
            if risk_score >= 40:
                entry = {
                    **metadata,
                    "risk_score": risk_score,
                    "reasons": reasons,
                }
                suspicious.append(entry)
                if risk_score >= args.high_risk_threshold:
                    high_risk.append(entry)
        except Exception as error:
            suspicious.append(
                {
                    "id": message_id,
                    "error": str(error),
                    "risk_score": -1,
                }
            )

    suspicious.sort(key=lambda item: item.get("risk_score", 0), reverse=True)
    high_risk.sort(key=lambda item: item.get("risk_score", 0), reverse=True)

    spam_query = f"in:spam older_than:{args.spam_older_than_days}d"
    print(f"Scanning spam with query: {spam_query} (max {args.max_spam})...")
    spam_ids = list_message_ids(service, spam_query, args.max_spam)

    spam_messages = []
    for index, message_id in enumerate(spam_ids, start=1):
        if index % 100 == 0:
            print(f"  processed {index}/{len(spam_ids)} spam messages")
        try:
            spam_messages.append(get_message_metadata(service, message_id))
        except Exception as error:
            spam_messages.append(
                {
                    "id": message_id,
                    "error": str(error),
                }
            )

    high_risk_ids = [message["id"] for message in high_risk if "id" in message]
    selected_ids = list(dict.fromkeys(high_risk_ids + spam_ids))
    print(f"Selected {len(selected_ids)} messages for Trash action")

    moved_count = move_to_trash(service, selected_ids, args.dry_run)

    os.makedirs(".tmp", exist_ok=True)
    report_path = (
        f".tmp/phishing_spam_cleanup_report_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
    )

    report = {
        "timestamp": datetime.now().isoformat(),
        "dry_run": args.dry_run,
        "action": (
            "Scan inbox for phishing/fraud and clean older spam. "
            "Messages are moved to Gmail Trash when not in dry-run mode."
        ),
        "config": {
            "max_inbox": args.max_inbox,
            "max_spam": args.max_spam,
            "high_risk_threshold": args.high_risk_threshold,
            "spam_older_than_days": args.spam_older_than_days,
        },
        "summary": {
            "inbox_scanned": len(inbox_ids),
            "suspicious_detected": len(
                [message for message in suspicious if message.get("risk_score", 0) >= 40]
            ),
            "high_risk_detected": len(
                [message for message in high_risk if message.get("risk_score", 0) >= args.high_risk_threshold]
            ),
            "spam_detected": len(spam_ids),
            "unique_messages_selected": len(selected_ids),
            "unique_messages_moved_to_trash": moved_count,
        },
        "high_risk_messages": high_risk,
        "spam_messages": spam_messages,
    }

    with open(report_path, "w", encoding="utf-8") as file_handle:
        json.dump(report, file_handle, indent=2)

    email_message_id = None
    if not args.no_email:
        if args.recipient:
            recipient = args.recipient
        else:
            profile = service.users().getProfile(userId="me").execute()
            recipient = profile.get("emailAddress")
        print(f"Emailing report to {recipient}...")
        email_message_id = send_report_email(service, recipient, report_path, report)

    print("---SUMMARY---")
    print(json.dumps(report["summary"]))
    print(f"REPORT_PATH={report_path}")
    if email_message_id:
        print(f"EMAIL_MESSAGE_ID={email_message_id}")


def parse_args():
    parser = argparse.ArgumentParser(description="Gmail weekly security cleanup")
    parser.add_argument("--max-inbox", type=int, default=500)
    parser.add_argument("--max-spam", type=int, default=500)
    parser.add_argument("--high-risk-threshold", type=int, default=70)
    parser.add_argument("--spam-older-than-days", type=int, default=7)
    parser.add_argument("--recipient", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-email", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    run_cleanup(parse_args())
