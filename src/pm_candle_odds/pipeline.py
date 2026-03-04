from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .analysis import StrategyRules, evaluate_strategy
from .data import ApiCredentials, OhlcvApiClient, OhlcvRequest


WEEKDAY_MAP: Dict[int, str] = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
WEEKDAY_ORDER: List[str] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass
class StudyConfig:
    exchange: str = "coinbase"
    symbol: str = "BTC/USD"
    start_utc: str = ""
    end_utc: str = ""
    outdir: str = "results/generated"
    min_5m_trend_candles: int = 2
    min_aligned_1m_in_first4: int = 3
    commission_rate: float = 0.01
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
        min_5m_trend_candles=cfg.min_5m_trend_candles,
        min_aligned_1m_in_first4=cfg.min_aligned_1m_in_first4,
        commission_rate=cfg.commission_rate,
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
        min_5m_trend_candles=cfg.min_5m_trend_candles,
        min_aligned_1m_in_first4=cfg.min_aligned_1m_in_first4,
        commission_rate=cfg.commission_rate,
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

    loss_dir = outdir / "loss_analysis"
    _save_loss_groupings(events_out, loss_dir)

    from .plots import save_strategy_charts

    chart_paths = save_strategy_charts(events_out, outdir / "charts")

    return StudyOutput(
        run_id=run_id,
        summary_path=summary_path,
        events_path=events_path,
        losers_path=losers_path,
        chart_paths=chart_paths,
    )


def _save_loss_groupings(signals_df: pd.DataFrame, outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)

    if signals_df.empty:
        _save_empty_loss_files(outdir)
        return

    df = signals_df.copy()
    df["period_start"] = pd.to_datetime(df["period_start"], utc=True)
    df["loss"] = (df["win"] == 0).astype(int)

    df["hour_utc"] = df["period_start"].dt.hour
    df["weekday_num_utc"] = df["period_start"].dt.weekday
    df["weekday_utc"] = df["weekday_num_utc"].map(WEEKDAY_MAP)
    df["month_utc"] = df["period_start"].dt.strftime("%Y-%m")
    df["session_utc"] = df["hour_utc"].apply(_session_from_hour_utc)

    est_ts = df["period_start"].dt.tz_convert("America/New_York")
    df["hour_est"] = est_ts.dt.hour
    df["weekday_num_est"] = est_ts.dt.weekday
    df["weekday_est"] = df["weekday_num_est"].map(WEEKDAY_MAP)
    df["month_est"] = est_ts.dt.strftime("%Y-%m")

    _group_to_csv(df, ["hour_utc"], outdir / "losses_by_hour_utc.csv", rename_bucket="bucket")
    _group_to_csv(
        df,
        ["weekday_num_utc", "weekday_utc"],
        outdir / "losses_by_weekday_utc.csv",
        sort_by_weekday_col="weekday_utc",
        drop_cols=["weekday_num_utc"],
        rename_bucket="bucket",
    )
    _group_to_csv(df, ["month_utc"], outdir / "losses_by_month_utc.csv", rename_bucket="bucket")

    _group_to_csv(df, ["hour_est"], outdir / "losses_by_hour_est.csv", rename_bucket="bucket")
    _group_to_csv(
        df,
        ["weekday_num_est", "weekday_est"],
        outdir / "losses_by_weekday_est.csv",
        sort_by_weekday_col="weekday_est",
        drop_cols=["weekday_num_est"],
        rename_bucket="bucket",
    )
    _group_to_csv(df, ["month_est"], outdir / "losses_by_month_est.csv", rename_bucket="bucket")

    by_weekday_hour_utc = _group_core(df, ["weekday_utc", "hour_utc"])
    by_weekday_hour_utc = _sort_weekday_hour(by_weekday_hour_utc, "weekday_utc", "hour_utc")
    by_weekday_hour_utc.to_csv(outdir / "losses_by_weekday_hour_utc.csv", index=False)

    by_weekday_hour_est = _group_core(df, ["weekday_est", "hour_est"])
    by_weekday_hour_est = _sort_weekday_hour(by_weekday_hour_est, "weekday_est", "hour_est")
    by_weekday_hour_est.to_csv(outdir / "losses_by_weekday_hour_est.csv", index=False)

    by_trend = _group_core(df, ["trend_direction"])
    by_trend.to_csv(outdir / "losses_by_trend_direction.csv", index=False)

    by_session_utc = _group_core(df, ["session_utc"])
    by_session_utc = by_session_utc.sort_values("loss_rate", ascending=False).reset_index(drop=True)
    by_session_utc.to_csv(outdir / "losses_by_session_utc.csv", index=False)

    _build_avoid_windows_report(
        by_weekday_hour_utc,
        weekday_col="weekday_utc",
        hour_col="hour_utc",
        outpath=outdir / "avoid_windows_report_utc.csv",
    )
    _build_avoid_windows_report(
        by_weekday_hour_est,
        weekday_col="weekday_est",
        hour_col="hour_est",
        outpath=outdir / "avoid_windows_report_est.csv",
    )


