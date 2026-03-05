"""
Gmail Security Cleanup - Modal

Daily morning automation that:
- Scans inbox for phishing/fraud risk
- Performs link forensics (canonicalization, redirect checks, threat intel, domain-age)
- Moves high-risk messages to Trash
- Clears spam older than N days
- Emails a JSON report to your Gmail

Setup:
  modal secret create gmail-token GMAIL_TOKEN="$(cat token.json)"
  modal deploy execution/modal_gmail_security_cleanup.py

Optional threat intel keys (recommended for stronger detection):
  SAFE_BROWSING_API_KEY
  VIRUSTOTAL_API_KEY
  PHISHTANK_API_KEY
  WHOISXML_API_KEY

Manual run:
  modal run execution/modal_gmail_security_cleanup.py::run_now --dry-run false
"""

import base64
import csv
import html
import ipaddress
import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.parser import Parser
from html.parser import HTMLParser
from typing import Any

import modal

app = modal.App("gmail-security-cleanup")

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "google-api-python-client",
    "google-auth",
    "google-auth-httplib2",
)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]

USER_AGENT = "gmail-security-cleanup/1.0"

URGENT_KEYWORDS = [
    "urgent",
    "immediate action",
    "act now",
    "expire",
    "suspended",
    "verify your account",
    "confirm your identity",
    "unusual activity",
    "security alert",
    "account locked",
    "final notice",
    "last chance",
]

SENSITIVE_REQUESTS = [
    "social security",
    "ssn",
    "password",
    "credit card",
    "banking",
    "routing number",
    "account number",
    "pin",
    "security code",
    "verify your information",
    "update your payment",
]

THREAT_KEYWORDS = [
    "legal action",
    "lawsuit",
    "arrest",
    "warrant",
    "irs",
    "tax fraud",
    "frozen account",
    "penalty",
]

SUSPICIOUS_DOMAIN_PATTERNS = [
    ".tk",
    ".ml",
    ".ga",
    ".cf",
    ".gq",
    "-secure",
    "-verify",
    "-update",
    "-account",
]

LEGITIMATE_DOMAINS = [
    "apple.com",
    "google.com",
    "amazon.com",
    "paypal.com",
    "microsoft.com",
    "chase.com",
    "wellsfargo.com",
    "bankofamerica.com",
    "americanexpress.com",
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "coinbase.com",
    "netflix.com",
]

TRACKING_DOMAINS = {
    "mailchimp.com",
    "sendgrid.net",
    "amazonses.com",
    "hubspot.com",
    "constantcontact.com",
    "salesforce.com",
    "marketo.com",
}

SHORTENER_DOMAINS = {
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "goo.gl",
    "ow.ly",
    "rebrand.ly",
    "is.gd",
    "buff.ly",
    "cutt.ly",
    "tiny.cc",
}

SUSPICIOUS_TLDS = {
    "zip",
    "mov",
    "top",
    "xyz",
    "click",
    "work",
    "support",
    "ink",
}

TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "mkt_tok",
    "vero_id",
    "trk",
    "ref",
    "source",
}

BRAND_NAMES = [
    "amazon",
    "apple",
    "google",
    "microsoft",
    "paypal",
    "facebook",
    "instagram",
    "linkedin",
    "coinbase",
    "chase",
    "wellsfargo",
    "bankofamerica",
    "americanexpress",
    "netflix",
]

SECOND_LEVEL_TLDS = {
    "co.uk",
    "org.uk",
    "ac.uk",
    "com.au",
    "net.au",
    "co.jp",
    "com.br",
}

LIKELY_LOGIN_TOKENS = {
    "login",
    "signin",
    "verify",
    "account",
    "password",
    "billing",
    "wallet",
    "secure",
}

REDIRECT_STATUSES = {301, 302, 303, 307, 308}

URL_RE = re.compile(r"https?://[^\s<>'\"`)\]]+", flags=re.IGNORECASE)
MAX_URLS_PER_MESSAGE = int(os.environ.get("MAX_URLS_PER_MESSAGE", "5"))


class LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls: set[str] = set()

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.urls.add(value.strip())


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


NO_REDIRECT_OPENER = urllib.request.build_opener(NoRedirectHandler())


