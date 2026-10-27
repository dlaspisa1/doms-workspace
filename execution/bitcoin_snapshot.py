"""
Bitcoin dashboard snapshot
==========================
Fetches Bitcoin data from free public APIs once and writes one JSON snapshot
for the claude.ai "Bitcoin Analytics Dashboard" artifact. Standalone: needs only
`requests` (and `pytrends` for Google Trends, optional).

Sources: CoinGecko (Kraken fallback), mempool.space, blockchain.info,
alternative.me Fear & Greed, Reddit r/Bitcoin, Blockchair, Google Trends.

Output (default .tmp/bitcoin_snapshot.json):
  {
    "fetched_at": "2026-10-27T17:42:10Z",
    "sources":    {"market": {"status": "ok", "note": "..."}, ...},
    "rows":       [{"kind": "metric", "key": "price", "value": 80621, ...}, ...]
  }

"rows" is what the artifact reads. Every row has a "kind":
  meta         fetched_at
  source       one per data source: status ok | fallback | partial | missing
  metric       a single number (key, value, source); optional text
  history      price/volume points (period 7d|30d|90d|1y, t in ms)
  hashrate     daily network hash rate (t in ms, ehs)
  block        last 6 blocks
  fng          30 days of Fear & Greed
  reddit       r/Bitcoin hot posts with a keyword mood
  wallet       top 100 addresses (Blockchair)
  trends       Google Trends weekly search interest for "bitcoin" (12 months)
  institution  reference estimates of institutional holdings (each with an as_of date)
  halving      reference table of past and next halvings
  s2f_ref      reference stock-to-flow values at each halving

A source that fails is recorded as "missing" and the run carries on.
Exit code 0 when anything was fetched, 3 when every live source failed
(usually no network), so a refresh never pushes an empty snapshot.

Run:
  pip install requests pytrends      # once
  python execution/bitcoin_snapshot.py            # writes .tmp/bitcoin_snapshot.json
  python execution/bitcoin_snapshot.py --out other.json
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "bitcoin-dashboard/1.0"}
KRAKEN = "https://api.kraken.com/0/public"


# ── Fetchers (standalone; only needs `requests`, plus optional `pytrends`) ─────
# Each returns parsed JSON, or an empty value ({} / [] / None) when its call fails,
# so one dead API never stops the run.

def _get(url, params=None, timeout=15):
    r = requests.get(url, params=params, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r


def _kraken_ohlc(interval):
    """Kraken XBT/USD candles as (ms, close). interval in minutes: 60 hourly (30 days), 1440 daily (~720 days)."""
    j = _get(f"{KRAKEN}/OHLC", {"pair": "XBTUSD", "interval": interval}).json()
    if j.get("error"):
        raise RuntimeError(f"Kraken: {j['error']}")
    res = j.get("result", {})
    key = next(k for k in res if k != "last")
    return [(int(c[0]) * 1000, float(c[4])) for c in res[key]]


def _kraken_current():
    """CoinGecko-shaped market_data from Kraken. Market cap, global volume, supply and ATH aren't available (0)."""
    j = _get(f"{KRAKEN}/Ticker", {"pair": "XBTUSD"}).json()
    if j.get("error"):
        raise RuntimeError(f"Kraken: {j['error']}")
    t = next(iter(j["result"].values()))
    price = float(t["c"][0])

    def pct_since(candles, steps_back):
        if len(candles) > steps_back and candles[-1 - steps_back][1]:
            then = candles[-1 - steps_back][1]
            return (price - then) / then * 100
        return None

    try:
        chg24h = pct_since(_kraken_ohlc(60), 24)
    except Exception:  # noqa: BLE001
        chg24h = None
    try:
        daily = _kraken_ohlc(1440)
        chg7d, chg30d = pct_since(daily, 7), pct_since(daily, 30)
    except Exception:  # noqa: BLE001
        chg7d = chg30d = None
    return {"market_data": {
        "current_price": {"usd": price},
        "price_change_percentage_24h": chg24h,
        "price_change_percentage_7d": chg7d,
        "price_change_percentage_30d": chg30d,
        "market_cap": {"usd": 0}, "total_volume": {"usd": 0},
        "high_24h": {"usd": float(t["h"][1])}, "low_24h": {"usd": float(t["l"][1])},
        "ath": {"usd": 0}, "ath_change_percentage": {"usd": 0}, "circulating_supply": 0,
    }}


