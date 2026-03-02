from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import pandas as pd

from .analysis import StrategyRules, evaluate_strategy
from .data import ApiCredentials, OhlcvApiClient, OhlcvRequest


@dataclass
class StudyConfig:
    exchange: str = "coinbase"
    symbol: str = "BTC/USD"
    start_utc: str = ""
    end_utc: str = ""
    outdir: str = "results/generated"
    trend_5m_min_run: int = 2
    one_min_required_in_first_four: int = 3
    invalidate_on_counter_breakout: bool = True
    skip_chop: bool = True
    use_env_api_keys: bool = True


@dataclass
class StudyOutput:
    run_id: str
    summary_path: Path
    events_path: Path
    losers_path: Path
    chart_paths: List[Path]


def default_start_end(days: int = 30) -> tuple[str, str]:
    end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start = end - timedelta(days=days)
    return start.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z")


def run_study(cfg: StudyConfig) -> StudyOutput:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    outdir = Path(cfg.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    start_utc = cfg.start_utc
    end_utc = cfg.end_utc
    if not start_utc or not end_utc:
        start_utc, end_utc = default_start_end(days=30)

    credentials = ApiCredentials.from_env() if cfg.use_env_api_keys else ApiCredentials()
    client = OhlcvApiClient(cfg.exchange, credentials=credentials)

    one_req = OhlcvRequest(
        exchange=cfg.exchange,
        symbol=cfg.symbol,
        timeframe="1m",
        start_utc=start_utc,
        end_utc=end_utc,
    )
    five_req = OhlcvRequest(
        exchange=cfg.exchange,
        symbol=cfg.symbol,
        timeframe="5m",
        start_utc=start_utc,
        end_utc=end_utc,
    )

    one_df = client.fetch_ohlcv_range(one_req)
    five_df = client.fetch_ohlcv_range(five_req)

    rules = StrategyRules(
        trend_5m_min_run=cfg.trend_5m_min_run,
        one_min_required_in_first_four=cfg.one_min_required_in_first_four,
        invalidate_on_counter_breakout=cfg.invalidate_on_counter_breakout,
        skip_chop=cfg.skip_chop,
    )

    summary_df, events_df = evaluate_strategy(five_df, one_df, rules)

    events_out = events_df.assign(
        run_id=run_id,
        exchange=cfg.exchange,
        symbol=cfg.symbol,
        start_utc=start_utc,
        end_utc=end_utc,
    )
    summary_out = summary_df.assign(
        run_id=run_id,
        exchange=cfg.exchange,
        symbol=cfg.symbol,
        start_utc=start_utc,
        end_utc=end_utc,
        trend_5m_min_run=cfg.trend_5m_min_run,
        one_min_required_in_first_four=cfg.one_min_required_in_first_four,
        invalidate_on_counter_breakout=cfg.invalidate_on_counter_breakout,
        skip_chop=cfg.skip_chop,
    )

    losers_out = events_out[events_out["win"] == 0].copy() if not events_out.empty else pd.DataFrame()

    summary_path = outdir / "summary.csv"
    events_path = outdir / "signals.csv"
    losers_path = outdir / "losers.csv"

    summary_out.to_csv(summary_path, index=False)
    events_out.to_csv(events_path, index=False)
    losers_out.to_csv(losers_path, index=False)

    data_dir = outdir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    one_df.to_csv(data_dir / "candles_1m.csv", index=False)
    five_df.to_csv(data_dir / "candles_5m.csv", index=False)

    from .plots import save_strategy_charts

    chart_paths = save_strategy_charts(events_out, outdir / "charts")

    return StudyOutput(
        run_id=run_id,
        summary_path=summary_path,
        events_path=events_path,
        losers_path=losers_path,
        chart_paths=chart_paths,
    )
