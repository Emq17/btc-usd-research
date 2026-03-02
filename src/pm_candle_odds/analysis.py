from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


@dataclass
class StrategyRules:
    trend_5m_min_run: int = 2
    one_min_required_in_first_four: int = 3
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
        if trend == 0 or run_len < rules.trend_5m_min_run:
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
        favor_count = int((first4["direction"] == trend).sum())
        passed_count_rule = favor_count >= rules.one_min_required_in_first_four

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
                "trend_run_len": int(run_len),
                "recent4_5m_pattern": _pattern_label(recent4),
                "is_chop": bool(is_chop),
                "first4_favor_count": favor_count,
                "required_favor_count": rules.one_min_required_in_first_four,
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
                }
            ]
        )
        return summary, events

    signals = events[events["signal_active"]].copy()
    signals["point"] = np.where(signals["win"].astype(int) == 1, 1, -1)
    signals["cumulative_points"] = signals["point"].cumsum()
    signals["signal_index"] = np.arange(1, len(signals) + 1)
    signals["cumulative_win_rate"] = signals["point"].cumsum() / signals["signal_index"]

    total = int(len(signals))
    wins = int(signals["win"].sum())
    losses = total - wins
    win_rate = float(wins / total) if total else 0.0

    summary = pd.DataFrame(
        [
            {
                "total_signals": total,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
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
