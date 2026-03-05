"""
Detect potential phishing and scam emails in Gmail inbox
"""

import re
from gmail_auth import get_gmail_service

class PhishingDetector:
    def __init__(self):
        self.service = get_gmail_service()

        # Phishing indicators
        self.urgency_keywords = [
            'urgent', 'immediate action', 'act now', 'expire', 'suspended',
            'verify your account', 'confirm your identity', 'unusual activity',
            'security alert', 'account locked', 'final notice', 'last chance'
        ]

        self.sensitive_requests = [
            'social security', 'ssn', 'password', 'credit card', 'banking',
            'routing number', 'account number', 'pin', 'security code',
            'verify your information', 'update your payment'
        ]

        self.threat_keywords = [
            'legal action', 'lawsuit', 'arrest', 'warrant', 'irs',
            'tax fraud', 'suspended', 'frozen account', 'penalty'
        ]

        self.suspicious_domains = [
            # Common phishing TLDs and patterns
            '.tk', '.ml', '.ga', '.cf', '.gq',  # Free TLDs often used for phishing
            '-secure', '-verify', '-update', '-account',  # Suspicious patterns
        ]

        self.legitimate_domains = [
            'apple.com', 'google.com', 'amazon.com', 'paypal.com',
            'microsoft.com', 'facebook.com', 'linkedin.com', 'twitter.com',
            'instagram.com', 'netflix.com', 'spotify.com', 'etrade.com',
            'schwab.com', 'vanguard.com', 'chase.com', 'wellsfargo.com',
            'bankofamerica.com', 'americanexpress.com'
        ]

    def _extract_domain(self, email):
        """Extract domain from email address"""
        match = re.search(r'@([\w\.-]+)', email)
        return match.group(1).lower() if match else ''

    def _is_suspicious_domain(self, domain):
        """Check if domain looks suspicious"""
        # Check against known legitimate domains
        for legit in self.legitimate_domains:
            if legit in domain:
                return False

        # Check for suspicious patterns
        for pattern in self.suspicious_domains:
            if pattern in domain:
                return True

        # Check for IP addresses in domain
        if re.match(r'\d+\.\d+\.\d+\.\d+', domain):
            return True

        return False

    def _calculate_risk_score(self, sender, subject, snippet):
        """Calculate risk score for an email (0-100)"""
        score = 0
        reasons = []

        sender_lower = sender.lower()
        subject_lower = subject.lower()
        snippet_lower = snippet.lower()
        content = f"{subject_lower} {snippet_lower}"

        # Check domain
        domain = self._extract_domain(sender_lower)
        if self._is_suspicious_domain(domain):
            score += 30
            reasons.append(f"Suspicious domain: {domain}")

        # Check for urgency language
        urgency_count = sum(1 for kw in self.urgency_keywords if kw in content)
        if urgency_count > 0:
            score += min(urgency_count * 15, 40)
            reasons.append(f"Urgency language detected ({urgency_count} instances)")

        # Check for sensitive information requests
        sensitive_count = sum(1 for kw in self.sensitive_requests if kw in content)
        if sensitive_count > 0:
            score += min(sensitive_count * 20, 50)
            reasons.append(f"Requests sensitive info ({sensitive_count} instances)")

        # Check for threats
        threat_count = sum(1 for kw in self.threat_keywords if kw in content)
        if threat_count > 0:
            score += min(threat_count * 25, 50)
            reasons.append(f"Contains threats ({threat_count} instances)")

        # Check for generic greetings
        generic_greetings = ['dear customer', 'dear user', 'dear member', 'valued customer']
        if any(greeting in content for greeting in generic_greetings):
            score += 10
            reasons.append("Generic greeting")

        # Check for suspicious patterns
        if 'click here' in content or 'verify now' in content:
            score += 15
            reasons.append("Suspicious call-to-action")

        # Check for misspellings of common brands
        brand_typos = [
            ('paypa1', 'paypal'), ('g00gle', 'google'), ('amaz0n', 'amazon'),
            ('micros0ft', 'microsoft'), ('app1e', 'apple')
        ]
        for typo, brand in brand_typos:
            if typo in content:
                score += 30
                reasons.append(f"Possible brand impersonation: {brand}")

        return min(score, 100), reasons

    def scan_inbox(self, max_messages=500):
        """Scan inbox for potential phishing/scam emails"""
        print("=" * 80)
        print("Phishing & Scam Detection")
        print("=" * 80)
        print()

        try:
            # Get recent unread or inbox messages
            results = self.service.users().messages().list(
                userId='me',
                q='in:inbox',
                maxResults=max_messages
            ).execute()

            messages = results.get('messages', [])

            if not messages:
                print("No messages to scan")
                return []

            print(f"Scanning {len(messages)} messages...\n")

            suspicious_emails = []

            for i, msg in enumerate(messages):
                if (i + 1) % 50 == 0:
                    print(f"Processed {i + 1}/{len(messages)} messages...")

                try:
                    # Get message details
                    msg_data = self.service.users().messages().get(
                        userId='me',
                        id=msg['id'],
                        format='metadata',
                        metadataHeaders=['From', 'Subject', 'Date']
                    ).execute()

                    # Extract info
                    headers = msg_data.get('payload', {}).get('headers', [])
                    sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
                    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
                    date_str = next((h['value'] for h in headers if h['name'] == 'Date'), '')
                    snippet = msg_data.get('snippet', '')

                    # Calculate risk score
                    risk_score, reasons = self._calculate_risk_score(sender, subject, snippet)

                    # Flag if high risk (score >= 40)
                    if risk_score >= 40:
                        suspicious_emails.append({
                            'id': msg['id'],
                            'sender': sender,
                            'subject': subject,
                            'date': date_str,
                            'snippet': snippet[:100],
                            'risk_score': risk_score,
                            'reasons': reasons
                        })

                except Exception as e:
                    print(f"Error processing message: {e}")
                    continue

            # Sort by risk score (highest first)
            suspicious_emails.sort(key=lambda x: x['risk_score'], reverse=True)

            # Display results
            print(f"\n{'=' * 80}")
            print(f"Scan Complete - Found {len(suspicious_emails)} suspicious emails")
            print(f"{'=' * 80}\n")

            if not suspicious_emails:
                print("✓ No suspicious emails detected!")
                return []

            for i, email in enumerate(suspicious_emails, 1):
                risk_level = "HIGH" if email['risk_score'] >= 70 else "MEDIUM"
                print(f"{i}. [{risk_level} RISK - Score: {email['risk_score']}]")
                print(f"   From: {email['sender']}")
                print(f"   Subject: {email['subject']}")
                print(f"   Date: {email['date'][:25]}")
                print(f"   Snippet: {email['snippet']}...")
                print(f"   Reasons:")
                for reason in email['reasons']:
                    print(f"     - {reason}")
                print(f"   Message ID: {email['id']}")
                print()

            return suspicious_emails

        except Exception as e:
            print(f"Error scanning inbox: {e}")
            return []

def main():
    detector = PhishingDetector()
    suspicious = detector.scan_inbox(max_messages=500)

    if suspicious:
        print("\n" + "=" * 80)
        print("⚠️  RECOMMENDATION")
        print("=" * 80)
        print("Review these messages carefully. Do NOT click any links or provide")
        print("personal information. If unsure, contact the company directly using")
        print("official contact methods (not links in the email).")
        print("\nTo delete these emails, you can run a separate deletion script.")

if __name__ == "__main__":
    main()
