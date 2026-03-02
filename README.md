# Bitcoin / U.S. Dollar - System Research

Research framework for short-horizon BTC/USD signal evaluation, data quality checks, and performance analytics.

This repository is designed as a public-facing engineering artifact for quant/system-research workflows. It demonstrates how to structure repeatable market experiments end-to-end without disclosing proprietary entry logic.

## Context
This repository reflects production-minded research habits:
- deterministic, repeatable workflows
- explicit outputs for peer review
- separation of data, analysis, and reporting concerns
- tooling that supports both experimentation and operational discipline

## Goals
- Build a reproducible research pipeline for BTC/USD intraday studies.
- Convert raw exchange candles into clean experiment datasets.
- Evaluate directional hypotheses with strict, timestamped signal/outcome tracking.
- Export analyst-friendly artifacts for review in Tableau or similar tools.
- Support fast iteration on new configurations while preserving auditability.

## Highlights
This highlights practical skills relevant to research, trading-tech, and data roles:
- API data ingestion and normalization
- Time-series transformation and validation
- Signal-event labeling and outcome scoring
- Batch backtesting and parameter sweeps
- Visualization and performance diagnostics
- Clean CLI/terminal UX for repeatable workflows

## Confidentiality Note
The public codebase keeps alpha-sensitive strategy internals abstracted at a high level. The framework, analytics, and process are fully demonstrable; proprietary edge details are intentionally not documented in this README.

## Tech Stack
- Python 3.9+
- `ccxt` for exchange data access
- `pandas` / `numpy` for research and analysis
- `matplotlib` for chart generation

## Quick Start
```bash
cd /Users/Anyone/Desktop/official-bitcoin-research
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

## Optional API Credentials
If your exchange account/API tier provides improved access, set:

```bash
export PM_EXCHANGE_API_KEY="your_key"
export PM_EXCHANGE_API_SECRET="your_secret"
export PM_EXCHANGE_API_PASSWORD="your_passphrase_if_needed"
```

If these are unset, the framework uses public endpoints where available.

## Run Research (Menu)
```bash
python3 scripts/study_menu.py
```

Menu defaults are tuned for quick repeated runs.

## Run Research (CLI)
```bash
python3 scripts/run_study.py \
  --exchange coinbase \
  --symbol BTC/USD \
  --start 2025-01-01T00:00:00Z \
  --end 2025-02-01T00:00:00Z
```

## Analytics Workflow
1. Run one or more backtests over defined windows.
2. Compare configurations by signal count, hit rate, and stability.
3. Inspect loss subsets for recurring failure conditions.
4. Use cumulative charts to evaluate consistency over time.
5. Promote robust settings into longer walk-forward testing.

## Tableau Integration
Recommended fields for dashboards:
- Time axis: `period_end`
- Outcome metrics: `win`, `point`, `cumulative_points`, `cumulative_win_rate`
- Filters: run window, exchange, symbol, configuration

Suggested visuals:
- Cumulative points over time
- Cumulative win-rate curve
- Monthly signal volume vs win rate
- Loss-case drilldowns by context tags

## Repository Structure
- `scripts/` runnable CLI and menu entry points
- `src/pm_candle_odds/` core pipeline, analysis, and plotting modules
- `results/` generated run artifacts (typically gitignored)
