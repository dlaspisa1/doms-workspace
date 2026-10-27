"""
Bitcoin data sources
====================
Fetchers for the Bitcoin Analytics Dashboard artifact; execution/bitcoin_snapshot.py
calls them once per refresh. Each returns an empty value ({} / [] / None) on failure
instead of raising, so one dead source never stops a snapshot.

Free APIs used (no keys):
  - CoinGecko (price, market cap, volume, history), Kraken as fallback
  - Mempool.space (hash rate, difficulty, fees, mempool, blocks)
  - Blockchain.com stats (transactions, on-chain volume)
  - alternative.me (Fear & Greed), Reddit r/Bitcoin, Blockchair (top wallets)
  - Google Trends via pytrends
"""

import time

import requests

KRAKEN = "https://api.kraken.com/0/public"


def _kraken_ohlc(interval: int):
    """Kraken OHLC candles for XBT/USD. interval in minutes (60 = hourly, 1440 = daily).
    Kraken returns at most 720 candles: 30 days hourly or about 2 years daily."""
    r = requests.get(f"{KRAKEN}/OHLC", params={"pair": "XBTUSD", "interval": interval}, timeout=15)
    r.raise_for_status()
    j = r.json()
    if j.get("error"):
        raise RuntimeError(f"Kraken: {j['error']}")
    res = j.get("result", {})
    key = next(k for k in res if k != "last")
    # [time, open, high, low, close, vwap, volume, count]
    return [(int(c[0]) * 1000, float(c[4]), float(c[2])) for c in res[key]]


def _kraken_current_as_coingecko():
    """Fallback when CoinGecko fails: Kraken price data in a CoinGecko market_data-compatible dict.
    Kraken has no global volume, market cap or all-time high, so those stay 0 (not reported)."""
    r = requests.get(f"{KRAKEN}/Ticker", params={"pair": "XBTUSD"}, timeout=15)
    r.raise_for_status()
    j = r.json()
    if j.get("error"):
        raise RuntimeError(f"Kraken: {j['error']}")
    t = next(iter(j["result"].values()))
    price = float(t["c"][0])

    def pct_since(candles, steps_back):
        if len(candles) > steps_back:
            then = candles[-1 - steps_back][1]
            return (price - then) / then * 100 if then else 0
        return 0

    try:
        hourly = _kraken_ohlc(60)
        chg24h = pct_since(hourly, 24)
    except Exception:
        chg24h = 0
    try:
        daily = _kraken_ohlc(1440)
        chg7d, chg30d = pct_since(daily, 7), pct_since(daily, 30)
    except Exception:
        chg7d = chg30d = 0
    return {
        "market_data": {
            "current_price":               {"usd": price},
            "price_change_percentage_24h": chg24h,
            "price_change_percentage_7d":  chg7d,
            "price_change_percentage_30d": chg30d,
            "market_cap":                  {"usd": 0},
            "total_volume":                {"usd": 0},
            "high_24h":                    {"usd": float(t["h"][1])},
            "low_24h":                     {"usd": float(t["l"][1])},
            "ath":                         {"usd": 0},
            "ath_change_percentage":       {"usd": 0},
            "circulating_supply":          0,
        }
    }


def _kraken_history(days: int):
    """Fallback price history from Kraken. Hourly up to 30 days, daily up to ~720 days.
    Kraken volume is one exchange's, not global, so volumes are 0 (not reported)."""
    interval = 60 if days <= 30 else 1440
    cutoff = int(time.time() * 1000) - days * 86_400_000
    candles = [c for c in _kraken_ohlc(interval) if c[0] >= cutoff]
    prices = [[t, close] for t, close, _ in candles]
    volumes = [[t, 0] for t, _, _ in candles]
    return {"prices": prices, "total_volumes": volumes}


def fetch_coingecko_current():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/bitcoin",
            params={
                "localization": "false", "tickers": "false",
                "community_data": "false", "developer_data": "false"
            },
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return _kraken_current_as_coingecko()


def fetch_price_history(days: int):
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
            params={"vs_currency": "usd", "days": days},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return _kraken_history(days)


def fetch_mempool_stats():
    stats = {}
    try:
        stats["fees"] = requests.get("https://mempool.space/api/v1/fees/recommended", timeout=10).json()
    except Exception:
        stats["fees"] = {}
    try:
        stats["mempool"] = requests.get("https://mempool.space/api/mempool", timeout=10).json()
    except Exception:
        stats["mempool"] = {}
    try:
        stats["difficulty"] = requests.get("https://mempool.space/api/v1/difficulty-adjustment", timeout=10).json()
    except Exception:
        stats["difficulty"] = {}
    try:
        stats["blocks"] = requests.get("https://mempool.space/api/v1/blocks", timeout=10).json()[:6]
    except Exception:
        stats["blocks"] = []
    try:
        hashrate_data = requests.get("https://mempool.space/api/v1/mining/hashrate/1m", timeout=10).json()
        stats["hashrate"] = hashrate_data
    except Exception:
        stats["hashrate"] = {}
    return stats


def fetch_block_height():
    try:
        return int(requests.get("https://mempool.space/api/blocks/tip/height", timeout=10).text)
    except Exception:
        return None


def fetch_google_trends():
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        pt.build_payload(["bitcoin"], cat=0, timeframe="today 12-m")
        df = pt.interest_over_time()
        if df.empty:
            return None
        df = df.reset_index()[["date", "bitcoin"]]
        df.columns = ["date", "interest"]
        return df
    except Exception:
        return None


def fetch_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=30", timeout=10)
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception:
        return []


def fetch_reddit_sentiment():
    try:
        headers = {"User-Agent": "bitcoin-dashboard/1.0"}
        r = requests.get(
            "https://www.reddit.com/r/Bitcoin/hot.json?limit=50",
            headers=headers, timeout=10
        )
        r.raise_for_status()
        posts = r.json()["data"]["children"]
        results = []
        for p in posts:
            d = p["data"]
            if d.get("stickied"):
                continue
            results.append({
                "title": d.get("title", ""),
                "ups": d.get("ups", 0),
                "comments": d.get("num_comments", 0),
                "url": f"https://reddit.com{d.get('permalink', '')}",
            })
        return results[:25]
    except Exception:
        return []


def fetch_top_wallets():
    try:
        r = requests.get(
            "https://api.blockchair.com/bitcoin/addresses",
            params={"s": "balance(desc)", "limit": 100},
            timeout=15
        )
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception:
        return []


def fetch_blockchain_stats():
    try:
        r = requests.get("https://api.blockchain.info/stats", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}