def get_gmail_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    token_raw = os.environ.get("GMAIL_TOKEN")
    if not token_raw:
        raise ValueError("GMAIL_TOKEN secret is missing")

    token_info = json.loads(token_raw)
    creds = Credentials.from_authorized_user_info(token_info, SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return build("gmail", "v1", credentials=creds)


def extract_domain(email_value: str) -> str:
    parsed = Parser().parsestr(f"From: {email_value}\n\n")
    address = parsed.get("From", "")
    match = re.search(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", address, flags=re.IGNORECASE)
    if not match:
        return ""
    email_address = match.group(1)
    domain = email_address.split("@", 1)[-1].lower().strip()
    return domain


def base_domain(domain: str) -> str:
    domain = (domain or "").strip(".").lower()
    if not domain:
        return ""
    parts = domain.split(".")
    if len(parts) <= 2:
        return domain
    suffix = ".".join(parts[-2:])
    if suffix in SECOND_LEVEL_TLDS and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def is_ip_host(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
        return True
    except Exception:
        return False


def decode_urlsafe_b64(data: str) -> str:
    if not data:
        return ""
    padding = "=" * ((4 - len(data) % 4) % 4)
    raw = base64.urlsafe_b64decode(data + padding)
    return raw.decode("utf-8", errors="ignore")


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def strip_html(html_text: str) -> str:
    if not html_text:
        return ""
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html_text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    return normalize_whitespace(text)


def extract_urls_from_text(text: str) -> set[str]:
    if not text:
        return set()
    return {match.rstrip(".,);!?]") for match in URL_RE.findall(text)}


def extract_urls_from_html(html_text: str) -> set[str]:
    urls = set()
    if not html_text:
        return urls
    parser = LinkExtractor()
    try:
        parser.feed(html_text)
    except Exception:
        pass
    urls.update(parser.urls)
    urls.update(extract_urls_from_text(html_text))
    return {url for url in urls if url.lower().startswith(("http://", "https://"))}


def canonicalize_url(url: str) -> tuple[str, str, int | None, str]:
    cleaned = (url or "").strip().strip("<>").strip("\"'")
    parts = urllib.parse.urlsplit(cleaned)
    if parts.scheme.lower() not in {"http", "https"}:
        raise ValueError("Unsupported scheme")

    raw_host = parts.hostname or ""
    if not raw_host:
        raise ValueError("Missing host")

    try:
        ascii_host = raw_host.encode("idna").decode("ascii").lower()
    except Exception:
        ascii_host = raw_host.lower()

    query_pairs = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    filtered_pairs = []
    for key, value in query_pairs:
        low_key = key.lower()
        if low_key.startswith("utm_") or low_key in TRACKING_QUERY_KEYS:
            continue
        filtered_pairs.append((key, value))

    normalized_query = urllib.parse.urlencode(filtered_pairs, doseq=True)

    scheme = parts.scheme.lower()
    port = parts.port
    include_port = port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80))
    netloc = ascii_host if not include_port else f"{ascii_host}:{port}"

    path = parts.path or "/"
    canonical = urllib.parse.urlunsplit((scheme, netloc, path, normalized_query, ""))
    return canonical, ascii_host, port, raw_host


def levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous = list(range(len(right) + 1))
    for i, char_left in enumerate(left, start=1):
        current = [i]
        for j, char_right in enumerate(right, start=1):
            insertions = previous[j] + 1
            deletions = current[j - 1] + 1
            substitutions = previous[j - 1] + (char_left != char_right)
            current.append(min(insertions, deletions, substitutions))
        previous = current
    return previous[-1]


def lookalike_normalized(text: str) -> str:
    replace_map = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})
    return text.translate(replace_map)


def detect_typosquat(hostname: str) -> list[str]:
    label = hostname.split(".")[0].lower()
    normalized = lookalike_normalized(label)
    matches = []
    for brand in BRAND_NAMES:
        if brand in label:
            continue
        if brand in normalized:
            matches.append(brand)
            continue
        dist = levenshtein_distance(normalized[: len(brand)], brand)
        if dist <= 1 and abs(len(normalized) - len(brand)) <= 2:
            matches.append(brand)
    return sorted(set(matches))


def safe_request_json(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = 7,
) -> tuple[int, dict[str, Any]]:
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"User-Agent": USER_AGENT, **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.getcode()
            payload = response.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as err:
        status = err.code
        payload = err.read().decode("utf-8", errors="ignore")
    except Exception as err:
        return 0, {"_error": str(err)}

    try:
        parsed = json.loads(payload)
        if isinstance(parsed, dict):
            return status, parsed
        return status, {"_data": parsed}
    except Exception:
        return status, {"_raw": payload}


