from __future__ import annotations
"""Quick diagnostic script to check BacktestingDataProvider.get_candles_df.
Run inside the backend-api Docker container (or conda env):

    conda run -n backend-api python /backend-api/utils/check_candles.py
"""

from datetime import datetime, timezone

from hummingbot.strategy_v2.backtesting.backtesting_data_provider import (
    BacktestingDataProvider,
)


def ts(date_str: str) -> int:
    """YYYY-MM-DD → unix timestamp (UTC midnight)."""
    y, m, d = map(int, date_str.split("-"))
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp())


def main() -> None:
    provider = BacktestingDataProvider()
    provider.start_time = ts("2024-03-11")
    provider.end_time = ts("2024-03-13")

    print(
        "Testing KuCoin BTC-USDT 3m candles from",
        provider.start_time,
        "to",
        provider.end_time,
    )

    for n in [50, 75, 100, 126, 142, 160]:
        try:
            df = provider.get_candles_df("kucoin", "BTC-USDT", "3m", n)
            if df is None:
                status = "None"
            else:
                status = f"{len(df)} rows"
        except Exception as e:  # pragma: no cover
            status = f"Exception: {e}"
        print(f"max_records={n:<3} -> {status}")


if __name__ == "__main__":
    main() 