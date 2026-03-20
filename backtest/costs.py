"""
IDX Transaction Cost Model
============================
Realistic cost model for backtesting IDX trades.

Costs:
  - Buy commission:  0.15% of trade value
  - Sell commission: 0.25% of trade value (includes 0.1% final income tax)
  - Slippage: 1 tick adverse per trade

IDX tick-size bands:
  Rp 1–50      → Rp 1
  Rp 51–200    → Rp 2
  Rp 201–500   → Rp 5
  Rp 501–2000  → Rp 10
  Rp 2001–5000 → Rp 25
  Rp 5001+     → Rp 50
"""

import logging
from typing import Optional

from config import (
    BUY_COMMISSION, SELL_COMMISSION, SLIPPAGE_TICKS,
    TICK_SIZE_TABLE, LOT_SIZE,
)

logger = logging.getLogger(__name__)


def get_tick_size(price: float) -> float:
    """Return the IDX tick size for a given price level."""
    for lower, upper, tick in TICK_SIZE_TABLE:
        if lower <= price <= upper:
            return tick
    return 50  # default for very high prices


def round_to_tick(price: float, direction: str = "nearest") -> float:
    """
    Round a price to the nearest valid tick.

    direction: "up", "down", or "nearest"
    """
    tick = get_tick_size(price)
    if direction == "up":
        return tick * ((price + tick - 1) // tick)
    elif direction == "down":
        return tick * (price // tick)
    else:
        return tick * round(price / tick)


def round_to_lot(shares: int) -> int:
    """Round shares down to nearest lot (100 shares)."""
    return (shares // LOT_SIZE) * LOT_SIZE


def compute_buy_cost(price: float, shares: int) -> dict:
    """
    Compute total cost of buying shares on IDX.

    Returns:
        {
            "exec_price": execution price after slippage,
            "gross_value": shares × exec_price,
            "commission": commission in IDR,
            "total_cost": gross_value + commission,
            "avg_cost_per_share": total_cost / shares,
        }
    """
    tick = get_tick_size(price)
    exec_price = price + (SLIPPAGE_TICKS * tick)  # adverse: price goes up

    gross_value = exec_price * shares
    commission = gross_value * BUY_COMMISSION

    total = gross_value + commission

    return {
        "exec_price": exec_price,
        "gross_value": gross_value,
        "commission": commission,
        "total_cost": total,
        "avg_cost_per_share": total / shares if shares > 0 else 0,
    }


def compute_sell_proceeds(price: float, shares: int) -> dict:
    """
    Compute total proceeds from selling shares on IDX.

    Returns:
        {
            "exec_price": execution price after slippage,
            "gross_value": shares × exec_price,
            "commission": commission in IDR (includes tax),
            "net_proceeds": gross_value - commission,
            "avg_price_per_share": net_proceeds / shares,
        }
    """
    tick = get_tick_size(price)
    exec_price = price - (SLIPPAGE_TICKS * tick)  # adverse: price goes down
    exec_price = max(exec_price, tick)  # can't go below minimum tick

    gross_value = exec_price * shares
    commission = gross_value * SELL_COMMISSION

    net = gross_value - commission

    return {
        "exec_price": exec_price,
        "gross_value": gross_value,
        "commission": commission,
        "net_proceeds": net,
        "avg_price_per_share": net / shares if shares > 0 else 0,
    }


def compute_round_trip_cost_pct(price: float) -> float:
    """
    Compute the total round-trip cost as a % of entry price.
    Useful for knowing the minimum move needed to break even.
    """
    tick = get_tick_size(price)
    slippage_cost = 2 * SLIPPAGE_TICKS * tick  # buy + sell slippage
    commission_cost = price * (BUY_COMMISSION + SELL_COMMISSION)
    total_cost = slippage_cost + commission_cost
    return total_cost / price
