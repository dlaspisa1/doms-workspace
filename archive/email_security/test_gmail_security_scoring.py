"""Regression suite for the Gmail security cleanup scorer.

Run:  python3 execution/test_gmail_security_scoring.py

Every case here exists because something was scored wrong in production. The legitimate-mail
cases guard against auto-trashing real mail; the adversarial cases guard against the opposite
failure, where a fix aimed at false positives quietly disarms phishing detection. Both halves
must stay green -- a previous "fix" passed every legitimate case while silently dropping raw-IP
phishing to 63 and shortener phishing to 40, both under the trash line.

No network access: redirect/intel/domain-age caches are pre-seeded per case.
"""
import importlib.util
import sys
import types

# Stub `modal` so the scorer imports without the SDK or an app context.
_m = types.ModuleType("modal")


class _Image:
    def pip_install(self, *a, **k):
        return self


class _App:
    def __init__(self, *a, **k):
        pass

    def function(self, *a, **k):
        return lambda f: f

    def local_entrypoint(self, *a, **k):
        return lambda f: f


_m.App = _App
_m.Image = types.SimpleNamespace(debian_slim=lambda *a, **k: _Image())
_m.Secret = types.SimpleNamespace(from_name=lambda *a, **k: None)
_m.Cron = lambda *a, **k: None
sys.modules["modal"] = _m

_spec = importlib.util.spec_from_file_location(
    "gsc", __file__.replace("test_gmail_security_scoring.py", "modal_gmail_security_cleanup.py")
)
g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g)

TRASH = g.DEFAULT_HIGH_RISK_THRESHOLD   # >= this is auto-trashed
REPORT = 40                             # >= this appears in the report at all

PHISH = (
    "Dear customer, we detected unusual activity. Your account has been suspended. Verify your "
    "account now to avoid legal action and a penalty. Click here to confirm your identity and "
    "update your payment: enter your password, social security number, credit card and routing "
    "number immediately. Final notice - act now or account locked."
)
BILL = (
    "Dear LIMITLESS AZ LLC, thank you for your payment. Your account number ending 4471 has been "
    "updated. Failure to pay by the due date may result in a penalty. Update your payment method "
    "or verify your information in the customer portal."
)
NEWS = (
    "Crypto markets update: $14.3B has been lost to hacks this year. Final thoughts on what "
    "comes next, plus our security checklist for protecting your account number and password."
)


def dkim(domain):
    return f"mx.google.com; dkim=pass header.i=@{domain}; dmarc=pass header.from={domain}"


def score(sender, body, urls, auth="", final=None, ages=None):
    """final: {url: final_url} to simulate a redirect. ages: {registrable_domain: age_days}."""
    final = final or {}
    ages = ages or {}
    rc, ic, ac = {}, {}, {}
    for u in urls:
        c, h, _, _ = g.canonicalize_url(u)
        dest = final.get(u, c)
        rc[c] = {"chain": [c, dest], "final_url": dest, "error": None}
        ic[c] = {"score": 0, "reasons": [], "providers": {}}
        for d in (h, g.canonicalize_url(dest)[1]):
            ac.setdefault(g.base_domain(d), None)
    for d, age in ages.items():
        ac[d] = age
    ac.setdefault(g.base_domain(g.extract_domain(sender)), None)
    s, _, _ = g.score_email(
        sender=sender, subject="", snippet=body[:120], full_text=body, urls=urls,
        redirect_cache=rc, intel_cache=ic, domain_age_cache=ac,
        auto_trash_threshold=TRASH, auth_results=auth,
    )
    return s


def outcome(s):
    return "TRASH" if s >= TRASH else ("flag" if s >= REPORT else "ignore")


CASES = []


def case(name, want, s):
    CASES.append((outcome(s) == want, name, s, outcome(s), want))