def fetch_coingecko_current():
    """CoinGecko /coins/bitcoin; Kraken when CoinGecko fails (the fallback has no "id" key)."""
    try:
        return _get("https://api.coingecko.com/api/v3/coins/bitcoin", {
            "localization": "false", "tickers": "false", "community_data": "false", "developer_data": "false",
        }).json()
    except Exception:  # noqa: BLE001
        return _kraken_current()


def fetch_price_history(days):
    """CoinGecko market_chart (free tier: up to 365 days); Kraken prices (no volume) when it fails."""
    try:
        return _get("https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
                    {"vs_currency": "usd", "days": days}).json()
    except Exception:  # noqa: BLE001
        cutoff = int(time.time() * 1000) - days * 86_400_000
        candles = [c for c in _kraken_ohlc(60 if days <= 30 else 1440) if c[0] >= cutoff]
        return {"prices": [[t, p] for t, p in candles], "total_volumes": [[t, 0] for t, _ in candles]}


def fetch_mempool_stats():
    stats = {}
    for key, url in [
        ("fees", "https://mempool.space/api/v1/fees/recommended"),
        ("mempool", "https://mempool.space/api/mempool"),
        ("difficulty", "https://mempool.space/api/v1/difficulty-adjustment"),
        ("blocks", "https://mempool.space/api/v1/blocks"),
        ("hashrate", "https://mempool.space/api/v1/mining/hashrate/1m"),
    ]:
        try:
            stats[key] = _get(url, timeout=10).json()
        except Exception:  # noqa: BLE001
            stats[key] = [] if key == "blocks" else {}
    stats["blocks"] = (stats.get("blocks") or [])[:6]
    return stats


def fetch_block_height():
    try:
        return int(_get("https://mempool.space/api/blocks/tip/height", timeout=10).text)
    except Exception:  # noqa: BLE001
        return None


def fetch_blockchain_stats():
    try:
        return _get("https://api.blockchain.info/stats", timeout=10).json()
    except Exception:  # noqa: BLE001
        return {}


def fetch_fear_greed():
    try:
        return _get("https://api.alternative.me/fng/", {"limit": 30}, timeout=10).json().get("data", [])
    except Exception:  # noqa: BLE001
        return []


def fetch_reddit_sentiment():
    try:
        posts = _get("https://www.reddit.com/r/Bitcoin/hot.json", {"limit": 50}, timeout=10).json()["data"]["children"]
    except Exception:  # noqa: BLE001
        return []
    out = []
    for p in posts:
        d = p.get("data", {})
        if d.get("stickied"):
            continue
        out.append({"title": d.get("title", ""), "ups": d.get("ups", 0), "comments": d.get("num_comments", 0),
                    "url": f"https://reddit.com{d.get('permalink', '')}"})
    return out[:25]


def fetch_top_wallets():
    try:
        return _get("https://api.blockchair.com/bitcoin/addresses", {"s": "balance(desc)", "limit": 100}).json().get("data") or []
    except Exception:  # noqa: BLE001
        return []


def fetch_google_trends():
    """[(ms, interest)] for "bitcoin" over 12 months, or None. Needs `pip install pytrends`."""
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        pt.build_payload(["bitcoin"], cat=0, timeframe="today 12-m")
        df = pt.interest_over_time()
        if df.empty:
            return None
        return [(int(ts.timestamp() * 1000), int(v)) for ts, v in df["bitcoin"].items()]
    except Exception:  # noqa: BLE001
        return None

HISTORY_PERIODS = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}

# Keyword lists for the Reddit mood.
BULLISH_WORDS = {"bull", "bullish", "pump", "moon", "ath", "buy", "long", "up", "surge", "rally", "gain", "accumulate", "hodl"}
BEARISH_WORDS = {"bear", "bearish", "dump", "crash", "sell", "short", "down", "drop", "fall", "fear", "panic", "capitulate"}

