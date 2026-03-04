from __future__ import annotations

import argparse
import sys
from pathlib import Path

if str(Path(__file__).resolve().parents[1] / "src") not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pm_candle_odds.pipeline import StudyConfig, default_start_end, run_study


def parse_args() -> argparse.Namespace:
    default_start, default_end = default_start_end(days=30)

    p = argparse.ArgumentParser(description="BTC/USD strategy research run")
    p.add_argument("--exchange", default="coinbase", help="ccxt exchange id")
    p.add_argument("--symbol", default="BTC/USD", help="market symbol")
    p.add_argument("--start", default=default_start, help="UTC start, e.g. 2025-01-01T00:00:00Z")
    p.add_argument("--end", default=default_end, help="UTC end, e.g. 2025-02-01T00:00:00Z")
    p.add_argument("--outdir", default="results/generated")

    p.add_argument(
        "--min-5m-trend-candles",
        dest="min_5m_trend_candles",
        type=int,
        default=2,
        help="minimum same-direction 5m candles required to define trend",
    )
    p.add_argument(
        "--min-aligned-1m-in-first4",
        dest="min_aligned_1m_in_first4",
        type=int,
        default=3,
        help="minimum 1m candles aligned with trend within first 4 minutes",
    )
    p.add_argument(
        "--commission-rate",
        type=float,
        default=0.01,
        help="commission applied per signal as decimal (default 0.01 = 1%)",
    )

    # Backward-compatible aliases for older command history.
    p.add_argument("--trend-run", dest="min_5m_trend_candles", type=int, help=argparse.SUPPRESS)
    p.add_argument("--first4-min", dest="min_aligned_1m_in_first4", type=int, help=argparse.SUPPRESS)

    p.add_argument("--no-breakout-invalidation", action="store_true", help="disable counter-breakout invalidation")
    p.add_argument("--allow-chop", action="store_true", help="allow alternating 5m chop periods")
    p.add_argument("--no-api-keys", action="store_true", help="ignore PM_EXCHANGE_API_* env vars")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = StudyConfig(
        exchange=args.exchange,
        symbol=args.symbol,
        start_utc=args.start,
        end_utc=args.end,
        outdir=args.outdir,
        min_5m_trend_candles=args.min_5m_trend_candles,
        min_aligned_1m_in_first4=args.min_aligned_1m_in_first4,
        commission_rate=args.commission_rate,
        invalidate_on_counter_breakout=not args.no_breakout_invalidation,
        skip_chop=not args.allow_chop,
        use_env_api_keys=not args.no_api_keys,
    )

    out = run_study(cfg)
    print(f"Run ID: {out.run_id}")
    print(f"Summary: {out.summary_path}")
    print(f"Signals: {out.events_path}")
    print(f"Losing signals: {out.losers_path}")
    if out.chart_paths:
        print("Charts:")
        for path in out.chart_paths:
            print(f" - {path}")


if __name__ == "__main__":
    main()