# --- Legitimate mail: must be IGNORED entirely, not merely spared from trashing -------------
case("Utility bill, authenticated, portal link", "ignore",
     score("Billing <no-reply@invoicecloud.net>", BILL,
           ["https://www.invoicecloud.com/portal/login.aspx"], dkim("invoicecloud.net")))
case("Utility bill + '-update' ESP subdomain", "ignore",
     score("Billing <no-reply@invoicecloud.net>", BILL,
           ["https://click.account-updates.espmailer.com/x/abc"], dkim("invoicecloud.net")))
case("Crypto newsletter w/ bit.ly (CoinGecko shape)", "ignore",
     score("CoinGecko <hello@coingecko.com>", NEWS,
           ["https://bit.ly/3xAbCdE"], dkim("coingecko.com")))
case("School newsletter, tracker -> social sites", "ignore",
     score("Todd <t@areteprepacademy.org>", "Upcoming events. Final notice for signups. Penalty box.",
           ["http://track.spe.schoolmessenger.com/f/a/xyz"], dkim("areteprepacademy.org"),
           final={"http://track.spe.schoolmessenger.com/f/a/xyz": "https://www.facebook.com/school"}))
case("Marketing mail via aweber tracker", "ignore",
     score("Kevin <kevink@amzmarketer.com>", "Your inventory dashboard is lying to you. Penalty.",
           ["https://clicks.aweber.com/y/ct/?l=AbCd"], dkim("amzmarketer.com"),
           final={"https://clicks.aweber.com/y/ct/?l=AbCd": "https://atomic-one.com/post"}))
case("XML namespace URI is not a link", "ignore",
     score("News <news@e.retailer.com>", "This week's deals. Unsubscribe anytime.",
           ["http://www.w3.org/1999/xhtml"], dkim("e.retailer.com")))

# --- Adversarial: must still be TRASHED ------------------------------------------------------
case("Phishing .tk spoof + fake login, no auth", "TRASH",
     score("PayPal <alert@paypal-verify-secure.tk>", PHISH,
           ["http://paypal-secure-login.tk/signin/verify?account=1"]))
case("Phishing .tk spoof, self-signed DKIM", "TRASH",
     score("PayPal <alert@paypal-verify-secure.tk>", PHISH,
           ["http://paypal-secure-login.tk/signin/verify?account=1"],
           dkim("paypal-verify-secure.tk")))
case("Raw-IP login link, self-signed DKIM", "TRASH",
     score("Security <no-reply@evil-host.com>", PHISH,
           ["http://192.0.2.44/paypal/login?verify=1"], dkim("evil-host.com")))
case("Spoofed From, DKIM aligned only to attacker", "TRASH",
     score("PayPal <service@paypal.com>", PHISH,
           ["http://paypal-secure-login.tk/signin/verify?account=1"],
           "mx.google.com; dkim=pass header.i=@totally-other.tk; spf=fail"))
case("Shortener resolving to a brand-new domain", "TRASH",
     score("Alerts <a@notify.example.com>", PHISH, ["https://bit.ly/3xAbCdE"],
           dkim("notify.example.com"),
           final={"https://bit.ly/3xAbCdE": "https://secure-wallet-verify.top/login"},
           ages={"secure-wallet-verify.top": 3}))
case("Typosquat brand domain", "TRASH",
     score("Apple <no-reply@app1e-support.com>", PHISH,
           ["https://app1e-support.com/verify/account"], dkim("app1e-support.com")))

w = max(len(c[1]) for c in CASES)
print(f"\n{'':2} {'case'.ljust(w)}  score  got     want")
print("-" * (w + 28))
for ok, name, s, got, want in CASES:
    print(f"{'ok' if ok else 'XX'} {name.ljust(w)}  {str(s).rjust(5)}  {got.ljust(6)}  {want}")
failed = [c for c in CASES if not c[0]]
print(f"\n{len(CASES) - len(failed)}/{len(CASES)} passed" + ("" if not failed else "  *** FAILURES ***"))
sys.exit(1 if failed else 0)