def probe_once(url: str) -> tuple[int, dict[str, str], str | None]:
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    req = urllib.request.Request(url, method="HEAD", headers=headers)
    try:
        with NO_REDIRECT_OPENER.open(req, timeout=6) as response:
            return response.getcode(), dict(response.headers), None
    except urllib.error.HTTPError as err:
        if err.code in REDIRECT_STATUSES:
            return err.code, dict(err.headers), None
        if err.code in {405, 501}:
            pass
        else:
            return err.code, dict(err.headers), None
    except Exception as err:
        return 0, {}, str(err)

    req_get = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with NO_REDIRECT_OPENER.open(req_get, timeout=6) as response:
            return response.getcode(), dict(response.headers), None
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), None
    except Exception as err:
        return 0, {}, str(err)


def follow_redirect_chain(url: str, cache: dict[str, dict[str, Any]], max_hops: int = 5) -> tuple[list[str], str, str | None]:
    if url in cache:
        cached = cache[url]
        return cached["chain"], cached["final_url"], cached["error"]

    chain = [url]
    current = url
    error = None

    for _ in range(max_hops):
        status, headers, err = probe_once(current)
        if err:
            error = err
            break
        if status not in REDIRECT_STATUSES:
            break
        location = headers.get("Location") or headers.get("location")
        if not location:
            break
        next_url = urllib.parse.urljoin(current, location)
        if next_url in chain:
            break
        chain.append(next_url)
        current = next_url

    result = {"chain": chain, "final_url": chain[-1], "error": error}
    cache[url] = result
    return chain, result["final_url"], error


def get_domain_age_days(domain: str, cache: dict[str, int | None]) -> int | None:
    domain = base_domain(domain)
    if not domain:
        return None
    if domain in cache:
        return cache[domain]

    api_key = os.environ.get("WHOISXML_API_KEY", "").strip()
    if not api_key:
        cache[domain] = None
        return None

    endpoint = (
        "https://www.whoisxmlapi.com/whoisserver/WhoisService"
        f"?apiKey={urllib.parse.quote(api_key)}"
        f"&domainName={urllib.parse.quote(domain)}"
        "&outputFormat=JSON"
    )
    status, payload = safe_request_json(endpoint, timeout=8)
    if status == 0:
        cache[domain] = None
        return None

    created = payload.get("WhoisRecord", {}).get("createdDate")
    parsed = parse_datetime(created)
    if not parsed:
        cache[domain] = None
        return None

    days = max(0, (datetime.now(timezone.utc) - parsed).days)
    cache[domain] = days
    return days


