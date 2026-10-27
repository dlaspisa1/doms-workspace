# Bitcoin Analytics Dashboard

## Goal
Keep a Bitcoin dashboard (price, network health, mempool and fees, on-chain activity, sentiment,
valuation models, holdings) current on claude.ai, refreshed hourly. No server or Streamlit app is involved.

- **Dashboard:** claude.ai Dashboard artifact "Bitcoin Analytics Dashboard",
  https://claude.ai/artifact/HdocoUeBkcigCugoVyCzw7 (private until shared from its Share menu).
- **Data:** `execution/bitcoin_snapshot.py`, a standalone script that writes one JSON snapshot.
- **Refresh:** a scheduled task, "Bitcoin dashboard hourly refresh", runs the script in the cloud
  and pushes the snapshot to the artifact's database.

The old Streamlit app (`execution/bitcoin_dashboard.py`, bitcoiner.streamlit.app) is retired.
Nothing here imports or needs it.

## How it fits together
1. `bitcoin_snapshot.py` calls the free APIs below and writes `.tmp/bitcoin_snapshot.json`:
   `{"fetched_at": ..., "sources": {...}, "rows": [...]}`.
2. The snapshot file is uploaded to the artifact, and the artifact's `datasets/snapshot` record
   is pointed at it. The page (`files/index.html` in the artifact's database) reads that record.
3. The page never fetches anything itself, and a refresh never touches the page.

Each row in `rows` has a `kind`: `meta` (fetched_at), `source` (each API's status), `metric`,
`history` (7d/30d/90d/1y), `hashrate`, `block`, `fng`, `reddit`, `wallet`, `trends`,
`institution`, `halving`, `s2f_ref`. Calculated figures (mining cost, halving countdown,
rainbow bands, stock-to-flow, Reddit mood, holdings value, signal) are worked out on the page
from these rows, so they always match the snapshot.

Source status is `ok`, `fallback`, `partial` or `missing`. The page marks any section whose
source is missing as unavailable, shows "Data as of" from `fetched_at`, and flags the data as
stale after 3 hours.

## Dashboard sections
Market · Mining economics · Price & volume history · Network health · Mempool & fees ·
On-chain activity (24h) · Recent blocks · Price ranges · Halving cycle · Rainbow chart ·
Stock-to-flow · Google Trends · Advanced on-chain (Glassnode note, no data) ·
Market mood & sentiment · Institutional & sovereign holdings · Top 100 wallets

## Data sources (free, no API keys)

| Source | Data |
|---|---|
| CoinGecko | Price, market cap, volume, % changes, ATH, price history (up to 365 days) |
| Kraken | Fallback price, 24h/7d/30d change, 24h high/low and history when CoinGecko fails (no volume, market cap, supply or ATH) |
| mempool.space | Fees, mempool, difficulty adjustment, hash rate (30 days), recent blocks, tip height |
| blockchain.info | 24h transactions, BTC sent, blocks mined, block size; hash rate fallback |
| alternative.me | Fear & Greed index (30 days) |
| Reddit | r/Bitcoin hot posts (keyword mood) |
| Blockchair | Top 100 addresses by balance |
| Google Trends (pytrends) | 12 months of weekly search interest for "bitcoin" |
| Fixed tables in the script | Institutional holdings estimates (mid-2025), halving history, stock-to-flow by halving |

## Refresh

Runs hourly as a scheduled task ("Bitcoin dashboard hourly refresh", cloud, :19 past each hour).
The task clones `dlaspisa1/doms-workspace` from GitHub, so changes to the script only take effect once pushed.

To run it by hand:

1. Build the snapshot:
   ```bash
   cd "/Users/dominicklaspisa/Doms workspace"
   pip install requests pytrends      # once; pytrends is only for Google Trends
   python3 execution/bitcoin_snapshot.py
   ```
   Writes `.tmp/bitcoin_snapshot.json` and prints each source's status.
   - Exit 0: at least one live source answered. A failed source is recorded as `missing`, not an error.
   - Exit 3: every live source failed (usually no network or blocked domains). **Stop. Do not push.**
     The dashboard keeps showing the last good snapshot.
2. Push the snapshot to the artifact's database (Claude does this with its Artifact tools):
   - Upload the file: `Artifact` publish with `url` = the artifact link above,
     `file_path` = `.tmp/bitcoin_snapshot.json`, `asset: true`. Note the returned `/_blob/<id>` url.
   - `ArtifactData` `get` collection `datasets`, doc `snapshot` (for its `version` and old `source.url`), then
     `update` it with `if_version` and
     `{"source": {"kind": "file", "url": "<new /_blob/ url>", "name": "bitcoin_snapshot.json", "format": "json"},
     "updated": {"at": "<fetched_at>", "by": "bitcoin_snapshot.py"}}`.
   - Delete the previous upload (`Artifact` delete, `path` = the old blob id) so assets don't pile up.
   - Never write `files/index.html` during a refresh. The page changes only when the layout changes.

### Network requirements
The snapshot needs outbound HTTPS to: api.coingecko.com, api.kraken.com, mempool.space,
api.blockchain.info, api.alternative.me, www.reddit.com, api.blockchair.com, trends.google.com.
Cloud runs (scheduled tasks) only reach domains allowed in claude.ai Settings > Capabilities;
if those aren't allowed, every run exits 3 and nothing is pushed.

## Updating the fixed tables
Holdings, halving and stock-to-flow tables live as `INSTITUTIONS`, `HALVINGS` and `S2F_REF` near the
top of `bitcoin_snapshot.py`. Edit them there; the next refresh carries the change to the dashboard.
Each holdings row carries an `as_of` date shown on the dashboard. Strategy is current (848,517 BTC, Form 8-K,
Oct 25, 2026); the other rows are mid-2025 estimates and likely stale.

## Known source behavior (Oct 2026)
- CoinGecko's free API only serves 365 days of history (longer requests return 401), so the dashboard
  offers 7d / 30d / 90d / 1y. Kraken can supply about 720 days of daily prices if a longer view is ever needed.
- CoinCap's v2 API was shut down (api.coincap.io no longer resolves); Kraken replaced it as the fallback.
- CoinGecko rate-limits bursts (HTTP 429); a failed period is recorded and the others still load (`partial`).
- Blockchair's free tier often answers 430 (IP temporarily blacklisted) and Reddit blocks some IPs;
  both then show as unavailable.
- Google Trends needs `pytrends` and often rate-limits; it then shows as unavailable.
- blockchain.info reports `miners_revenue_usd` as 0; the snapshot records it as not reported, not $0.
- blockchain.info `blocks_size` is the day's total, so average block size = `blocks_size / n_blocks_mined`.
- CoinGecko has no 52-week high/low; the snapshot takes them from the 1-year daily prices.
- mempool.space hash rate `/v1/mining/hashrate/1m` is a 1-month daily series; `currentHashrate` is H/s.
