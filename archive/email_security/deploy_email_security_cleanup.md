# Deploy Email Security Cleanup to a New Mailbox

## Goal

Stand up the phishing/spam cleanup robot on a mailbox other than `dlaspisa1@gmail.com` —
specifically the business accounts (EC Brandz, Googipet) — without repeating the false-positive
incident that the personal deployment went through.

The reference implementation is `execution/modal_gmail_security_cleanup.py`. Copy it and adapt;
do not rewrite the scorer from scratch. Its scoring rules encode a live incident and several
adversarial fixes that are not obvious from reading the code cold.

## Inputs

| Input | Example | Notes |
|-------|---------|-------|
| Target mailbox | `dominick@googipet.com` | The address the robot acts on |
| Modal profile/workspace | `dominick-65380` | Where the app is deployed |
| Modal secret name | `gmail-token-googipet` | **Must be distinct per mailbox** |
| Report recipient | usually the mailbox itself | Where the daily report is emailed |
| Auto-trash threshold | 70 | Leave alone unless you re-run the live scan |

## Tools/Scripts

- `execution/modal_gmail_security_cleanup.py` — reference implementation (personal account)
- Copy to `execution/modal_email_security_<account>.py`, change `modal.App("...")` name and the
  secret name. Two apps must never share an app name or they overwrite each other.

## Process

### 1. Pre-flight (do this before writing any code)

1. `modal profile list` — note which profile is active **before** you start. Switching is global
   and silently breaks other workspaces on this machine. Restore it when done.
2. **Verify the secret opens the mailbox you think it does.** Do not infer from the secret's name.
   Run a throwaway read-only Modal function that calls
   `service.users().getProfile(userId="me")` and prints `emailAddress` and the granted scopes.
   Requires `gmail.modify` to move mail. A correctly-named secret pointing at the wrong mailbox is
   the most expensive mistake available here — verified 2026-08-10 that `gmail-token` exists in
   BOTH `dlaspisa1` and `dominick-65380` and both open `dlaspisa1@gmail.com`.
3. Confirm nothing is already deployed against that mailbox. Two schedulers on one inbox will
   double-act.

### 2. Adapt the scorer

Keep the safety model intact (see **Scoring safety model** below). Business mail differs from
personal in ways that matter:

- **Business email compromise (BEC) is the real threat**, not consumer phishing. Wire-transfer
  requests, changed bank details, invoice redirects, and vendor-impersonation from lookalike
  domains. Consider adding: display-name impersonation of internal staff from an external domain,
  and reply-to that differs from From.
- Business inboxes carry far more legitimate invoice/payment vocabulary. The content/technical
  split matters MORE here, not less.
- Do not port the personal `LEGITIMATE_DOMAINS` / `BRAND_NAMES` lists unchanged — add the
  business's real vendors, and its own domains.

### 3. Rollout — do not skip

1. Deploy with `dry_run=True`.
2. **Run the finished scorer across the whole live inbox** at the same message cap the cron uses,
   and produce a list of exactly what would be trashed and what flagged, with the reasons that
   fired.
3. Show that list to the user and get explicit approval before setting `dry_run=False`.
   Enabling moving is the user's call, not the agent's.
4. If the list contains anything worth keeping, the scorer is not done.

### 4. Post-deploy

- Read the first week of report emails. The `moved_messages` JSON attachment lists everything
  moved with `source` (`high_risk` vs `spam_old`) and the score.
- Restore anything wrongly trashed within Gmail's 30-day Trash window.

## Scoring safety model — do not weaken

Full rationale in `directives/cleanup_gmail_inbox.md`. Summary of the invariants:

1. **Split the score.** `content_score` = language only (urgency, sensitive-data asks, threat
   words). `technical_score` = infrastructure evidence (spoofed sender domain, IP-address link
   host, typosquat, shortener, threat-intel hit, new domain).
2. **`CONTENT_ONLY_CAP = 55`** — language alone may flag for review, never auto-trash.
3. **`TECHNICAL_EVIDENCE_FLOOR = 25`** — auto-trash requires technical evidence of real strength,
   not merely nonzero. A binary `technical_score > 0` gate lets 15 points of hostname trivia
   unlock the full content range.
4. **Judge the registrable domain**, not the full hostname, for every structural heuristic and
   substring match. ESP click-tracking subdomains are long, hashed, and often contain `-update` /
   `-secure` in a subdomain the sender never chose.
5. **Redirect-to-sender is normal.** Only flag redirects landing somewhere unrelated to both the
   link domain and the sender domain.
6. **Sender authentication suppresses language scoring — and only that.** Accept `dmarc=pass` with
   aligned `header.from`, or `dkim=pass` whose `header.i` aligns with the From: domain (compare
   registrable domains). Apply ONLY when technical evidence is already below the floor. A valid
   signature proves "this domain sent this", not "this domain is trustworthy".