def parse_datetime(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None

    attempt = value.strip()
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S %Z",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(attempt, fmt)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue

    try:
        dt = datetime.fromisoformat(attempt.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def check_safe_browsing(url: str) -> tuple[int, list[str], dict[str, Any]]:
    api_key = os.environ.get("SAFE_BROWSING_API_KEY", "").strip()
    if not api_key:
        return 0, [], {"enabled": False}

    endpoint = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={urllib.parse.quote(api_key)}"
    body = {
        "client": {"clientId": "gmail-security-cleanup", "clientVersion": "1.0"},
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }
    status, payload = safe_request_json(
        endpoint,
        method="POST",
        headers={"Content-Type": "application/json"},
        body=json.dumps(body).encode("utf-8"),
    )

    if status == 0:
        return 0, [], {"enabled": True, "error": payload.get("_error", "request_failed")}

    matches = payload.get("matches", []) if isinstance(payload, dict) else []
    if matches:
        return 70, ["Google Safe Browsing match"], {"enabled": True, "matches": len(matches)}
    return 0, [], {"enabled": True, "matches": 0}


def check_virustotal(url: str) -> tuple[int, list[str], dict[str, Any]]:
    api_key = os.environ.get("VIRUSTOTAL_API_KEY", "").strip()
    if not api_key:
        return 0, [], {"enabled": False}

    url_id = base64.urlsafe_b64encode(url.encode("utf-8")).decode("utf-8").strip("=")
    endpoint = f"https://www.virustotal.com/api/v3/urls/{url_id}"

    status, payload = safe_request_json(endpoint, headers={"x-apikey": api_key}, timeout=8)
    if status == 0:
        return 0, [], {"enabled": True, "error": payload.get("_error", "request_failed")}
    if status >= 400:
        return 0, [], {"enabled": True, "http_status": status}

    attributes = payload.get("data", {}).get("attributes", {})
    stats = attributes.get("last_analysis_stats", {})
    malicious = int(stats.get("malicious", 0) or 0)
    suspicious = int(stats.get("suspicious", 0) or 0)
    reputation = int(attributes.get("reputation", 0) or 0)

    score = 0
    reasons = []
    if malicious > 0:
        score += 70
        reasons.append(f"VirusTotal malicious detections ({malicious})")
    elif suspicious > 0:
        score += 45
        reasons.append(f"VirusTotal suspicious detections ({suspicious})")
    if reputation < 0:
        score += 10
        reasons.append("VirusTotal negative reputation")

    return min(score, 80), reasons, {
        "enabled": True,
        "malicious": malicious,
        "suspicious": suspicious,
        "reputation": reputation,
    }


def check_urlhaus(url: str) -> tuple[int, list[str], dict[str, Any]]:
    body = urllib.parse.urlencode({"url": url}).encode("utf-8")
    status, payload = safe_request_json(
        "https://urlhaus-api.abuse.ch/v1/url/",
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=body,
        timeout=8,
    )

    if status == 0:
        return 0, [], {"enabled": True, "error": payload.get("_error", "request_failed")}
    query_status = str(payload.get("query_status", "")).lower()
    if query_status in {"ok", "ok_url"}:
        url_status = str(payload.get("url_status", "")).lower()
        if url_status == "online":
            return 70, ["URLhaus lists URL as malicious (online)"], {"enabled": True, "url_status": url_status}
        return 50, ["URLhaus lists URL as malicious"], {"enabled": True, "url_status": url_status}

    return 0, [], {"enabled": True, "query_status": query_status or "no_results"}


def check_phishtank(url: str) -> tuple[int, list[str], dict[str, Any]]:
    form = {"url": url, "format": "json"}
    app_key = os.environ.get("PHISHTANK_API_KEY", "").strip()
    if app_key:
        form["app_key"] = app_key

    status, payload = safe_request_json(
        "https://checkurl.phishtank.com/checkurl/",
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=urllib.parse.urlencode(form).encode("utf-8"),
        timeout=8,
    )

    if status == 0:
        return 0, [], {"enabled": True, "error": payload.get("_error", "request_failed")}
    results = payload.get("results", {}) if isinstance(payload, dict) else {}
    in_db = bool(results.get("in_database"))
    valid = bool(results.get("valid"))
    verified = bool(results.get("verified"))

    if in_db and valid and verified:
        return 70, ["PhishTank verified phishing URL"], {"enabled": True, "in_database": True, "verified": True}

    return 0, [], {"enabled": True, "in_database": in_db, "verified": verified, "valid": valid}


def threat_intel_score(url: str, cache: dict[str, dict[str, Any]]) -> tuple[int, list[str], dict[str, Any]]:
    if url in cache:
        cached = cache[url]
        return cached["score"], cached["reasons"], cached["providers"]

    score = 0
    reasons: list[str] = []
    providers: dict[str, Any] = {}

    sb_score, sb_reasons, sb_meta = check_safe_browsing(url)
    score += sb_score
    reasons.extend(sb_reasons)
    providers["safe_browsing"] = sb_meta

    vt_score, vt_reasons, vt_meta = check_virustotal(url)
    score += vt_score
    reasons.extend(vt_reasons)
    providers["virustotal"] = vt_meta

    urlhaus_score, urlhaus_reasons, urlhaus_meta = check_urlhaus(url)
    score += urlhaus_score
    reasons.extend(urlhaus_reasons)
    providers["urlhaus"] = urlhaus_meta

    pt_score, pt_reasons, pt_meta = check_phishtank(url)
    score += pt_score
    reasons.extend(pt_reasons)
    providers["phishtank"] = pt_meta

    result = {
        "score": min(score, 90),
        "reasons": reasons,
        "providers": providers,
    }
    cache[url] = result
    return result["score"], reasons, providers


def is_suspicious_domain(domain: str) -> bool:
    if not domain:
        return False

    normalized = domain.lower()
    if is_ip_host(normalized):
        return True

    if any(pattern in normalized for pattern in SUSPICIOUS_DOMAIN_PATTERNS):
        return True

    base = base_domain(normalized)
    if base in SHORTENER_DOMAINS:
        return True

    return False


def analyze_single_url(
    url: str,
    sender_domain: str,
    context_text: str,
    redirect_cache: dict[str, dict[str, Any]],
    intel_cache: dict[str, dict[str, Any]],
    domain_age_cache: dict[str, int | None],
) -> dict[str, Any]:
    try:
        canonical, host, port, raw_host = canonicalize_url(url)
    except Exception as err:
        return {
            "url": url,
            "risk_score": 0,
            "reasons": [f"URL parse error: {err}"],
        }

    score = 0
    reasons: list[str] = []

    split = urllib.parse.urlsplit(canonical)
    host_base = base_domain(host)
    sender_base = base_domain(sender_domain)
    raw_host_lower = (raw_host or "").lower()
    path_query = f"{split.path} {split.query}".lower()

    if split.username or split.password:
        score += 15
        reasons.append("URL contains embedded credentials")

    if is_ip_host(host):
        score += 35
        reasons.append("Link host is an IP address")

    if host_base in SHORTENER_DOMAINS:
        score += 25
        reasons.append(f"Shortened URL domain: {host_base}")

    if split.scheme != "https":
        if any(token in path_query for token in LIKELY_LOGIN_TOKENS):
            score += 20
            reasons.append("Non-HTTPS URL with login/account-like path")
        else:
            score += 8
            reasons.append("Non-HTTPS URL")

    if port and port not in {80, 443}:
        score += 15
        reasons.append(f"Unusual URL port: {port}")

    if "xn--" in host or any(ord(char) > 127 for char in raw_host_lower):
        score += 30
        reasons.append("Potential IDN homograph domain")

    typos = detect_typosquat(host)
    if typos:
        score += 30
        reasons.append(f"Potential typosquat impersonation: {', '.join(typos[:2])}")

    tld = host.split(".")[-1] if "." in host else host
    if tld in SUSPICIOUS_TLDS:
        score += 10
        reasons.append(f"High-risk top-level domain: .{tld}")

    if sender_base and host_base and sender_base != host_base and host_base not in TRACKING_DOMAINS:
        sender_is_brand = any(sender_base.endswith(domain) for domain in LEGITIMATE_DOMAINS) or any(
            brand in sender_base for brand in BRAND_NAMES
        )
        brand_mentioned = any(brand in context_text.lower() for brand in BRAND_NAMES)
        if sender_is_brand or brand_mentioned:
            score += 15
            reasons.append(f"Sender/link domain mismatch: {sender_base} -> {host_base}")

    if is_suspicious_domain(host):
        score += 15
        reasons.append(f"Suspicious domain pattern: {host}")

    digit_ratio = (sum(char.isdigit() for char in host) / max(1, len(host)))
    if digit_ratio >= 0.25:
        score += 8
        reasons.append("Domain has unusually high numeric content")
    if host.count("-") >= 3:
        score += 8
        reasons.append("Domain has excessive hyphen usage")
    if len(host) >= 35:
        score += 8
        reasons.append("Domain length unusually long")

    chain, final_url, redirect_error = follow_redirect_chain(canonical, redirect_cache)
    final_host = host
    try:
        _, final_host, _, _ = canonicalize_url(final_url)
    except Exception:
        pass
    if final_host and base_domain(final_host) != host_base:
        score += 10
        reasons.append(f"Redirects to different domain: {base_domain(final_host)}")
    if redirect_error:
        reasons.append(f"Redirect probe error: {redirect_error}")

    intel_score, intel_reasons, intel_providers = threat_intel_score(canonical, intel_cache)
    score += intel_score
    reasons.extend(intel_reasons)

    age_days = get_domain_age_days(final_host or host, domain_age_cache)
    if age_days is not None:
        if age_days <= 30:
            score += 35
            reasons.append(f"Very new domain ({age_days} days old)")
        elif age_days <= 90:
            score += 20
            reasons.append(f"New domain ({age_days} days old)")
        elif age_days <= 180:
            score += 10
            reasons.append(f"Young domain ({age_days} days old)")

    return {
        "url": url,
        "canonical_url": canonical,
        "domain": host,
        "base_domain": host_base,
        "final_url": final_url,
        "final_domain": final_host,
        "redirect_chain": chain,
        "domain_age_days": age_days,
        "risk_score": min(score, 100),
        "reasons": sorted(set(reasons)),
        "threat_intel": intel_providers,
    }


def score_email(
    sender: str,
    subject: str,
    snippet: str,
    full_text: str,
    urls: list[str],
    redirect_cache: dict[str, dict[str, Any]],
    intel_cache: dict[str, dict[str, Any]],
    domain_age_cache: dict[str, int | None],
) -> tuple[int, list[str], list[dict[str, Any]]]:
    score = 0
    reasons: list[str] = []
    sender_domain = extract_domain(sender)
    content = f"{subject or ''} {snippet or ''} {full_text or ''}".lower()

    if is_suspicious_domain(sender_domain):
        score += 30
        reasons.append(f"Suspicious sender domain: {sender_domain}")

    urgent_count = sum(1 for kw in URGENT_KEYWORDS if kw in content)
    if urgent_count:
        score += min(urgent_count * 15, 40)
        reasons.append(f"Urgency language detected ({urgent_count})")

    sensitive_count = sum(1 for kw in SENSITIVE_REQUESTS if kw in content)
    if sensitive_count:
        score += min(sensitive_count * 20, 50)
        reasons.append(f"Sensitive data request ({sensitive_count})")

    threat_count = sum(1 for kw in THREAT_KEYWORDS if kw in content)
    if threat_count:
        score += min(threat_count * 25, 50)
        reasons.append(f"Threat language ({threat_count})")

    if any(greeting in content for greeting in ["dear customer", "dear user", "valued customer"]):
        score += 10
        reasons.append("Generic greeting")

    if "click here" in content or "verify now" in content:
        score += 15
        reasons.append("Suspicious call-to-action")

    link_findings = []
    high_risk_link_count = 0
    if urls:
        for url in urls[:MAX_URLS_PER_MESSAGE]:
            finding = analyze_single_url(
                url=url,
                sender_domain=sender_domain,
                context_text=content,
                redirect_cache=redirect_cache,
                intel_cache=intel_cache,
                domain_age_cache=domain_age_cache,
            )
            link_findings.append(finding)
            if finding.get("risk_score", 0) >= 45:
                high_risk_link_count += 1

        max_link_risk = max((item.get("risk_score", 0) for item in link_findings), default=0)
        aggregate_link_score = max_link_risk
        if high_risk_link_count >= 2:
            aggregate_link_score += 10
            reasons.append("Multiple high-risk links detected")
        score += min(aggregate_link_score, 70)

        highest_link = max(link_findings, key=lambda item: item.get("risk_score", 0))
        if highest_link.get("risk_score", 0) >= 35:
            reasons.append(
                f"Highest-risk link {highest_link.get('base_domain', highest_link.get('domain', 'unknown'))}"
                f" scored {highest_link.get('risk_score', 0)}"
            )

    return min(score, 100), sorted(set(reasons)), link_findings


def header_value(headers: list[dict[str, str]], name: str) -> str:
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def list_message_ids(service, query: str, limit: int) -> list[str]:
    ids: list[str] = []
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


def extract_message_content(payload: dict[str, Any]) -> tuple[str, str]:
    plain_parts: list[str] = []
    html_parts: list[str] = []

    def walk(part: dict[str, Any]):
        mime = (part.get("mimeType") or "").lower()
        body = part.get("body", {}) or {}
        data = body.get("data")
        if data:
            text = decode_urlsafe_b64(data)
            if mime == "text/plain":
                plain_parts.append(text)
            elif mime == "text/html":
                html_parts.append(text)
            elif not part.get("parts"):
                plain_parts.append(text)
        for child in part.get("parts", []) or []:
            if isinstance(child, dict):
                walk(child)

    walk(payload or {})
    return "\n".join(plain_parts), "\n".join(html_parts)


def get_message_analysis_data(service, message_id: str) -> dict[str, Any]:
    message = service.users().messages().get(
        userId="me",
        id=message_id,
        format="full",
    ).execute()

    headers = message.get("payload", {}).get("headers", [])
    sender = header_value(headers, "From")
    subject = header_value(headers, "Subject")
    date_value = header_value(headers, "Date")
    snippet = message.get("snippet", "")[:200]

    plain_text, html_text = extract_message_content(message.get("payload", {}))
    body_text = normalize_whitespace(f"{plain_text} {strip_html(html_text)}")

    urls = sorted(
        set()
        .union(extract_urls_from_text(plain_text))
        .union(extract_urls_from_html(html_text))
        .union(extract_urls_from_text(snippet))
    )

    return {
        "id": message_id,
        "sender": sender,
        "subject": subject,
        "date": date_value,
        "snippet": snippet,
        "body_text": body_text[:4000],
        "urls": urls,
    }


def get_message_metadata(service, message_id: str) -> dict[str, Any]:
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
        "snippet": message.get("snippet", "")[:200],
    }


def move_to_trash(service, message_ids: list[str], dry_run: bool) -> int:
    if dry_run or not message_ids:
        return 0
    moved = 0
    for index in range(0, len(message_ids), 1000):
        batch = message_ids[index:index + 1000]
        service.users().messages().batchModify(
            userId="me",
            body={"ids": batch, "addLabelIds": ["TRASH"]},
        ).execute()
        moved += len(batch)
    return moved


def send_report_email(service, recipient: str, report: dict[str, Any]) -> str:
    summary = report["summary"]
    moved_messages = report.get("moved_messages", []) or []
    subject = "Gmail Daily Security Cleanup Report"

    moved_lines = []
    if moved_messages:
        moved_lines.append("Moved/Selected messages (From | Subject):")
        for index, item in enumerate(moved_messages, start=1):
            source = item.get("source", "unknown")
            sender = normalize_whitespace(item.get("sender", "")) or "(unknown sender)"
            msg_subject = normalize_whitespace(item.get("subject", "")) or "(no subject)"
            moved_lines.append(f"{index}. [{source}] {sender} | {msg_subject}")
    else:
        moved_lines.append("No messages were selected for trash action.")

    body = (
        "Your Gmail security cleanup completed.\n\n"
        f"Timestamp: {report['timestamp']}\n"
        f"Dry run: {report['dry_run']}\n"
        f"Inbox scanned: {summary['inbox_scanned']}\n"
        f"Suspicious detected: {summary['suspicious_detected']}\n"
        f"High-risk detected: {summary['high_risk_detected']}\n"
        f"Messages with URLs: {summary['messages_with_urls']}\n"
        f"Messages with high-risk links: {summary['messages_with_high_risk_links']}\n"
        f"Spam detected: {summary['spam_detected']}\n"
        f"Unique messages selected: {summary['unique_messages_selected']}\n"
        f"Moved to Trash: {summary['unique_messages_moved_to_trash']}\n\n"
        + "\n".join(moved_lines)
        + "\n\nAttached: moved_messages.csv and full JSON report."
    )

    message = MIMEMultipart()
    message["To"] = recipient
    message["From"] = recipient
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(["id", "source", "from", "subject", "date", "risk_score"])
    for item in moved_messages:
        writer.writerow(
            [
                item.get("id", ""),
                item.get("source", ""),
                item.get("sender", ""),
                item.get("subject", ""),
                item.get("date", ""),
                item.get("risk_score", ""),
            ]
        )
    csv_attachment = MIMEBase("text", "csv")
    csv_attachment.set_payload(csv_buffer.getvalue().encode("utf-8"))
    encoders.encode_base64(csv_attachment)
    csv_attachment.add_header(
        "Content-Disposition",
        f'attachment; filename="moved_messages_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.csv"',
    )
    message.attach(csv_attachment)

    report_json = json.dumps(report, indent=2).encode("utf-8")
    attachment = MIMEBase("application", "json")
    attachment.set_payload(report_json)
    encoders.encode_base64(attachment)
    attachment.add_header(
        "Content-Disposition",
        f'attachment; filename="phishing_spam_cleanup_report_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.json"',
    )
    message.attach(attachment)

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    response = service.users().messages().send(userId="me", body={"raw": raw_message}).execute()
    return response.get("id", "")


def run_cleanup(
    dry_run: bool = False,
    max_inbox: int = 500,
    max_spam: int = 500,
    high_risk_threshold: int = 70,
    spam_older_than_days: int = 7,
    recipient: str | None = None,
) -> dict[str, Any]:
    service = get_gmail_service()

    redirect_cache: dict[str, dict[str, Any]] = {}
    intel_cache: dict[str, dict[str, Any]] = {}
    domain_age_cache: dict[str, int | None] = {}

    inbox_ids = list_message_ids(service, "in:inbox", max_inbox)
    suspicious: list[dict[str, Any]] = []
    high_risk: list[dict[str, Any]] = []
    messages_with_urls = 0
    messages_with_high_risk_links = 0

    for index, message_id in enumerate(inbox_ids, start=1):
        if index % 50 == 0:
            print(f"Processed {index}/{len(inbox_ids)} inbox messages")

        try:
            metadata = get_message_analysis_data(service, message_id)
            risk_score, reasons, link_findings = score_email(
                sender=metadata["sender"],
                subject=metadata["subject"],
                snippet=metadata["snippet"],
                full_text=metadata["body_text"],
                urls=metadata["urls"],
                redirect_cache=redirect_cache,
                intel_cache=intel_cache,
                domain_age_cache=domain_age_cache,
            )

            if metadata["urls"]:
                messages_with_urls += 1
            if any(item.get("risk_score", 0) >= 45 for item in link_findings):
                messages_with_high_risk_links += 1

            if risk_score >= 40:
                entry = {
                    "id": metadata["id"],
                    "sender": metadata["sender"],
                    "subject": metadata["subject"],
                    "date": metadata["date"],
                    "snippet": metadata["snippet"],
                    "risk_score": risk_score,
                    "reasons": reasons,
                    "urls": metadata["urls"],
                    "link_findings": link_findings,
                }
                suspicious.append(entry)
                if risk_score >= high_risk_threshold:
                    high_risk.append(entry)
        except Exception as error:
            suspicious.append({"id": message_id, "risk_score": -1, "error": str(error)})

    suspicious.sort(key=lambda item: item.get("risk_score", 0), reverse=True)
    high_risk.sort(key=lambda item: item.get("risk_score", 0), reverse=True)

    spam_query = f"in:spam older_than:{spam_older_than_days}d"
    spam_ids = list_message_ids(service, spam_query, max_spam)
    spam_messages: list[dict[str, Any]] = []
    for message_id in spam_ids:
        try:
            spam_messages.append(get_message_metadata(service, message_id))
        except Exception as error:
            spam_messages.append({"id": message_id, "error": str(error)})

    selected_ids = list(dict.fromkeys([item["id"] for item in high_risk if "id" in item] + spam_ids))
    selected_by_id: dict[str, dict[str, Any]] = {}
    for item in high_risk:
        message_id = item.get("id")
        if not message_id:
            continue
        selected_by_id[message_id] = {
            "id": message_id,
            "source": "high_risk",
            "sender": item.get("sender", ""),
            "subject": item.get("subject", ""),
            "date": item.get("date", ""),
            "risk_score": item.get("risk_score"),
        }
    for item in spam_messages:
        message_id = item.get("id")
        if not message_id or message_id in selected_by_id:
            continue
        selected_by_id[message_id] = {
            "id": message_id,
            "source": "spam_old",
            "sender": item.get("sender", ""),
            "subject": item.get("subject", ""),
            "date": item.get("date", ""),
            "risk_score": "",
        }
    moved_messages = [
        selected_by_id.get(
            message_id,
            {
                "id": message_id,
                "source": "unknown",
                "sender": "",
                "subject": "",
                "date": "",
                "risk_score": "",
            },
        )
        for message_id in selected_ids
    ]
    moved = move_to_trash(service, selected_ids, dry_run=dry_run)

    report = {
        "timestamp": datetime.now().isoformat(),
        "dry_run": dry_run,
        "config": {
            "max_inbox": max_inbox,
            "max_spam": max_spam,
            "high_risk_threshold": high_risk_threshold,
            "spam_older_than_days": spam_older_than_days,
            "threat_intel": {
                "safe_browsing_enabled": bool(os.environ.get("SAFE_BROWSING_API_KEY")),
                "virustotal_enabled": bool(os.environ.get("VIRUSTOTAL_API_KEY")),
                "phishtank_enabled": bool(os.environ.get("PHISHTANK_API_KEY")),
                "whoisxml_enabled": bool(os.environ.get("WHOISXML_API_KEY")),
                "urlhaus_enabled": True,
            },
        },
        "summary": {
            "inbox_scanned": len(inbox_ids),
            "suspicious_detected": len([item for item in suspicious if item.get("risk_score", 0) >= 40]),
            "high_risk_detected": len([item for item in high_risk if item.get("risk_score", 0) >= high_risk_threshold]),
            "messages_with_urls": messages_with_urls,
            "messages_with_high_risk_links": messages_with_high_risk_links,
            "spam_detected": len(spam_ids),
            "unique_messages_selected": len(selected_ids),
            "unique_messages_moved_to_trash": moved,
        },
        "high_risk_messages": high_risk,
        "spam_messages": spam_messages,
        "moved_messages": moved_messages,
    }

    if recipient is None:
        profile = service.users().getProfile(userId="me").execute()
        recipient = profile.get("emailAddress")

    message_id = send_report_email(service, recipient, report)
    report["email"] = {"recipient": recipient, "message_id": message_id}

    print(json.dumps(report["summary"]))
    print(f"EMAIL_RECIPIENT={recipient}")
    print(f"EMAIL_MESSAGE_ID={message_id}")
    return report


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("gmail-token")],
    schedule=modal.Cron("0 13 * * *"),  # Daily, 13:00 UTC (8:00 AM ET standard time)
    timeout=1200,
)
def run_daily_cleanup():
    return run_cleanup(
        dry_run=False,
        max_inbox=120,
        max_spam=120,
    )


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("gmail-token")],
    timeout=3600,
)
def run_now(
    dry_run: bool = False,
    max_inbox: int = 500,
    max_spam: int = 500,
    high_risk_threshold: int = 70,
    spam_older_than_days: int = 7,
):
    return run_cleanup(
        dry_run=dry_run,
        max_inbox=max_inbox,
        max_spam=max_spam,
        high_risk_threshold=high_risk_threshold,
        spam_older_than_days=spam_older_than_days,
    )


@app.local_entrypoint()
def main(dry_run: bool = False):
    result = run_now.remote(dry_run=dry_run)
    print(json.dumps(result.get("summary", {}), indent=2))
