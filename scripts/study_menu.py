from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if str(Path(__file__).resolve().parents[1] / "src") not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pm_candle_odds.pipeline import default_start_end


def ask(prompt: str, default: str) -> str:
    val = input(f"{prompt} [{default}]: ").strip()
    return val if val else default


def ask_bool(prompt: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    val = input(f"{prompt} [{hint}]: ").strip().lower()
    if not val:
        return default
    return val in {"y", "yes"}


def build_command() -> list:
    start_default, end_default = default_start_end(days=30)

    exchange = ask("Exchange (ccxt id)", "coinbase")
    symbol = ask("Symbol", "BTC/USD")
    start = ask("Start UTC", start_default)
    end = ask("End UTC", end_default)
    outdir = ask("Output directory", "results/generated")

    min_5m_trend_candles = ask("Minimum 5m trend candles", "2")
    min_aligned_1m_in_first4 = ask("Minimum aligned 1m candles in first 4", "3")
    commission_rate = ask("Commission rate per signal (decimal)", "0.01")

    disable_breakout = ask_bool("Disable counter-breakout invalidation", default=False)
    allow_chop = ask_bool("Allow chop (alternating 5m candles)", default=False)
    ignore_keys = ask_bool("Ignore API keys from env (PM_EXCHANGE_API_*)", default=False)

    cmd = [
        sys.executable,
        "scripts/run_study.py",
        "--exchange",
        exchange,
        "--symbol",
        symbol,
        "--start",
        start,
        "--end",
        end,
        "--outdir",
        outdir,
        "--min-5m-trend-candles",
        min_5m_trend_candles,
        "--min-aligned-1m-in-first4",
        min_aligned_1m_in_first4,
        "--commission-rate",
        commission_rate,
    ]

    if disable_breakout:
        cmd.append("--no-breakout-invalidation")
    if allow_chop:
        cmd.append("--allow-chop")
    if ignore_keys:
        cmd.append("--no-api-keys")

    return cmd


def main() -> None:
    print("\nBTC/USD Strategy Research Menu\n")
    print("Rule settings are named for readability in output tables and file exports.\n")

    while True:
        cmd = build_command()
        print("\nRunning:")
        print(" ".join(cmd))
        subprocess.run(cmd, check=False)
        if not ask_bool("Run another study?", default=False):
            break


if __name__ == "__main__":
    main()
