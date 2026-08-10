# Gmail Inbox Cleanup

## Goal
Automatically clean up Gmail inbox by intelligently categorizing emails into existing folders, archiving old messages (9+ months), and removing promotional content.

## Inputs
- **days_to_archive**: Number of days old before archiving (default: 270 = 9 months)
- **max_messages_to_categorize**: Maximum messages to analyze per run (default: 1000)
- **max_messages_for_duplicate_check**: Maximum messages to check for duplicates (default: 2000)
- **promotional_keywords**: List of keywords to identify promotional emails (default: ["unsubscribe", "promotional", "newsletter", "marketing"])
- **enable_duplicate_detection**: Enable/disable duplicate detection (default: true)
- **dry_run**: Boolean to preview actions without executing (default: true)

## Tools/Scripts
- `execution/gmail_cleanup_smart.py` - Smart cleanup script with intelligent categorization and duplicate detection
- `execution/gmail_cleanup.py` - Basic cleanup script (legacy)
- `execution/gmail_security_cleanup.py` - Phishing/spam security cleanup with JSON + email report
- `execution/gmail_auth.py` - Gmail OAuth authentication
- `execution/list_gmail_labels.py` - List all existing Gmail labels
- `execution/setup_weekly_automation.sh` - Setup weekly cron job for automatic cleanup
- `execution/remove_weekly_automation.sh` - Remove weekly cron job automation
- `execution/setup_weekly_security_automation.sh` - Setup weekly cron for security cleanup/report
- `execution/remove_weekly_security_automation.sh` - Remove weekly security cleanup cron
- Google Gmail API credentials (credentials.json)

## Process
1. **Authentication**: Use OAuth2 to authenticate with Gmail API
2. **Load Existing Labels**: Fetch all 142+ existing user labels/folders
3. **Smart Categorization**:
   - Analyze inbox messages (sender, subject, content snippet)
   - Match emails to existing folders using intelligent patterns:
     - Real Estate (mortgage, property, lease, rent)
     - Receipts (invoice, order confirmation, purchase)
     - Amazon (amazon.com, aws)
     - Medical (doctor, prescription, health)
     - Insurance (policy, claim, premium)
     - Travel & Leisure (booking, hotel, flight, itinerary)
     - Career (LinkedIn, job postings, applications)
     - Investments (vanguard, schwab, dividend, stock)
     - Income Taxes (IRS, tax forms, returns)
     - And many more based on existing folder structure
   - Apply appropriate labels to categorized messages
   - Skip starred, important, or unread messages
4. **Duplicate Detection** (optional, enabled by default):
   - Analyze messages for duplicates based on signature (sender + subject + date)
   - Keep the first occurrence, archive subsequent duplicates
   - Skip starred, important, or unread messages
   - Log duplicate count
5. **Archive Old Messages**:
   - Query messages older than 9 months (270 days)
   - Skip starred, important, or unread messages
   - Archive (remove from inbox, keep in All Mail)
   - Log archived message count
6. **Delete Promotional Emails**:
   - Query for promotional category and keywords
   - Move to trash (30-day retention before permanent delete)
   - Skip starred messages
   - Log deleted message count

## Outputs
- **JSON log** in `.tmp/gmail_cleanup_YYYY-MM-DD.json` with:
  - Timestamp
  - Messages categorized count (by label)
  - Important emails skipped count
  - Duplicates archived count
  - Old messages archived count
  - Promotional emails deleted count
  - Errors (if any)
  - Dry run status
- **Console summary** of actions taken
- **Cron logs** (if automation enabled) in `.tmp/cron_logs/cleanup_YYYYMMDD_HHMMSS.log`

## Weekly Automation
To run the cleanup automatically every week:

1. **Setup**: Run `./execution/setup_weekly_automation.sh`
   - Adds cron job to run every Sunday at 2:00 AM
   - Logs saved to `.tmp/cron_logs/`
   - **Important**: Set `dry_run=False` in script before enabling automation

2. **Remove**: Run `./execution/remove_weekly_automation.sh`
   - Removes the cron job

3. **Monitor**: Check logs in `.tmp/cron_logs/` to review automated runs

## Weekly Security Automation
To run phishing/spam cleanup automatically every week with report email:

1. **Setup**: Run `./execution/setup_weekly_security_automation.sh`
   - Adds cron job to run every Sunday at 2:00 AM
   - Executes `execution/gmail_security_cleanup.py`
   - Sends a report email with attached JSON output
   - Logs saved to `.tmp/cron_logs/`

2. **Remove**: Run `./execution/remove_weekly_security_automation.sh`
   - Removes the security cron job

