# Bitcoin / U.S. Dollar - System Research

## Setup
```bash
cd /Users/Anyone/Desktop/official-bitcoin-research
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Optional API Keys (Environment Variables)
If your exchange supports richer authenticated data access, set these before running:

```bash
export PM_EXCHANGE_API_KEY="your_key"
export PM_EXCHANGE_API_SECRET="your_secret"
export PM_EXCHANGE_API_PASSWORD="your_passphrase_if_needed"
```

If unset, public market data is used.

## Run (Menu)
```bash
python scripts/study_menu.py
```

Defaults are optimized so you can mostly press Enter:
- Exchange: `coinbase`
- Symbol: `BTC/USD`
- Date window: last 30 days

## Run (CLI)
```bash
python scripts/run_study.py \
  --exchange coinbase \
  --symbol BTC/USD \
  --start 2025-01-01T00:00:00Z \
  --end 2025-02-01T00:00:00Z
```

## Output Files
- `results/generated/summary.csv`
- `results/generated/signals.csv`
- `results/generated/losers.csv`
- `results/generated/data/candles_1m.csv`
- `results/generated/data/candles_5m.csv`
- `results/generated/charts/cumulative_points.png`
- `results/generated/charts/cumulative_win_rate.png`
- `results/generated/charts/signal_invalidation_counts.png`

## Tableau
- Use `signals.csv` for time-series charts.
- Plot `period_end` on X-axis.
- Plot `cumulative_points` on Y-axis for your points curve (win=+1, loss=-1).
- Plot `cumulative_win_rate` on Y-axis for win-rate drift over time.
- Use `losers.csv` to inspect common loss characteristics.
