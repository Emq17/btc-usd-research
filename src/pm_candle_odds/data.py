from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd


TIMEFRAME_MS: Dict[str, int] = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "10m": 600_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}

PANDAS_FREQ: Dict[str, str] = {
    "1m": "1min",
    "3m": "3min",
    "5m": "5min",
    "10m": "10min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "1d": "1d",
}


@dataclass
class OhlcvRequest:
    exchange: str
    symbol: str
    timeframe: str
    start_utc: str
    end_utc: str
    limit_per_call: int = 1000


@dataclass
class ApiCredentials:
    api_key: str = ""
    api_secret: str = ""
    api_password: str = ""

    @classmethod
    def from_env(cls) -> "ApiCredentials":
        return cls(
            api_key=os.getenv("PM_EXCHANGE_API_KEY", ""),
            api_secret=os.getenv("PM_EXCHANGE_API_SECRET", ""),
            api_password=os.getenv("PM_EXCHANGE_API_PASSWORD", ""),
        )


class OhlcvApiClient:
    def __init__(self, exchange_name: str, credentials: Optional[ApiCredentials] = None) -> None:
        import ccxt  # local import so package import works without ccxt installed

        if not hasattr(ccxt, exchange_name):
            raise ValueError(f"Unsupported exchange: {exchange_name}")

        credentials = credentials or ApiCredentials()
        opts = {"enableRateLimit": True, "timeout": 30_000}
        if credentials.api_key:
            opts["apiKey"] = credentials.api_key
        if credentials.api_secret:
            opts["secret"] = credentials.api_secret
        if credentials.api_password:
            opts["password"] = credentials.api_password

        exchange_cls = getattr(ccxt, exchange_name)
        self.exchange = exchange_cls(opts)
        self.exchange.load_markets()

    def fetch_ohlcv_range(self, req: OhlcvRequest) -> pd.DataFrame:
        start_ms = _to_utc_ms(req.start_utc)
        end_ms = _to_utc_ms(req.end_utc)
        if end_ms <= start_ms:
            raise ValueError("end_utc must be after start_utc")

        if req.timeframe not in TIMEFRAME_MS:
            raise ValueError(f"Unsupported timeframe: {req.timeframe}")

        native_timeframes = self.exchange.timeframes or {}
        if req.timeframe in native_timeframes:
            return self._fetch_native(req, start_ms, end_ms)

        fallback_tf = _best_supported_sub_timeframe(req.timeframe, list(native_timeframes.keys()))
        if not fallback_tf:
            raise ValueError(
                f"Exchange {self.exchange.id} does not support requested timeframe {req.timeframe}, "
                "and no lower timeframe was available for resampling."
            )

        fallback_req = OhlcvRequest(
            exchange=req.exchange,
            symbol=req.symbol,
            timeframe=fallback_tf,
            start_utc=req.start_utc,
            end_utc=req.end_utc,
            limit_per_call=req.limit_per_call,
        )
        base_df = self._fetch_native(fallback_req, start_ms, end_ms)
        return _resample_ohlcv(base_df, target_timeframe=req.timeframe, end_ms=end_ms)

    def _fetch_native(self, req: OhlcvRequest, start_ms: int, end_ms: int) -> pd.DataFrame:
        rows: List[List[float]] = []
        since = start_ms
        step_ms = TIMEFRAME_MS[req.timeframe]

        while since < end_ms:
            try:
                batch = self.exchange.fetch_ohlcv(
                    symbol=req.symbol,
                    timeframe=req.timeframe,
                    since=since,
                    limit=req.limit_per_call,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to fetch candles from {self.exchange.id} for {req.symbol} "
                    f"at {req.timeframe}. Check symbol/timeframe support and network access."
                ) from exc
            if not batch:
                break

            rows.extend(batch)
            last_open_ms = int(batch[-1][0])
            next_since = last_open_ms + step_ms
            if next_since <= since:
                break
            since = next_since

        if not rows:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        df = pd.DataFrame(rows, columns=["open_ms", "open", "high", "low", "close", "volume"])
        df = df.drop_duplicates(subset=["open_ms"]).sort_values("open_ms")
        df = df[df["open_ms"] < end_ms].copy()
        df["timestamp"] = pd.to_datetime(df["open_ms"], unit="ms", utc=True)
        df = df[["timestamp", "open", "high", "low", "close", "volume"]].reset_index(drop=True)
        return df


def _to_utc_ms(value: str) -> int:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _best_supported_sub_timeframe(target: str, available: List[str]) -> Optional[str]:
    target_ms = TIMEFRAME_MS[target]
    candidates = [tf for tf in available if tf in TIMEFRAME_MS and target_ms % TIMEFRAME_MS[tf] == 0]
    if not candidates:
        return None
    return min(candidates, key=lambda tf: target_ms // TIMEFRAME_MS[tf])


def _resample_ohlcv(df: pd.DataFrame, target_timeframe: str, end_ms: int) -> pd.DataFrame:
    if df.empty:
        return df
    freq = PANDAS_FREQ[target_timeframe]
    out = df.copy()
    out = out.set_index("timestamp")
    agg = out.resample(freq, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    agg = agg.dropna(subset=["open", "high", "low", "close"]).reset_index()
    agg = agg[agg["timestamp"] < pd.to_datetime(end_ms, unit="ms", utc=True)].reset_index(drop=True)
    return agg
