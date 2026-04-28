"""
External market data signals for trade gating.
All sources are free, no API key required, and work globally (including GCP VMs).

Sources:
  - OKX:   funding rates (replaces Binance fapi which is geo-blocked on GCP US/EU)
  - Bybit: open interest % change (also geo-unblocked)
  - alternative.me: Fear & Greed (already used, re-exported here for convenience)
"""
import requests

# Symbol maps: our pair format → exchange format
OKX_SYMBOLS   = {"BTC/USD": "BTC-USDT-SWAP", "ETH/USD": "ETH-USDT-SWAP", "SOL/USD": "SOL-USDT-SWAP"}
BYBIT_SYMBOLS  = {"BTC/USD": "BTCUSDT",        "ETH/USD": "ETHUSDT",        "SOL/USD": "SOLUSDT"}

TIMEOUT = 6  # seconds per request


# ---------------------------------------------------------------------------
# 1. Funding Rate — OKX (free, no key, globally accessible)
# ---------------------------------------------------------------------------

def get_funding_rate(pair: str) -> float | None:
    """
    Returns the current 8h funding rate as a decimal (e.g. 0.0001 = 0.01%).
    Positive = longs pay shorts (market is long-biased).
    Negative = shorts pay longs (market is short-biased).
    Returns None on any error.
    """
    sym = OKX_SYMBOLS.get(pair)
    if not sym:
        return None
    try:
        r = requests.get(
            "https://www.okx.com/api/v5/public/funding-rate",
            params={"instId": sym},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return None
        data = r.json().get("data", [])
        if not data:
            return None
        return float(data[0]["fundingRate"])
    except Exception:
        return None


def is_funding_overcrowded(pair: str, threshold: float = 0.0008) -> bool:
    """
    Returns True if funding rate is extreme enough to suggest the trade is crowded.
    Threshold default: 0.08% per 8h (= ~3% annualised cost to hold longs).
    At this level, the long side is crowded enough to veto new buys.
    Returns False (safe to trade) if the API is unavailable.
    """
    rate = get_funding_rate(pair)
    if rate is None:
        return False  # if data unavailable, don't block the trade
    crowded = abs(rate) > threshold
    direction = "LONG-crowded" if rate > 0 else "SHORT-crowded"
    if crowded:
        print(f"  [market_data] {pair} funding {rate*100:+.4f}% → {direction}, VETO")
    else:
        print(f"  [market_data] {pair} funding {rate*100:+.4f}% → neutral")
    return crowded


# ---------------------------------------------------------------------------
# 2. Open Interest % Change — Bybit (free, no key, globally accessible)
# ---------------------------------------------------------------------------

def get_oi_change_pct(pair: str, lookback_hours: int = 4) -> float | None:
    """
    Returns the % change in open interest over the last `lookback_hours` hours.
    Positive = OI is growing (more leverage being added).
    Negative = OI is shrinking (leverage being removed / liquidated).
    Returns None on any error.
    """
    sym = BYBIT_SYMBOLS.get(pair)
    if not sym:
        return None
    try:
        r = requests.get(
            "https://api.bybit.com/v5/market/open-interest",
            params={
                "category": "linear",
                "symbol": sym,
                "intervalTime": "1h",
                "limit": lookback_hours + 1,  # +1 so we have a prior point
            },
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return None
        rows = r.json().get("result", {}).get("list", [])
        if len(rows) < 2:
            return None
        current = float(rows[0]["openInterest"])
        prior   = float(rows[-1]["openInterest"])
        if prior == 0:
            return None
        return (current - prior) / prior * 100.0
    except Exception:
        return None


def is_oi_danger(pair: str, oi_rise_pct: float = 5.0) -> bool:
    """
    Returns True if OI is rising fast (>oi_rise_pct% in 4h) — signals
    leverage buildup that hasn't been confirmed by price. Often precedes
    a flush. Use as a soft veto on new buys in this condition.
    Returns False (safe) if data unavailable.
    """
    chg = get_oi_change_pct(pair)
    if chg is None:
        return False
    danger = chg > oi_rise_pct
    print(f"  [market_data] {pair} OI change {chg:+.2f}% (4h) → {'DANGER' if danger else 'OK'}")
    return danger


# ---------------------------------------------------------------------------
# 3. Combined gate — call this from hourly_trader
# ---------------------------------------------------------------------------

def is_market_safe_to_buy(pair: str) -> bool:
    """
    Master buy-safety check combining all external signals.
    Returns True if safe to buy, False if any signal vetoes the trade.

    Veto conditions:
      - Funding rate extreme (> 0.08% absolute) → market overcrowded
      - OI rising > 5% in 4h → unconfirmed leverage buildup

    Designed to fail-open: if APIs are down, returns True so the bot
    doesn't go silent. Logs the reason for any veto.
    """
    if is_funding_overcrowded(pair):
        print(f"  [market_data] {pair} → BUY VETOED by funding rate")
        return False

    if is_oi_danger(pair):
        print(f"  [market_data] {pair} → BUY VETOED by OI buildup")
        return False

    return True