INSTITUTIONS = [
    {"entity": "BlackRock (IBIT ETF)", "type": "ETF", "btc": 550_000, "notes": "Largest Bitcoin ETF by AUM"},
    {"entity": "Grayscale (GBTC)", "type": "ETF/Trust", "btc": 220_000, "notes": "Original institutional product"},
    {"entity": "Strategy (MicroStrategy)", "type": "Corp Treasury", "btc": 848_517, "notes": "Largest corporate holder (Form 8-K)", "as_of": "Oct 25, 2026"},
    {"entity": "Fidelity (FBTC)", "type": "ETF", "btc": 175_000, "notes": "Second largest spot ETF"},
    {"entity": "US Government", "type": "Sovereign", "btc": 200_000, "notes": "Seized assets (DOJ/Treasury)"},
    {"entity": "Ark Invest (ARKB)", "type": "ETF", "btc": 50_000, "notes": "Cathie Wood's Bitcoin ETF"},
    {"entity": "El Salvador", "type": "Sovereign", "btc": 6_000, "notes": "Legal tender nation"},
    {"entity": "Coinbase (custody)", "type": "Custodian", "btc": 800_000, "notes": "Custodian for BlackRock, Fidelity & others"},
    {"entity": "Satoshi Nakamoto", "type": "Individual", "btc": 1_100_000, "notes": "Genesis era, never moved"},
]

# Fixed reference tables: past and next halvings, stock-to-flow at each halving.
HALVINGS = [
    {"halving": "#1", "date": "Nov 28, 2012", "block": 210_000, "reward": "50 → 25 BTC", "price_at": "$12", "price_1y": "$1,000", "gain": "+8,233%"},
    {"halving": "#2", "date": "Jul 9, 2016", "block": 420_000, "reward": "25 → 12.5 BTC", "price_at": "$650", "price_1y": "$2,500", "gain": "+285%"},
    {"halving": "#3", "date": "May 11, 2020", "block": 630_000, "reward": "12.5 → 6.25 BTC", "price_at": "$8,500", "price_1y": "$57,000", "gain": "+571%"},
    {"halving": "#4", "date": "Apr 19, 2024", "block": 840_000, "reward": "6.25 → 3.125 BTC", "price_at": "$63,800", "price_1y": "TBD", "gain": "TBD"},
    {"halving": "#5 (next)", "date": "~Apr 2028", "block": 1_050_000, "reward": "3.125 → 1.5625 BTC", "price_at": "?", "price_1y": "?", "gain": "?"},
]
S2F_REF = [
    {"year": "2009", "halving": "Genesis", "reward": 50, "s2f": "0.7", "model_price": "$0"},
    {"year": "2012", "halving": "#1", "reward": 25, "s2f": "11", "model_price": "$20"},
    {"year": "2016", "halving": "#2", "reward": 12.5, "s2f": "25", "model_price": "$740"},
    {"year": "2020", "halving": "#3", "reward": 6.25, "s2f": "56", "model_price": "$55,000"},
    {"year": "2024", "halving": "#4 (now)", "reward": 3.125, "s2f": "live", "model_price": "live"},
    {"year": "2028", "halving": "#5 (est.)", "reward": 1.5625, "s2f": "~240", "model_price": "TBD"},
]

# Sources that come from live APIs (the reference tables are fixed).
LIVE_SOURCES = ["market", "history", "fees", "mempool", "difficulty", "hashrate",
                "blocks", "block_height", "onchain", "fear_greed", "reddit", "wallets", "google_trends"]