7. **Never score ESP/tracking infrastructure as attack evidence.** This caused a second round of
   wrongful trashing (2026-08-25). Specifically: do not scrape XML namespace URIs out of raw HTML
   and treat them as links; do not count a shortener twice; do not treat a redirect to a mainstream
   site (twitter/facebook/instagram/outlook) as an attacker bounce; and do not apply sender/link
   domain mismatch to authenticated senders, whose choice of mail vendor is their own. Weight
   shorteners below the evidence floor for authenticated senders — the redirect chain resolves the
   destination and scores it on domain age and threat intel, which is the real protection.

**Never add a language/keyword signal to `technical_score`** — it silently re-enables keyword-only
auto-trash.

## Reference implementation and test suite

Copy these rather than rebuilding from this description — they encode fixes that are not obvious:

- `/Users/dominicklaspisa/Doms workspace/execution/modal_gmail_security_cleanup.py`
- `/Users/dominicklaspisa/Doms workspace/execution/test_gmail_security_scoring.py`

The test suite runs offline (caches are pre-seeded, no network) and must stay 12/12 green.

## Verification — required before declaring success

Use real full message bodies pulled from the live mailbox, never snippets. Report actual scores
and the outcome (ignored / flagged / trashed) for each:

- Legitimate invoices and vendor mail using alarming billing language → **ignored**, not merely
  spared from trashing.
- The same, with an ESP tracking hostname containing `-update` → still ignored.
- Synthetic phishing: lookalike sender on a high-risk TLD + fake login link → trashed.
- The same phishing **DKIM-signed by its own domain** → still trashed.
- Raw-IP link phishing, DKIM-signed → still trashed.
- URL-shortener phishing with threat language, DKIM-signed → still trashed.
- Spoofed From: whose DKIM aligns only to an unrelated domain → trashed.
- Benign newsletter → ignored.

The adversarial half is the half that catches real regressions. A draft that zeroed language
unconditionally passed every legitimate-mail test while silently dropping raw-IP phishing to 63
and shortener phishing to 40 — both under the trash line.

## Outputs

- Deployed Modal app, one per mailbox, distinct app + secret names
- Daily report email with a JSON attachment listing every moved message
- A short note to the user: what is deployed, which workspace, which mode, what schedule

## Edge Cases

1. **Spam folder handling.** The job also trashes `in:spam older_than:7d`. That only empties what
   Gmail already classified as spam — it does not classify anything itself. Expect 30–50
   messages/day on a busy account; this is normal and is NOT the robot judging that mail.
2. **Autoresponders score high.** "Thank you for your email", out-of-office, and "we received your
   request" replies use sensitive/urgent vocabulary and get flagged. Check `Auto-Submitted:
   auto-replied` and `Precedence: bulk` before treating one as a false positive worth restoring.
3. **The robot flags its own report email** (it quotes threat vocabulary). Exclude self-sent
   reports by sender+subject, or accept the daily noise.
4. **Newsletters with finance/crypto vocabulary** (CoinGecko, market digests) are the most common
   remaining false positive on the personal account — they combine tracking links with threat
   words ("hacks", "lost", "final"). Watch for these on business accounts too.
5. **Read-only Gmail connectors cannot untrash.** Recovery needs an OAuth token with
   `gmail.modify` and
   `messages().modify(removeLabelIds=["TRASH"], addLabelIds=["INBOX"])`, which preserves other
   labels such as UNREAD.
6. **Google Workspace accounts** may require admin consent or a service account with domain-wide
   delegation rather than a personal OAuth flow. Confirm before assuming the personal token
   approach transfers.
7. **Trash retention is 30 days.** Mistakes are only recoverable inside that window — say so in
   the report email.

## Learnings

- 2026-08-06/07: the personal deployment auto-trashed a financial summary and two utility-bill
  payment confirmations. Root causes were keyword-only scoring, full-hostname structural
  heuristics, and penalizing redirect-to-sender. See `directives/cleanup_gmail_inbox.md`.
- 2026-08-10: went live after a clean full-inbox scan (0 trashable).
- 2026-08-25 review of 15 days live: false-positive rate dropped from ~24/day flagged to 1–6/day,
  but the job still auto-trashed 5 legitimate messages over that period (2 CoinGecko newsletters,
  a school newsletter, a marketing newsletter, and one accountant autoresponder). **A clean
  one-day scan does not prove the scorer is safe** — mail arriving later crossed the line. Budget
  for a weekly review of the `high_risk` entries for at least the first month.
- Verify claims about who moved a message from the report JSON (`dry_run`,
  `unique_messages_moved_to_trash`, and `source=high_risk`), not from the fact that a message is
  sitting in Trash. The user may have trashed it themselves.
- 2026-08-25 tightening: fixed four defects that scored ESP/tracking infrastructure as attack
  evidence (XML namespace URIs scraped as links, shortener double-counting, redirect-to-social
  penalised, sender/link mismatch applied to authenticated senders). The five false positives went
  from 70-85 to 0-18, and a live 120-message scan went from 5 wrongful trashes to 0 trash / 1 flag.
  A permanent 12-case regression suite now guards both directions.

