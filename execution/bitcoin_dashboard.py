"""
Bitcoin On-Chain Analytics Dashboard
=====================================
Free APIs used:
  - CoinGecko (price, market cap, volume, history)
  - Mempool.space (hash rate, difficulty, fees, mempool, blocks)
  - Blockchain.com stats (transactions, on-chain volume)

Run:
  source venv/bin/activate
  streamlit run execution/bitcoin_dashboard.py
"""

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timezone
import time

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Bitcoin Analytics",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: #1a1a2e;
        border-radius: 10px;
        padding: 16px 20px;
        border: 1px solid #2d2d4e;
    }
    .metric-label { color: #888; font-size: 13px; margin-bottom: 4px; }
    .metric-value { color: #fff; font-size: 26px; font-weight: 700; }
    .metric-delta-pos { color: #22c55e; font-size: 14px; }
    .metric-delta-neg { color: #ef4444; font-size: 14px; }
    .section-header {
        color: #f59e0b;
        font-size: 16px;
        font-weight: 600;
        margin: 20px 0 10px 0;
        border-bottom: 1px solid #2d2d4e;
        padding-bottom: 6px;
    }
    .stMetric label { color: #888 !important; }
    div[data-testid="stMetricValue"] { font-size: 24px !important; }
</style>
""", unsafe_allow_html=True)


# ── API fetchers (cached 5 min) ───────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_coingecko_current():
    r = requests.get(
        "https://api.coingecko.com/api/v3/coins/bitcoin",
        params={
            "localization": "false", "tickers": "false",
            "community_data": "false", "developer_data": "false"
        },
        timeout=15
    )
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=300)
def fetch_price_history(days: int):
    r = requests.get(
        "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
        params={"vs_currency": "usd", "days": days, "interval": "daily" if days > 30 else "hourly"},
        timeout=15
    )
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=300)
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


@st.cache_data(ttl=300)
def fetch_blockchain_stats():
    try:
        r = requests.get("https://api.blockchain.info/stats", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}


# ── Helpers ───────────────────────────────────────────────────────────────────
def fmt_price(v):
    return f"${v:,.0f}"

def fmt_large(v):
    if v >= 1e12:
        return f"${v/1e12:.2f}T"
    if v >= 1e9:
        return f"${v/1e9:.2f}B"
    if v >= 1e6:
        return f"${v/1e6:.2f}M"
    return f"${v:,.0f}"

def fmt_hash(h):
    """Format hash rate in EH/s."""
    ehs = h / 1e18
    return f"{ehs:.1f} EH/s"

def delta_color(v):
    return "metric-delta-pos" if v >= 0 else "metric-delta-neg"

def delta_arrow(v):
    return "▲" if v >= 0 else "▼"


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    # Header
    col_title, col_refresh = st.columns([4, 1])
    with col_title:
        st.markdown("# ₿ Bitcoin Analytics Dashboard")
    with col_refresh:
        st.markdown(f"<div style='text-align:right; color:#888; padding-top:20px;'>Updated: {datetime.now().strftime('%H:%M:%S')}</div>", unsafe_allow_html=True)
        if st.button("↻ Refresh"):
            st.cache_data.clear()
            st.rerun()

    # Load data
    with st.spinner("Fetching live data..."):
        try:
            cg = fetch_coingecko_current()
            mempool = fetch_mempool_stats()
            bc_stats = fetch_blockchain_stats()
        except Exception as e:
            st.error(f"Failed to fetch data: {e}")
            return

    md = cg.get("market_data", {})
    price = md.get("current_price", {}).get("usd", 0)
    change_24h = md.get("price_change_percentage_24h", 0) or 0
    change_7d = md.get("price_change_percentage_7d", 0) or 0
    change_30d = md.get("price_change_percentage_30d", 0) or 0
    market_cap = md.get("market_cap", {}).get("usd", 0)
    volume_24h = md.get("total_volume", {}).get("usd", 0)
    high_24h = md.get("high_24h", {}).get("usd", 0)
    low_24h = md.get("low_24h", {}).get("usd", 0)
    ath = md.get("ath", {}).get("usd", 0)
    ath_change = md.get("ath_change_percentage", {}).get("usd", 0) or 0
    circulating = md.get("circulating_supply", 0)

    # ── Top metrics ───────────────────────────────────────────────────────────
    st.markdown("---")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("BTC Price", fmt_price(price), f"{change_24h:+.2f}% (24h)")
    with c2:
        st.metric("Market Cap", fmt_large(market_cap))
    with c3:
        st.metric("24h Volume", fmt_large(volume_24h))
    with c4:
        st.metric("7d Change", f"{change_7d:+.2f}%")
    with c5:
        st.metric("30d Change", f"{change_30d:+.2f}%")

    st.markdown("---")

    # ── Price chart ───────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">📈 Price & Volume History</div>', unsafe_allow_html=True)

    period_map = {"7 Days": 7, "30 Days": 30, "90 Days": 90, "1 Year": 365, "All Time": 1825}
    selected = st.radio("Period", list(period_map.keys()), horizontal=True, index=1)
    days = period_map[selected]

    try:
        hist = fetch_price_history(days)
        prices = hist.get("prices", [])
        volumes = hist.get("total_volumes", [])

        df_price = pd.DataFrame(prices, columns=["timestamp", "price"])
        df_price["date"] = pd.to_datetime(df_price["timestamp"], unit="ms")
        df_vol = pd.DataFrame(volumes, columns=["timestamp", "volume"])
        df_vol["date"] = pd.to_datetime(df_vol["timestamp"], unit="ms")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_price["date"], y=df_price["price"],
            name="Price", line=dict(color="#f59e0b", width=2),
            yaxis="y1"
        ))
        fig.add_trace(go.Bar(
            x=df_vol["date"], y=df_vol["volume"],
            name="Volume", marker_color="rgba(245,158,11,0.2)",
            yaxis="y2"
        ))
        fig.update_layout(
            plot_bgcolor="#0f0f1a", paper_bgcolor="#0f0f1a",
            font=dict(color="#aaa"),
            height=380,
            yaxis=dict(title="Price (USD)", tickformat="$,.0f", gridcolor="#1e1e2e", side="left"),
            yaxis2=dict(title="Volume", overlaying="y", side="right", showgrid=False),
            legend=dict(x=0, y=1),
            margin=dict(l=0, r=0, t=20, b=0),
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"Could not load price history: {e}")

    # ── Network + Mempool ─────────────────────────────────────────────────────
    col_net, col_mem = st.columns(2)

    # Network Health
    with col_net:
        st.markdown('<div class="section-header">⛏️ Network Health</div>', unsafe_allow_html=True)

        diff_data = mempool.get("difficulty", {})
        hashrate_data = mempool.get("hashrate", {})

        # Current hash rate from hashrate endpoint
        current_hashrate = None
        if hashrate_data and "currentHashrate" in hashrate_data:
            current_hashrate = hashrate_data["currentHashrate"]

        diff_adj = diff_data.get("difficultyChange", 0) or 0
        remaining_blocks = diff_data.get("remainingBlocks", "—")
        est_retarget = diff_data.get("estimatedRetargetDate", None)

        n1, n2 = st.columns(2)
        with n1:
            if current_hashrate:
                st.metric("Hash Rate", fmt_hash(current_hashrate))
            else:
                st.metric("Hash Rate", "—")
            st.metric("Circulating Supply", f"{circulating/1e6:.3f}M BTC")
        with n2:
            st.metric("Difficulty Adj.", f"{diff_adj:+.2f}%", f"{remaining_blocks} blocks")
            st.metric("ATH Distance", f"{ath_change:.1f}%", f"ATH: {fmt_price(ath)}")

        # Hash rate chart
        if hashrate_data and "hashrates" in hashrate_data:
            hr_list = hashrate_data["hashrates"]
            df_hr = pd.DataFrame(hr_list)
            df_hr["date"] = pd.to_datetime(df_hr["timestamp"], unit="s")
            df_hr["ehs"] = df_hr["avgHashrate"] / 1e18

            fig_hr = go.Figure()
            fig_hr.add_trace(go.Scatter(
                x=df_hr["date"], y=df_hr["ehs"],
                fill="tozeroy", line=dict(color="#818cf8", width=2),
                fillcolor="rgba(129,140,248,0.15)", name="Hash Rate"
            ))
            fig_hr.update_layout(
                plot_bgcolor="#0f0f1a", paper_bgcolor="#0f0f1a",
                font=dict(color="#aaa"), height=180,
                yaxis=dict(title="EH/s", gridcolor="#1e1e2e"),
                margin=dict(l=0, r=0, t=10, b=0),
                showlegend=False,
            )
            st.plotly_chart(fig_hr, use_container_width=True)

    # Mempool & Fees
    with col_mem:
        st.markdown('<div class="section-header">🔁 Mempool & Fees</div>', unsafe_allow_html=True)

        fees = mempool.get("fees", {})
        mem = mempool.get("mempool", {})

        low_fee = fees.get("economyFee", "—")
        med_fee = fees.get("halfHourFee", "—")
        high_fee = fees.get("fastestFee", "—")
        pending_tx = mem.get("count", 0)
        mem_vsize = mem.get("vsize", 0)
        mem_mb = mem_vsize / 1e6 if mem_vsize else 0

        f1, f2, f3 = st.columns(3)
        with f1:
            st.metric("Low Priority", f"{low_fee} sat/vB")
        with f2:
            st.metric("Medium (~30min)", f"{med_fee} sat/vB")
        with f3:
            st.metric("High (~10min)", f"{high_fee} sat/vB")

        m1, m2 = st.columns(2)
        with m1:
            st.metric("Pending TXs", f"{pending_tx:,}")
        with m2:
            st.metric("Mempool Size", f"{mem_mb:.1f} MB")

        # Fee gauge chart
        if all(isinstance(f, (int, float)) for f in [low_fee, med_fee, high_fee]):
            fig_fee = go.Figure(go.Bar(
                x=["Low", "Medium", "High"],
                y=[low_fee, med_fee, high_fee],
                marker_color=["#22c55e", "#f59e0b", "#ef4444"],
                text=[f"{v} sat/vB" for v in [low_fee, med_fee, high_fee]],
                textposition="outside",
            ))
            fig_fee.update_layout(
                plot_bgcolor="#0f0f1a", paper_bgcolor="#0f0f1a",
                font=dict(color="#aaa"), height=200,
                yaxis=dict(title="sat/vB", gridcolor="#1e1e2e"),
                margin=dict(l=0, r=0, t=10, b=0),
                showlegend=False,
            )
            st.plotly_chart(fig_fee, use_container_width=True)

    # ── On-chain stats ────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">🔗 On-Chain Activity (24h)</div>', unsafe_allow_html=True)

    o1, o2, o3, o4 = st.columns(4)
    tx_count = bc_stats.get("n_tx", 0)
    btc_sent = bc_stats.get("total_btc_sent", 0)
    btc_sent_k = btc_sent / 1e8 if btc_sent else 0  # convert from satoshis
    miners_revenue = bc_stats.get("miners_revenue_usd", 0)
    avg_block_size = bc_stats.get("blocks_size", 0)
    avg_block_mb = avg_block_size / 1e6 if avg_block_size else 0

    with o1:
        st.metric("Transactions (24h)", f"{tx_count:,}" if tx_count else "—")
    with o2:
        st.metric("BTC Sent (24h)", f"{btc_sent_k:,.0f} BTC" if btc_sent_k else "—")
    with o3:
        st.metric("Miner Revenue", fmt_large(miners_revenue) if miners_revenue else "—")
    with o4:
        st.metric("Avg Block Size", f"{avg_block_mb:.2f} MB" if avg_block_mb else "—")

    # ── Recent blocks ─────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">🧱 Recent Blocks</div>', unsafe_allow_html=True)

    blocks = mempool.get("blocks", [])
    if blocks:
        block_rows = []
        for b in blocks:
            ts = b.get("timestamp", 0)
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S UTC") if ts else "—"
            block_rows.append({
                "Height": f"{b.get('height', '—'):,}",
                "Time": dt,
                "Txs": f"{b.get('tx_count', 0):,}",
                "Size": f"{b.get('size', 0)/1e6:.2f} MB",
                "Fees (BTC)": f"{b.get('extras', {}).get('totalFees', 0)/1e8:.4f}",
                "Avg Fee (sat/vB)": f"{b.get('extras', {}).get('avgFeeRate', 0):.0f}",
            })
        df_blocks = pd.DataFrame(block_rows)
        st.dataframe(df_blocks, use_container_width=True, hide_index=True)
    else:
        st.info("Block data unavailable")

    # ── Price range ───────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">📊 Price Ranges</div>', unsafe_allow_html=True)

    r1, r2, r3, r4, r5 = st.columns(5)
    with r1:
        st.metric("24h High", fmt_price(high_24h))
    with r2:
        st.metric("24h Low", fmt_price(low_24h))
    with r3:
        st.metric("52w High", fmt_price(md.get("high_52_weeks", {}).get("usd", 0) or 0))
    with r4:
        st.metric("52w Low", fmt_price(md.get("low_52_weeks", {}).get("usd", 0) or 0))
    with r5:
        st.metric("All-Time High", fmt_price(ath))

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        "<div style='color:#555; text-align:center; font-size:12px;'>"
        "Data: CoinGecko · Mempool.space · Blockchain.com · Refreshes every 5 min · Not financial advice"
        "</div>",
        unsafe_allow_html=True
    )

    # Auto-refresh every 5 minutes
    time.sleep(0)  # yields control; Streamlit reruns on user interaction
    st.markdown(
        "<script>setTimeout(function(){window.location.reload()}, 300000);</script>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