def num(x):
    """Float or None (rejects missing, non-numeric and NaN)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def positive(x):
    """Like num(), but treats 0 / negatives as 'not reported' (APIs use 0 for missing)."""
    v = num(x)
    return v if v is not None and v > 0 else None


class Snapshot:
    def __init__(self):
        self.rows = []
        self.sources = {}

    def source(self, name, status, note=""):
        self.sources[name] = {"status": status, "note": note}

    def metric(self, key, value, source, text=None):
        row = {"kind": "metric", "key": key, "value": num(value), "source": source}
        if text is not None:
            row["text"] = text
        self.rows.append(row)

    def add(self, kind, **fields):
        self.rows.append({"kind": kind, **fields})

    def run(self, name, fn, *args):
        """Run one collector; any exception marks that source missing."""
        try:
            return fn(self, *args)
        except Exception as e:  # noqa: BLE001  (one bad source must not stop the run)
            self.source(name, "missing", f"{type(e).__name__}: {e}"[:300])
            return None


# ── Collectors ────────────────────────────────────────────────────────────────

def collect_market(s):
    cg = fetch_coingecko_current()  # CoinGecko, falls back to Kraken inside
    md = (cg or {}).get("market_data") or {}

    def usd(k):
        v = md.get(k)
        return v.get("usd") if isinstance(v, dict) else v

    price = positive(usd("current_price"))
    if price is None:
        raise ValueError("no price in response")
    # The Kraken fallback has no "id" and reports 0 for what it doesn't have
    # (market cap, global volume, supply, ATH); positive() turns those into "not reported".
    fallback = "id" not in cg
    if fallback:
        s.source("market", "fallback", "CoinGecko failed, used Kraken: market cap, global volume, supply and ATH not available")
    else:
        s.source("market", "ok", "CoinGecko /coins/bitcoin")

    s.metric("price", price, "market")
    s.metric("change_24h", md.get("price_change_percentage_24h"), "market")
    s.metric("market_cap", positive(usd("market_cap")), "market")
    s.metric("volume_24h", positive(usd("total_volume")), "market")
    s.metric("circulating", positive(md.get("circulating_supply")), "market")
    ath = positive(usd("ath"))
    s.metric("change_7d", md.get("price_change_percentage_7d"), "market")
    s.metric("change_30d", md.get("price_change_percentage_30d"), "market")
    s.metric("high_24h", positive(usd("high_24h")), "market")
    s.metric("low_24h", positive(usd("low_24h")), "market")
    s.metric("ath", ath, "market")
    s.metric("ath_change", usd("ath_change_percentage") if ath else None, "market")
    return price


def collect_history(s):
    got, failed, kraken = [], [], []
    for label, days in HISTORY_PERIODS.items():
        try:
            hist = fetch_price_history(days)  # CoinGecko, falls back to Kraken inside
            prices = hist.get("prices") or []
            if not prices:
                raise ValueError("no prices")
            volumes = {int(t): positive(v) for t, v in hist.get("total_volumes") or []}
            for t, p in prices:
                s.add("history", period=label, t=int(t), price=num(p), volume=volumes.get(int(t)))
            got.append(label)
            if not any(volumes.values()):  # the Kraken fallback reports no volume
                kraken.append(label)
            if label == "1y":
                closes = [num(p) for _, p in prices if num(p)]
                s.metric("high_52w", max(closes), "history")
                s.metric("low_52w", min(closes), "history")
        except Exception as e:  # noqa: BLE001
            failed.append(f"{label} ({type(e).__name__})")
    if not got:
        s.source("history", "missing", "all periods failed: " + ", ".join(failed))
    elif failed:
        s.source("history", "partial", "missing: " + ", ".join(failed)
                 + ("; from Kraken without volume: " + ", ".join(kraken) if kraken else ""))
    elif kraken:
        s.source("history", "fallback", "CoinGecko failed for " + ", ".join(kraken) + "; used Kraken prices (no volume)")
    else:
        s.source("history", "ok", "CoinGecko /market_chart (7, 30, 90, 365 days)")


def collect_mempool(s, bc_stats):
    stats = fetch_mempool_stats()  # each part is {} / [] when its call failed

    fees = stats.get("fees") or {}
    if "fastestFee" in fees:
        s.source("fees", "ok", "mempool.space /v1/fees/recommended")
        s.metric("fee_low", fees.get("economyFee"), "fees")
        s.metric("fee_med", fees.get("halfHourFee"), "fees")
        s.metric("fee_high", fees.get("fastestFee"), "fees")
    else:
        s.source("fees", "missing", "mempool.space fees call failed")

    mem = stats.get("mempool") or {}
    if "count" in mem:
        s.source("mempool", "ok", "mempool.space /mempool")
        s.metric("mempool_count", mem.get("count"), "mempool")
        s.metric("mempool_mb", (num(mem.get("vsize")) or 0) / 1e6, "mempool")
    else:
        s.source("mempool", "missing", "mempool.space mempool call failed")

    diff = stats.get("difficulty") or {}
    if "difficultyChange" in diff:
        s.source("difficulty", "ok", "mempool.space /v1/difficulty-adjustment")
        s.metric("difficulty_change", diff.get("difficultyChange"), "difficulty")
        s.metric("remaining_blocks", diff.get("remainingBlocks"), "difficulty")
        s.metric("retarget_at", diff.get("estimatedRetargetDate"), "difficulty")
    else:
        s.source("difficulty", "missing", "mempool.space difficulty call failed")

    hr = stats.get("hashrate") or {}
    current = positive(hr.get("currentHashrate"))
    if current:
        s.source("hashrate", "ok", "mempool.space /v1/mining/hashrate/1m")
        for p in hr.get("hashrates") or []:
            ehs = positive(p.get("avgHashrate"))
            if ehs and p.get("timestamp"):
                s.add("hashrate", t=int(p["timestamp"]) * 1000, ehs=ehs / 1e18)
    elif positive((bc_stats or {}).get("hash_rate")):
        # Fallback: blockchain.info reports hash rate in GH/s.
        current = positive(bc_stats["hash_rate"]) * 1e9
        s.source("hashrate", "fallback", "mempool.space failed, current value from blockchain.info, no 30-day chart")
    else:
        s.source("hashrate", "missing", "mempool.space and blockchain.info hash rate both failed")
    if current:
        s.metric("hashrate_ehs", current / 1e18, "hashrate")

    blocks = stats.get("blocks") or []
    if blocks:
        s.source("blocks", "ok", "mempool.space /v1/blocks")
        for b in blocks:
            extras = b.get("extras") or {}
            s.add("block",
                  height=b.get("height"),
                  t=int(b.get("timestamp") or 0) * 1000 or None,
                  tx_count=b.get("tx_count"),
                  size_mb=(num(b.get("size")) or 0) / 1e6,
                  fees_btc=(num(extras.get("totalFees")) or 0) / 1e8,
                  avg_fee_rate=num(extras.get("avgFeeRate")))
    else:
        s.source("blocks", "missing", "mempool.space blocks call failed")


def collect_block_height(s):
    h = fetch_block_height()
    if not h:
        raise ValueError("no tip height")
    s.source("block_height", "ok", "mempool.space /blocks/tip/height")
    s.metric("block_height", h, "block_height")


def collect_onchain(s, bc_stats):
    if not bc_stats or "n_tx" not in bc_stats:
        raise ValueError("blockchain.info /stats returned nothing")
    s.source("onchain", "ok", "blockchain.info /stats (last 24h)")
    blocks_24h = positive(bc_stats.get("n_blocks_mined"))
    size_total = positive(bc_stats.get("blocks_size"))
    sent_sat = positive(bc_stats.get("total_btc_sent"))
    s.metric("n_tx", positive(bc_stats.get("n_tx")), "onchain")
    s.metric("btc_sent", sent_sat / 1e8 if sent_sat else None, "onchain")
    # blockchain.info often reports 0 here; 0 means "not reported", not $0.
    s.metric("miners_revenue_usd", positive(bc_stats.get("miners_revenue_usd")), "onchain")
    s.metric("blocks_24h", blocks_24h, "onchain")
    # blocks_size is the total for the day, so divide by blocks mined for the average.
    s.metric("avg_block_mb", size_total / blocks_24h / 1e6 if size_total and blocks_24h else None, "onchain")


def collect_fear_greed(s):
    data = fetch_fear_greed()
    if not data:
        raise ValueError("alternative.me returned nothing")
    s.source("fear_greed", "ok", "alternative.me /fng (30 days)")
    for d in data:
        s.add("fng", t=int(d["timestamp"]) * 1000, value=int(d["value"]), label=d.get("value_classification"))
    s.metric("fng_value", int(data[0]["value"]), "fear_greed", text=data[0].get("value_classification"))


def collect_reddit(s):
    posts = fetch_reddit_sentiment()
    if not posts:
        raise ValueError("Reddit returned nothing (blocked or rate-limited)")
    s.source("reddit", "ok", "reddit.com r/Bitcoin hot (keyword mood)")
    for i, p in enumerate(posts):
        words = set(p["title"].lower().split())
        mood = "bullish" if words & BULLISH_WORDS else ("bearish" if words & BEARISH_WORDS else "neutral")
        s.add("reddit", rank=i + 1, title=p["title"][:200], ups=p.get("ups", 0),
              comments=p.get("comments", 0), url=p.get("url"), mood=mood)


def collect_wallets(s):
    wallets = fetch_top_wallets()
    if not wallets:
        raise ValueError("Blockchair returned nothing (usually its rate limit)")
    s.source("wallets", "ok", "Blockchair /bitcoin/addresses (top 100 by balance)")
    for i, w in enumerate(wallets):
        s.add("wallet", rank=i + 1, address=w.get("address"),
              balance_btc=(num(w.get("balance")) or 0) / 1e8, tx_count=w.get("transaction_count"))


def collect_trends(s):
    points = fetch_google_trends()  # pytrends; None when it fails or isn't installed
    if not points:
        raise ValueError("Google Trends returned nothing (pytrends missing, blocked or rate-limited)")
    s.source("google_trends", "ok", "Google Trends via pytrends, 'bitcoin', last 12 months, weekly")
    for t, interest in points:
        s.add("trends", t=t, interest=interest)


def collect_reference(s):
    s.source("reference", "ok", "Fixed halving and stock-to-flow reference tables")
    for h in HALVINGS:
        s.add("halving", **h)
    for r in S2F_REF:
        s.add("s2f_ref", **r)


def collect_institutions(s):
    s.source("holdings", "ok", "Fixed estimates from public filings, each dated in its as_of; not live")
    for e in INSTITUTIONS:
        s.add("institution", **{"as_of": "mid-2025", **e})


# ── Main ──────────────────────────────────────────────────────────────────────

def build_snapshot():
    s = Snapshot()
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    s.add("meta", key="fetched_at", text=fetched_at)

    s.run("market", collect_market)
    s.run("history", collect_history)
    bc_stats = None
    try:
        bc_stats = fetch_blockchain_stats()
    except Exception:  # noqa: BLE001
        bc_stats = {}
    s.run("fees", collect_mempool, bc_stats)
    s.run("block_height", collect_block_height)
    s.run("onchain", collect_onchain, bc_stats)
    s.run("fear_greed", collect_fear_greed)
    s.run("reddit", collect_reddit)
    s.run("wallets", collect_wallets)
    s.run("google_trends", collect_trends)
    collect_institutions(s)
    collect_reference(s)

    for name, info in s.sources.items():
        s.add("source", key=name, status=info["status"], note=info["note"])
    return {"fetched_at": fetched_at, "sources": s.sources, "rows": s.rows}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--out", default=str(ROOT / ".tmp" / "bitcoin_snapshot.json"))
    args = ap.parse_args(argv)

    snap = build_snapshot()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".part")
    tmp.write_text(json.dumps(snap, separators=(",", ":")))
    os.replace(tmp, out)

    print(f"Wrote {out} ({out.stat().st_size / 1024:.0f} KB, {len(snap['rows'])} rows), fetched_at {snap['fetched_at']}")
    for name, info in snap["sources"].items():
        flag = "  " if info["status"] == "ok" else "!!"
        print(f"  {flag} {name:<13} {info['status']:<9} {info['note']}")

    live_ok = [n for n in LIVE_SOURCES if snap["sources"].get(n, {}).get("status") in ("ok", "fallback", "partial")]
    if not live_ok:
        print("Every live source failed (no network?). Do not push this snapshot.", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