3. **Safety model**:
   - Inbox phishing/fraud scoring only moves high-risk messages to trash
   - Spam cleanup targets `in:spam older_than:7d`
   - Trash retention remains 30 days for recovery

   **Content vs. technical scoring (added 2026-08-07 after a false-positive incident).**
   "High-risk" alone is NOT a sufficient safety guarantee — how the score is *composed* is what
   makes auto-trash safe. `score_email()` keeps two separate tallies:

   - **content_score** — language only: urgency words, sensitive-data phrases, threat words,
     generic greetings, "click here". Ordinary bills, invoices, payment confirmations and
     financial summaries legitimately use ALL of this vocabulary.
   - **technical_score** — evidence about infrastructure: a spoofed-looking sender domain, a
     link that is genuinely dangerous (IP-address host, typosquat, shortener, threat-intel hit,
     freshly registered domain).

   Two rules gate auto-trash (constants at the top of the script):
   - `CONTENT_ONLY_CAP = 55` — when technical evidence is weak/absent, language score is capped
     at 55, below the 70 auto-trash line. **Language alone can flag for review but can never
     auto-trash.**
   - `TECHNICAL_EVIDENCE_FLOOR = 25` — a message is only *eligible* for auto-trash once technical
     signals reach 25. Below that, the total is clamped to `threshold - 1`. This exists because
     weak structural signals are worth only 8–15 points each and are common on legitimate mail;
     without the floor, 15 points of hostname trivia would unlock the full content range and
     re-open the exact failure this fixes.

   Corollary for anyone tuning the scorer: **never add a language/keyword signal to
   `technical_score`.** Doing so silently re-enables keyword-only auto-trash.

   **Sender authentication (added 2026-08-10).** Capping content at 55 stopped the wrongful
   trashing, but ordinary bills still sat in the report as permanent false positives. The scorer
   now reads the `Authentication-Results` header via `sender_is_authenticated()`, which accepts
   `dmarc=pass` with aligned `header.from`, or `dkim=pass` whose `header.i` signing domain matches
   the From: domain (compared on the registrable domain, so `send.cfosilvia.com` and
   `mg.invoicecloud.net` still align with their parent).

   The rule is deliberately narrow: **authentication only suppresses language scoring, and only
   when technical evidence is already below the floor.** A verified signature proves "this domain
   really sent this", NOT "this domain is trustworthy" — anyone can DKIM-sign a throwaway domain.
   So when a genuine red flag IS present (raw-IP link, shortener, typosquat, sender spoof),
   language counts in full and authentication buys nothing. That case is a compromised-but-
   authenticated account sending a malicious link, which is exactly what this job must catch.

   Verified adversarially: phishing that DKIM-signs its own `.tk` domain still scores 100 and is
   still trashed. An earlier draft that zeroed content unconditionally dropped raw-IP phishing to
   63 and shortener phishing to 40 — both below the trash line. Do not reintroduce that.

## Edge Cases
1. **Rate Limits**: Gmail API has quota limits (250 quota units/user/second)
   - Implement exponential backoff
   - Batch operations where possible (max 1000 messages per batch)
2. **Authentication Expiry**: Token refresh handled automatically by google-auth library
3. **Important Messages**: Never archive/delete:
   - Starred messages
   - Messages marked important
   - Unread messages (configurable)
4. **Duplicate Detection**: Uses signature (sender + subject + date-prefix)
   - May have false positives if sender resends exact same email on same day
   - Always keeps first occurrence, archives subsequent ones
5. **Label Creation**: Uses existing labels only (142 labels available)
6. **Undo**: Keep logs in `.tmp/` for reference; Gmail trash retention is 30 days
7. **Errors**: Continue processing on individual message errors, log failures
8. **Automation**: Cron requires `dry_run=False` to actually perform actions

## Learnings
- Always run with dry_run=true first to preview actions
- User has 142 existing labels with detailed folder hierarchy - use these instead of creating new ones
- Gmail's "category" system may already handle some promotional filtering
- Intelligent pattern matching works well for auto-categorization (sender domain, subject keywords, content snippets)
- 9-month archive period (270 days) is more appropriate for business/personal mixed inbox
- Never touch starred, important, or unread messages - these indicate user intent
- Batch operations in groups of 1000 messages to respect API limits
- Process messages in batches of 50 for progress updates during categorization
- Duplicate detection using sender+subject+date signature is effective but may have edge cases
- Weekly automation (Sunday 2 AM) provides good balance between keeping inbox clean and not overwhelming API
- Cron logs are essential for debugging automated runs
- Token refresh works automatically - no manual intervention needed for automation
- **2026-08-07 false-positive incident.** The daily job (`dry_run=False`, 13:00 UTC) auto-trashed
  three legitimate messages: a daily finance summary and two utility-bill payment confirmations.
  Three independent defects each let ordinary mail reach the 70 auto-trash line:
  1. Keyword-only scoring — normal bill vocabulary ("account number", "penalty") scored as
     phishing with zero technical red flags. Fixed by the content/technical split above.
  2. Structural link heuristics (digit ratio, hyphen count, length, suspicious-pattern list)
     judged the FULL hostname, so legitimate ESP click-tracking subdomains read as generated
     phishing domains. Fixed by judging `host_base` (registrable domain) instead — a spoofed
     domain is fake at the registrable level, which `host_base` still catches.
  3. A link redirecting back to the sender's own domain — the normal shape of click tracking —
     was scored as a risk signal. Fixed: only flag redirects landing somewhere unrelated to
     BOTH the link domain and the sender domain.
  Also note: a finance summary listing portfolio holdings mentions brand names (apple, amazon,
  coinbase...), which trips the sender/link brand-mismatch rule. The evidence floor contains it.
- Verify scorer changes against REAL message bodies pulled from the live inbox, not snippets —
  the false positives were only reproducible with full body text.
- The Gmail *connector* (MCP) is read-only and cannot untrash. To restore messages, use local
  `token.json` (has `gmail.modify`) with `messages().modify()`:
  `removeLabelIds=["TRASH"], addLabelIds=["INBOX"]`. Other labels (UNREAD etc.) are preserved.
