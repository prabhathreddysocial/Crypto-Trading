import requests
from config import ALPACA_KEY, ALPACA_SECRET, BASE_URL

HEADERS = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET}
POSITION_SIZE_USD = 5000


def get_account():
    r = requests.get(f"{BASE_URL}/v2/account", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def get_positions():
    r = requests.get(f"{BASE_URL}/v2/positions", headers=HEADERS)
    r.raise_for_status()
    return {p["symbol"]: p for p in r.json()}


def get_open_orders():
    r = requests.get(f"{BASE_URL}/v2/orders?status=open", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def place_order(symbol: str, side: str, usd_amount: float, current_price: float = None):
    """
    Places a market order using notional (USD) amount.
    `current_price` is kept for signature compatibility but unused — Alpaca
    handles the conversion when notional is specified.
    """
    alpaca_symbol = symbol.replace("/", "")
    payload = {
        "symbol": alpaca_symbol,
        "notional": str(round(usd_amount, 2)),   # dollar amount, no qty math needed
        "side": side,
        "type": "market",
        "time_in_force": "gtc",
    }
    r = requests.post(f"{BASE_URL}/v2/orders", headers=HEADERS, json=payload)
    if not r.ok:
        raise Exception(f"Alpaca order error {r.status_code}: {r.text}")
    return r.json()


def close_position(symbol: str):
    alpaca_symbol = symbol.replace("/", "")
    r = requests.delete(f"{BASE_URL}/v2/positions/{alpaca_symbol}", headers=HEADERS)
    if r.status_code in (200, 204):
        return True
    return False


def manage_exits(positions: dict, take_profit=0.06, stop_loss=0.03,
                 max_hold_hours=72) -> list:
    """
    Exit rules (checked in priority order):
    1. Take profit  : unrealized P&L >= +6%
    2. Stop loss    : unrealized P&L <= -3%
    3. Time exit    : position held longer than max_hold_hours (default 72h)
       Prevents stale positions sitting idle for weeks with no TP/SL trigger.
    """
    from datetime import datetime, timezone
    closed = []
    now = datetime.now(timezone.utc)

    for symbol, pos in positions.items():
        pnl_pct = float(pos["unrealized_plpc"])
        slash_symbol = symbol.replace("USD", "/USD")

        if pnl_pct >= take_profit:
            print(f"  TAKE PROFIT {symbol}: +{pnl_pct*100:.2f}%")
            close_position(slash_symbol)
            closed.append(symbol)

        elif pnl_pct <= -stop_loss:
            print(f"  STOP LOSS {symbol}: {pnl_pct*100:.2f}%")
            close_position(slash_symbol)
            closed.append(symbol)

        else:
            # Time-based exit: close if held too long without hitting TP/SL
            created_at_str = pos.get("created_at") or pos.get("updated_at", "")
            try:
                # Alpaca returns ISO format: "2026-04-22T18:48:18Z"
                created_at = datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )
                hold_hours = (now - created_at).total_seconds() / 3600
                if hold_hours >= max_hold_hours:
                    print(f"  TIME EXIT {symbol}: held {hold_hours:.1f}h (P&L: {pnl_pct*100:+.2f}%)")
                    close_position(slash_symbol)
                    closed.append(symbol)
            except Exception:
                pass  # skip time check if timestamp parse fails

    return closed


def execute_signal(symbol: str, signal: int, df, positions: dict, strategy: str = "") -> str:
    """
    positions is a dict keyed by Alpaca symbol (e.g. "BTCUSD").
    signal: 1 = buy, -1 = sell, 0 = hold.
    Caller is responsible for gating on has_position before calling this.
    """
    alpaca_symbol = symbol.replace("/", "")
    current_price = float(df["close"].iloc[-1])
    has_position = alpaca_symbol in positions  # dict key lookup — O(1), correct

    if signal == 1 and not has_position:
        print(f"    → Placing BUY {symbol} @ ${current_price:,.2f} (${POSITION_SIZE_USD})")
        try:
            order = place_order(symbol, "buy", POSITION_SIZE_USD, current_price)
            print(f"    → Order placed: {order.get('id', 'unknown')} status={order.get('status')}")
            return "bought"
        except Exception as e:
            print(f"    → BUY FAILED: {e}")
            return f"failed: {e}"

    elif signal == -1 and has_position:
        print(f"    → Placing SELL {symbol} @ ${current_price:,.2f}")
        try:
            result = close_position(symbol)
            print(f"    → Position closed: {result}")
            return "sold"
        except Exception as e:
            print(f"    → SELL FAILED: {e}")
            return f"failed: {e}"

    return "hold"