def _save_empty_loss_files(outdir: Path) -> None:
    cols = ["bucket", "total_signals", "losses", "wins", "loss_rate"]
    detail_cols_utc = ["weekday_utc", "hour_utc", "total_signals", "losses", "wins", "loss_rate"]
    detail_cols_est = ["weekday_est", "hour_est", "total_signals", "losses", "wins", "loss_rate"]
    avoid_cols_utc = [
        "weekday_utc",
        "hour_utc",
        "total_signals",
        "losses",
        "wins",
        "loss_rate",
        "min_samples_filter",
        "label",
    ]
    avoid_cols_est = [
        "weekday_est",
        "hour_est",
        "total_signals",
        "losses",
        "wins",
        "loss_rate",
        "min_samples_filter",
        "label",
    ]

    pd.DataFrame(columns=cols).to_csv(outdir / "losses_by_hour_utc.csv", index=False)
    pd.DataFrame(columns=cols).to_csv(outdir / "losses_by_weekday_utc.csv", index=False)
    pd.DataFrame(columns=cols).to_csv(outdir / "losses_by_month_utc.csv", index=False)
    pd.DataFrame(columns=cols).to_csv(outdir / "losses_by_hour_est.csv", index=False)
    pd.DataFrame(columns=cols).to_csv(outdir / "losses_by_weekday_est.csv", index=False)
    pd.DataFrame(columns=cols).to_csv(outdir / "losses_by_month_est.csv", index=False)

    pd.DataFrame(columns=detail_cols_utc).to_csv(outdir / "losses_by_weekday_hour_utc.csv", index=False)
    pd.DataFrame(columns=detail_cols_est).to_csv(outdir / "losses_by_weekday_hour_est.csv", index=False)

    pd.DataFrame(columns=["trend_direction", "total_signals", "losses", "wins", "loss_rate"]).to_csv(
        outdir / "losses_by_trend_direction.csv", index=False
    )
    pd.DataFrame(columns=["session_utc", "total_signals", "losses", "wins", "loss_rate"]).to_csv(
        outdir / "losses_by_session_utc.csv", index=False
    )

    pd.DataFrame(columns=avoid_cols_utc).to_csv(outdir / "avoid_windows_report_utc.csv", index=False)
    pd.DataFrame(columns=avoid_cols_est).to_csv(outdir / "avoid_windows_report_est.csv", index=False)


def _group_core(df: pd.DataFrame, keys: List[str]) -> pd.DataFrame:
    out = df.groupby(keys, as_index=False).agg(total_signals=("win", "size"), losses=("loss", "sum"))
    out["wins"] = out["total_signals"] - out["losses"]
    out["loss_rate"] = out["losses"] / out["total_signals"]
    return out


def _group_to_csv(
    df: pd.DataFrame,
    keys: List[str],
    path: Path,
    drop_cols: Optional[List[str]] = None,
    rename_bucket: Optional[str] = None,
    sort_by_weekday_col: Optional[str] = None,
) -> None:
    out = _group_core(df, keys)
    if sort_by_weekday_col:
        out = _sort_weekday(out, sort_by_weekday_col)
    if drop_cols:
        out = out.drop(columns=drop_cols)
    if rename_bucket and len(keys) == 1:
        out = out.rename(columns={keys[-1]: rename_bucket})
    out.to_csv(path, index=False)


def _sort_weekday(df: pd.DataFrame, col: str) -> pd.DataFrame:
    out = df.copy()
    out[col] = pd.Categorical(out[col], categories=WEEKDAY_ORDER, ordered=True)
    out = out.sort_values(col).reset_index(drop=True)
    out[col] = out[col].astype(str)
    return out


def _sort_weekday_hour(df: pd.DataFrame, weekday_col: str, hour_col: str) -> pd.DataFrame:
    out = _sort_weekday(df, weekday_col)
    out = out.sort_values([weekday_col, hour_col]).reset_index(drop=True)
    return out


def _session_from_hour_utc(hour_utc: int) -> str:
    # Coarse UTC trading-session buckets.
    if 0 <= hour_utc < 7:
        return "Asia"
    if 7 <= hour_utc < 13:
        return "London"
    if 13 <= hour_utc < 21:
        return "New_York"
    return "Off_Hours"


def _build_avoid_windows_report(
    grouped_df: pd.DataFrame,
    weekday_col: str,
    hour_col: str,
    outpath: Path,
    min_samples_filter: int = 20,
    top_n: int = 15,
) -> None:
    cols = [weekday_col, hour_col, "total_signals", "losses", "wins", "loss_rate", "min_samples_filter", "label"]
    if grouped_df.empty:
        pd.DataFrame(columns=cols).to_csv(outpath, index=False)
        return

    report = grouped_df[grouped_df["total_signals"] >= min_samples_filter].copy()
    if report.empty:
        pd.DataFrame(columns=cols).to_csv(outpath, index=False)
        return

    report = report.sort_values(["loss_rate", "losses", "total_signals"], ascending=[False, False, False]).head(top_n)
    report["min_samples_filter"] = min_samples_filter
    report["label"] = report[weekday_col].astype(str) + "_" + report[hour_col].astype(str).str.zfill(2)
    report = report[cols].reset_index(drop=True)
    report.to_csv(outpath, index=False)
