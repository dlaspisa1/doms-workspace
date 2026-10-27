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
| Kraken | Fallback price and history when CoinGecko fails or for periods past its 365-day free limit (no volume, market cap or ATH) |
| Mempool.space | Hash rate, difficulty adjustment, fee rates, mempool size, recent blocks |
| Blockchain.com | 24h tx count, BTC sent on-chain, miner revenue, block size |

## Dashboard Sections

1. **Top Metrics** — Price, market cap, 24h volume, 7d/30d change
2. **Price & Volume History** — Price line with volume bars (7d/30d/90d/1y/2y; 2y comes from Kraken without volume)
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

## Artifact Dashboard (claude.ai)

The same sections also live as a claude.ai Dashboard artifact, "Bitcoin Analytics Dashboard":
https://claude.ai/artifact/HdocoUeBkcigCugoVyCzw7 (private until shared from its Share menu).

The page never fetches anything itself. It reads one snapshot file attached to the artifact
(dataset `snapshot` in the artifact's database). Each snapshot row has a `kind`
(`metric`, `history`, `hashrate`, `block`, `fng`, `reddit`, `wallet`, `institution`, `source`, `meta`).
`source` rows carry each API's status (`ok`, `fallback`, `partial`, `missing`); the page marks any section
whose source is missing as unavailable, and shows "Data as of" from `fetched_at`.

## Refresh

Runs hourly as a scheduled task ("Bitcoin dashboard hourly refresh"). To run it by hand:

1. Build the snapshot:
   ```bash
   cd "/Users/dominicklaspisa/Doms workspace"
   source venv/bin/activate
   python execution/bitcoin_snapshot.py
   ```
   Writes `.tmp/bitcoin_snapshot.json` and prints each source's status.
   - Exit 0: at least one live source answered. A failed source is recorded as `missing`, not an error.
   - Exit 3: every live source failed (usually no network or blocked domains). **Stop. Do not push.**
     The dashboard keeps showing the last good snapshot, and its "Data as of" line turns stale after 3 hours.
2. Push the snapshot to the artifact's database (Claude does this with its Artifact tools):
   - Upload the file to the artifact: `Artifact` publish with `url` = the artifact link above,
     `file_path` = `.tmp/bitcoin_snapshot.json`, `asset: true`. Note the returned `/_blob/<id>` url.
   - Read `datasets/snapshot` with `ArtifactData` `get` (for its `version`), then `update` it with
     `if_version` and: `source.url` = the new `/_blob/<id>`, `source.name` = `bitcoin_snapshot.json`,
     `updated` = `{"at": <fetched_at from the snapshot>, "by": "bitcoin_snapshot.py"}`.
     Send the whole `source` object (`kind: "file"`, `url`, `name`, `format: "json"`).
   - Then delete the previous upload (`Artifact` delete with `url` and `path` = the old blob id) so assets don't pile up.
   - Never write `files/index.html` during a refresh. The page is only changed when the layout changes.

### Network requirements
The snapshot needs outbound HTTPS to: api.coingecko.com, api.kraken.com, mempool.space, api.blockchain.info,
api.alternative.me, www.reddit.com, api.blockchair.com, trends.google.com. Cloud runs (scheduled tasks) only reach domains allowed in
claude.ai Settings > Capabilities; if those aren't allowed, every run exits 3 and nothing is pushed.

### Known source behavior (Oct 2026)
- CoinGecko's free API only serves 365 days of history. The Streamlit app's longest period is "2 Years" (Kraken daily candles, max ~720 days); the artifact offers 7d / 30d / 90d / 1y.
- CoinCap's v2 API was shut down (api.coincap.io no longer resolves), so Kraken replaced it as the fallback.
- CoinGecko rate-limits bursts (HTTP 429); a failed period is recorded and the others still load (`partial`).
- Blockchair's free tier often answers 430 (rate limit) and Reddit blocks some IPs; both then show as unavailable.
- Google Trends needs `pytrends` installed (`pip install pytrends`) and often rate-limits; it then shows as unavailable.
- blockchain.info reports `miners_revenue_usd` as 0; the snapshot records it as not reported, not $0.
- blockchain.info `blocks_size` is the day's total, so average block size = `blocks_size / n_blocks_mined`
  (the Streamlit app shows the total as the average; the snapshot corrects this).
- CoinGecko has no 52-week high/low field (the Streamlit app shows $0); the snapshot takes them from the 1-year daily prices.
