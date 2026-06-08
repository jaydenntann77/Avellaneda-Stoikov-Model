"""Helpers for converting Binance-style order book data into project objects."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from avellaneda_stoikov.order_book import OrderBookSnapshot


BINANCE_USD_M_FUTURES_BASE_URL = "https://fapi.binance.com"
SUPPORTED_DEPTH_LIMITS = {5, 10, 20, 50, 100, 500, 1000}


@dataclass(frozen=True)
class BinanceOrderBook:
    """Local order book state built from Binance depth levels."""

    bids: Mapping[float, float]
    asks: Mapping[float, float]

    @classmethod
    def from_depth_message(cls, message: Mapping[str, Any]) -> "BinanceOrderBook":
        """Create local book state from a Binance-style depth message."""

        bids = _parse_price_quantity_levels(
            _get_levels(message, long_key="bids", short_key="b"),
            side_name="bids",
        )
        asks = _parse_price_quantity_levels(
            _get_levels(message, long_key="asks", short_key="a"),
            side_name="asks",
        )
        return cls(
            bids=dict(bids),
            asks=dict(asks),
        )

    def apply_depth_update(self, message: Mapping[str, Any]) -> "BinanceOrderBook":
        """Return new book state after applying Binance depth update levels.

        Binance update quantities are absolute quantities at a price level.
        Quantity 0 means the level should be removed.
        """

        if not _has_bid_or_ask_levels(message):
            raise ValueError("depth update must contain bid or ask levels.")

        next_bids = dict(self.bids)
        next_asks = dict(self.asks)
        if "b" in message or "bids" in message:
            _apply_level_updates(
                levels=next_bids,
                updates=_parse_price_quantity_levels(
                    _get_levels(message, long_key="bids", short_key="b"),
                    side_name="bids",
                ),
            )
        if "a" in message or "asks" in message:
            _apply_level_updates(
                levels=next_asks,
                updates=_parse_price_quantity_levels(
                    _get_levels(message, long_key="asks", short_key="a"),
                    side_name="asks",
                ),
            )

        return BinanceOrderBook(bids=next_bids, asks=next_asks)

    def to_snapshot(self) -> OrderBookSnapshot:
        """Convert local book state to the project snapshot object."""

        return OrderBookSnapshot.from_levels(
            bids=tuple(self.bids.items()),
            asks=tuple(self.asks.items()),
        )


def reconstruct_snapshots_from_binance_messages(
    messages: Sequence[Mapping[str, Any]],
) -> tuple[OrderBookSnapshot, ...]:
    """Reconstruct snapshots from one full depth message and later updates.

    The first message is treated as the initial full book. Each later message is
    applied as a Binance depth update, and one OrderBookSnapshot is emitted
    after every message.
    """

    if not messages:
        raise ValueError("at least one Binance depth message is required.")

    book = BinanceOrderBook.from_depth_message(messages[0])
    snapshots = [book.to_snapshot()]

    for message in messages[1:]:
        book = book.apply_depth_update(message)
        snapshots.append(book.to_snapshot())

    return tuple(snapshots)


def snapshot_from_binance_depth(message: Mapping[str, Any]) -> OrderBookSnapshot:
    """Create an OrderBookSnapshot from a Binance-style depth message.

    Binance data commonly represents price levels as strings, for example:

        ["100000.0", "0.5"]

    This helper converts those raw levels into floats, then delegates sorting
    and validation to OrderBookSnapshot.
    """

    bids = _get_levels(message, long_key="bids", short_key="b")
    asks = _get_levels(message, long_key="asks", short_key="a")
    return OrderBookSnapshot.from_levels(
        bids=_parse_price_quantity_levels(bids, side_name="bids"),
        asks=_parse_price_quantity_levels(asks, side_name="asks"),
    )


def load_binance_depth_messages_jsonl(path: str | Path) -> tuple[dict[str, Any], ...]:
    """Load Binance depth messages from a newline-delimited JSON file.

    Blank lines are ignored. Each non-blank line must be a JSON object.
    """

    messages = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        stripped_line = line.strip()
        if not stripped_line:
            continue

        try:
            message = json.loads(stripped_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number} is not valid JSON.") from exc

        if not isinstance(message, dict):
            raise ValueError(f"line {line_number} must contain a JSON object.")

        messages.append(message)

    if not messages:
        raise ValueError("JSONL file must contain at least one message.")

    return tuple(messages)


def fetch_binance_futures_depth_snapshot(
    symbol: str = "BTCUSDT",
    limit: int = 100,
    timeout_seconds: float = 10.0,
    base_url: str = BINANCE_USD_M_FUTURES_BASE_URL,
) -> dict[str, Any]:
    """Fetch one live Binance USD-M futures order book snapshot."""

    _validate_symbol(symbol)
    _validate_depth_limit(limit)
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive.")

    query = urllib.parse.urlencode({"symbol": symbol.upper(), "limit": limit})
    url = f"{base_url.rstrip('/')}/fapi/v1/depth?{query}"
    with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if not isinstance(payload, dict):
        raise ValueError("Binance depth response must be a JSON object.")
    return payload


def save_live_binance_depth_snapshots_jsonl(
    path: str | Path,
    symbol: str = "BTCUSDT",
    limit: int = 100,
    snapshot_count: int = 1,
    interval_seconds: float = 1.0,
) -> None:
    """Fetch live depth snapshots and save them as newline-delimited JSON."""

    if snapshot_count <= 0:
        raise ValueError("snapshot_count must be positive.")
    if interval_seconds < 0:
        raise ValueError("interval_seconds cannot be negative.")

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for snapshot_index in range(snapshot_count):
            message = fetch_binance_futures_depth_snapshot(symbol=symbol, limit=limit)
            file.write(json.dumps(message, separators=(",", ":")) + "\n")
            if snapshot_index < snapshot_count - 1 and interval_seconds > 0:
                time.sleep(interval_seconds)


def _get_levels(
    message: Mapping[str, Any],
    long_key: str,
    short_key: str,
) -> Any:
    if long_key in message:
        return message[long_key]
    if short_key in message:
        return message[short_key]
    raise ValueError(f"message must contain {long_key!r} or {short_key!r}.")


def _has_bid_or_ask_levels(message: Mapping[str, Any]) -> bool:
    return any(key in message for key in ("bids", "b", "asks", "a"))


def _parse_price_quantity_levels(
    raw_levels: Any,
    side_name: str,
) -> tuple[tuple[float, float], ...]:
    if not isinstance(raw_levels, Sequence) or isinstance(raw_levels, str):
        raise ValueError(f"{side_name} must be a sequence of price/quantity levels.")

    parsed_levels = []
    for raw_level in raw_levels:
        if not isinstance(raw_level, Sequence) or isinstance(raw_level, str):
            raise ValueError(f"each {side_name} level must be a price/quantity pair.")
        if len(raw_level) != 2:
            raise ValueError(f"each {side_name} level must contain exactly two values.")

        price, quantity = raw_level
        try:
            parsed_levels.append((float(price), float(quantity)))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{side_name} levels must contain numeric values.") from exc

    return tuple(parsed_levels)


def _apply_level_updates(
    levels: dict[float, float],
    updates: tuple[tuple[float, float], ...],
) -> None:
    for price, quantity in updates:
        if quantity == 0:
            levels.pop(price, None)
        else:
            levels[price] = quantity


def _validate_symbol(symbol: str) -> None:
    if not symbol or not symbol.isalnum():
        raise ValueError("symbol must be a non-empty alphanumeric string.")


def _validate_depth_limit(limit: int) -> None:
    if limit not in SUPPORTED_DEPTH_LIMITS:
        raise ValueError(f"limit must be one of {sorted(SUPPORTED_DEPTH_LIMITS)}.")
