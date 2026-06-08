"""Capture a small live Binance Futures depth sample as JSONL."""

from avellaneda_stoikov.binance import save_live_binance_depth_snapshots_jsonl


def main() -> None:
    output_path = "data/raw/btcusdt_futures_depth_live.jsonl"
    save_live_binance_depth_snapshots_jsonl(
        path=output_path,
        symbol="BTCUSDT",
        limit=20,
        snapshot_count=10,
        interval_seconds=1.0,
    )
    print(f"saved {output_path}")


if __name__ == "__main__":
    main()
