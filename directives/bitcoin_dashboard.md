# Bitcoin Analytics Dashboard

## Goal
Run a local Streamlit dashboard that displays Bitcoin price, on-chain metrics, network health, mempool data, and recent blocks in real time.

## How to Run

```bash
cd "/Users/dominicklaspisa/Doms workspace"
source venv/bin/activate
streamlit run execution/bitcoin_dashboard.py
```

Then open http://localhost:8501 in your browser.

## Data Sources (all free, no API keys required)

| Source | Data |
|---|---|
| CoinGecko | Price, market cap, volume, % changes, historical data, ATH |
| Mempool.space | Hash rate, difficulty adjustment, fee rates, mempool size, recent blocks |
| Blockchain.com | 24h tx count, BTC sent on-chain, miner revenue, block size |

## Dashboard Sections

1. **Top Metrics** — Price, market cap, 24h volume, 7d/30d change
2. **Price & Volume History** — Candlestick chart with volume bars (7d/30d/90d/1y/all-time)
3. **Network Health** — Hash rate chart, difficulty adjustment countdown, circulating supply
4. **Mempool & Fees** — Low/medium/high fee rates (sat/vB), pending tx count, mempool size
5. **On-Chain Activity** — 24h tx count, BTC sent on-chain, miner revenue, avg block size
6. **Recent Blocks** — Height, time, tx count, size, fees for the last 6 blocks
7. **Price Ranges** — 24h high/low, 52-week high/low, all-time high

## Refresh Behavior
- API responses cached for 5 minutes via `@st.cache_data(ttl=300)`
- Page auto-reloads every 5 minutes via injected JS
- Manual refresh button available in the header

## Dependencies
- `streamlit` — UI framework
- `plotly` — interactive charts
- `pandas` — data manipulation
- `requests` — API calls (already in venv)

Install:
```bash
pip install streamlit plotly pandas
```

## Known Constraints / Edge Cases
- CoinGecko free tier: ~30 req/min — do not lower TTL below 60s
- Mempool.space may return empty blocks array if API is slow — handled gracefully
- Blockchain.com `/stats` returns satoshis for `total_btc_sent` — converted to BTC in script
- Hash rate endpoint (`/v1/mining/hashrate/1m`) returns 1-month rolling data

## Deploying Publicly (Streamlit Cloud)
1. Create a free account at https://github.com
2. Create a new repo and push this workspace
3. Go to https://streamlit.io/cloud → "New app" → point to `execution/bitcoin_dashboard.py`
4. App gets a public URL (e.g., `yourname.streamlit.app`)
