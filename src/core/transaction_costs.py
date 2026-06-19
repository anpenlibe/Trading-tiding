"""Indian equity transaction-cost model (NSE, Zerodha schedule).

Real trading friction is far more than a flat per-trade fee: it is a stack of
regulatory + exchange + broker charges, several of which are *asymmetric*
(applied to only the buy or only the sell side) and *product-dependent*
(delivery vs intraday). A flat commission cannot express that, so a backtest
that uses one systematically understates costs and overstates returns.

This module centralises the whole schedule as auditable rate constants and a
single pure function, ``compute_charges(turnover, side, product)``. Rates are
the publicly documented NSE/Zerodha figures (review against the latest budget
when they change — STT in particular is revised in Union Budgets).

Charge stack (per leg, on a turnover = price * quantity):
  - Brokerage      : delivery ₹0; intraday min(₹20, 0.03% of turnover)
  - STT            : delivery 0.1% both sides; intraday 0.025% sell-only
  - Exchange txn   : NSE equity ~0.00297% of turnover (both sides)
  - SEBI charges   : ₹10 per crore (both sides)
  - Stamp duty     : delivery 0.015% buy-only; intraday 0.003% buy-only
  - GST            : 18% on (brokerage + exchange txn + SEBI)
  - DP charge      : delivery sell-only flat fee (depository, incl. GST)

STT, exchange, SEBI and stamp duty are broker-independent — switching brokers
does not change them. Only brokerage and DP are Zerodha-specific here.
"""

from src.data.config import TRADING_PRODUCT

# --- Rate schedule (decimals of turnover unless noted) ---------------------
# Brokerage
INTRADAY_BROKERAGE_RATE = 0.0003   # 0.03%
INTRADAY_BROKERAGE_CAP = 20.0      # ₹20 per executed order

# Securities Transaction Tax (STT)
STT_DELIVERY = 0.001    # 0.1% on BOTH buy and sell
STT_INTRADAY_SELL = 0.00025  # 0.025% on SELL only

# Exchange transaction charge (NSE equity)
EXCHANGE_TXN_RATE = 0.0000297  # 0.00297%, both sides

# SEBI turnover charge: ₹10 per crore = 10 / 1e7
SEBI_RATE = 0.000001

# Stamp duty (buy side only)
STAMP_DUTY_DELIVERY = 0.00015  # 0.015%
STAMP_DUTY_INTRADAY = 0.00003  # 0.003%

# GST on (brokerage + exchange txn + SEBI)
GST_RATE = 0.18

# Depository (DP) charge: delivery SELL only, flat per scrip per day, incl. GST.
# Zerodha ₹13.5 + CDSL, ~₹15.93 with GST.
DELIVERY_SELL_DP_CHARGE = 15.93


def _brokerage(turnover: float, product: str) -> float:
    """Broker commission for one leg. Delivery is free; intraday is capped."""
    if product == "intraday":
        return min(INTRADAY_BROKERAGE_CAP, INTRADAY_BROKERAGE_RATE * turnover)
    return 0.0


def _stt(turnover: float, side: str, product: str) -> float:
    """Securities Transaction Tax — asymmetric by side and product."""
    if product == "intraday":
        return STT_INTRADAY_SELL * turnover if side == "SELL" else 0.0
    return STT_DELIVERY * turnover  # delivery: both sides


def _stamp_duty(turnover: float, side: str, product: str) -> float:
    """Stamp duty applies to the BUY leg only."""
    if side != "BUY":
        return 0.0
    rate = STAMP_DUTY_INTRADAY if product == "intraday" else STAMP_DUTY_DELIVERY
    return rate * turnover


def compute_charges(turnover: float, side: str, product: str = TRADING_PRODUCT) -> float:
    """Total transaction charges for one leg of a trade.

    Args:
        turnover: price * quantity for this leg (use the fill price, i.e.
            slippage-adjusted, so charges are levied on what actually traded).
        side: "BUY" or "SELL" (case-insensitive).
        product: "delivery" (default) or "intraday".

    Returns:
        Total charges in ₹ (brokerage + STT + exchange + SEBI + GST + stamp
        duty + any DP charge), rounded to paise.
    """
    side = side.upper()
    product = product.lower()
    if turnover <= 0:
        return 0.0

    brokerage = _brokerage(turnover, product)
    exchange = EXCHANGE_TXN_RATE * turnover
    sebi = SEBI_RATE * turnover
    gst = GST_RATE * (brokerage + exchange + sebi)
    stt = _stt(turnover, side, product)
    stamp = _stamp_duty(turnover, side, product)

    dp = DELIVERY_SELL_DP_CHARGE if (product == "delivery" and side == "SELL") else 0.0

    total = brokerage + stt + exchange + sebi + gst + stamp + dp
    return round(total, 2)
