from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


@dataclass
class StrategyRules:
    min_5m_trend_candles: int = 2
    min_aligned_1m_in_first4: int = 3
    commission_rate: float = 0.01
    invalidate_on_counter_breakout: bool = True
    skip_chop: bool = True


@dataclass
class StrategySummary:
    total_signals: int
    wins: int
    losses: int
    win_rate: float


def evaluate_strategy(
    five_min_df: pd.DataFrame,
    one_min_df: pd.DataFrame,
    rules: StrategyRules,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    five = _prep(five_min_df)
    one = _prep(one_min_df)

    records: List[Dict] = []

    for i in range(4, len(five)):
        target = five.iloc[i]
        prev = five.iloc[:i]
        trend, run_len = _detect_trend(prev["direction"].tolist())
        if trend == 0 or run_len < rules.min_5m_trend_candles:
            continue

        recent4 = prev.tail(4)["direction"].tolist()
        is_chop = _is_alternating(recent4)
        if rules.skip_chop and is_chop:
            continue

        start = target["timestamp"]
        end = start + pd.Timedelta(minutes=5)
        chunk = one[(one["timestamp"] >= start) & (one["timestamp"] < end)].sort_values("timestamp")
        if len(chunk) < 4:
            continue

        first4 = chunk.head(4).copy()
        aligned_1m_count = int((first4["direction"] == trend).sum())
        passed_count_rule = aligned_1m_count >= rules.min_aligned_1m_in_first4

        invalidated_breakout = False
        invalid_reason = ""
        if rules.invalidate_on_counter_breakout:
            invalidated_breakout, invalid_reason = _counter_breakout_invalidation(first4, trend)

        signal_active = passed_count_rule and not invalidated_breakout
        outcome_win = bool(target["direction"] == trend) if signal_active else False

        records.append(
            {
                "period_start": start,
                "period_end": end,
                "trend_direction": _dir_label(trend),
                "current_5m_trend_length": int(run_len),
                "recent4_5m_pattern": _pattern_label(recent4),
                "is_chop": bool(is_chop),
                "aligned_1m_in_first4": aligned_1m_count,
                "required_aligned_1m_in_first4": rules.min_aligned_1m_in_first4,
                "passed_count_rule": bool(passed_count_rule),
                "invalidated_counter_breakout": bool(invalidated_breakout),
                "invalid_reason": invalid_reason,
                "signal_active": bool(signal_active),
                "target_5m_direction": _dir_label(int(target["direction"])),
                "win": int(outcome_win),
            }
        )

    events = pd.DataFrame(records)
    if events.empty:
        summary = pd.DataFrame(
            [
                {
                    "total_signals": 0,
                    "wins": 0,
                    "losses": 0,
                    "win_rate": 0.0,
                    "commission_rate": float(rules.commission_rate),
                    "gross_points": 0.0,
                    "net_points_after_commission": 0.0,
                    "avg_net_point": 0.0,
                }
            ]
        )
        return summary, events

    signals = events[events["signal_active"]].copy()
    signals["gross_point"] = np.where(signals["win"].astype(int) == 1, 1.0, -1.0)
    signals["commission_rate"] = float(rules.commission_rate)
    signals["point"] = signals["gross_point"] - signals["commission_rate"]
    signals["cumulative_points"] = signals["point"].cumsum()
    signals["cumulative_gross_points"] = signals["gross_point"].cumsum()
    signals["signal_index"] = np.arange(1, len(signals) + 1)
    signals["cumulative_win_rate"] = signals["win"].cumsum() / signals["signal_index"]

    total = int(len(signals))
    wins = int(signals["win"].sum())
    losses = total - wins
    win_rate = float(wins / total) if total else 0.0
    gross_points = float(signals["gross_point"].sum()) if total else 0.0
    net_points_after_commission = float(signals["point"].sum()) if total else 0.0
    avg_net_point = float(net_points_after_commission / total) if total else 0.0

    summary = pd.DataFrame(
        [
            {
                "total_signals": total,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "commission_rate": float(rules.commission_rate),
                "gross_points": gross_points,
                "net_points_after_commission": net_points_after_commission,
                "avg_net_point": avg_net_point,
            }
        ]
    )
    return summary, signals


def _prep(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy().sort_values("timestamp").reset_index(drop=True)
    out["direction"] = np.where(out["close"] > out["open"], 1, np.where(out["close"] < out["open"], -1, 0))
    return out


def _detect_trend(history: List[int]) -> Tuple[int, int]:
    if not history:
        return 0, 0
    last = history[-1]
    if last == 0:
        return 0, 0
    run = 1
    for v in reversed(history[:-1]):
        if v == last:
            run += 1
        else:
            break
    return last, run


def _is_alternating(values: List[int]) -> bool:
    if len(values) < 4:
        return False
    if any(v == 0 for v in values):
        return False
    return values[0] != values[1] and values[1] != values[2] and values[2] != values[3] and values[0] == values[2] and values[1] == values[3]


def _counter_breakout_invalidation(first4: pd.DataFrame, trend: int) -> Tuple[bool, str]:
    anchor = first4.iloc[0]
    if trend == -1:
        counter = first4[first4["direction"] == 1]
        if not counter.empty and float(counter["close"].max()) > float(anchor["high"]):
            return True, "counter_green_closed_above_first_high"
    if trend == 1:
        counter = first4[first4["direction"] == -1]
        if not counter.empty and float(counter["close"].min()) < float(anchor["low"]):
            return True, "counter_red_closed_below_first_low"
    return False, ""


def _dir_label(v: int) -> str:
    if v > 0:
        return "up"
    if v < 0:
        return "down"
    return "flat"


def _pattern_label(values: List[int]) -> str:
    if not values:
        return ""
    map_ = {1: "G", -1: "R", 0: "D"}
    return "".join(map_[v] for v in values)
