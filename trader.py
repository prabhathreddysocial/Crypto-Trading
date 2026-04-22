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


def place_order(symbol: str, side: str, usd_amount: float, current_price: float):
    alpaca_symbol = symbol.replace("/", "")
    qty = round(usd_amount / current_price, 6)
    payload = {
        "symbol": alpaca_symbol,
        "qty": str(qty),
        "side": side,
        "type": "market",
        "time_in_force": "gtc",
    }
    r = requests.post(f"{BASE_URL}/v2/orders", headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()


def close_position(symbol: str):
    alpaca_symbol = symbol.replace("/", "")
    r = requests.delete(f"{BASE_URL}/v2/positions/{alpaca_symbol}", headers=HEADERS)
    if r.status_code in (200, 204):
        return True
    return False


def manage_exits(positions: dict, take_profit=0.06, stop_loss=0.03) -> list:
    closed = []
    for symbol, pos in positions.items():
        pnl_pct = float(pos["unrealized_plpc"])
        if pnl_pct >= take_profit:
            print(f"  TAKE PROFIT {symbol}: +{pnl_pct*100:.2f}%")
            close_position(symbol.replace("USD", "/USD"))
            closed.append(symbol)
        elif pnl_pct <= -stop_loss:
            print(f"  STOP LOSS {symbol}: {pnl_pct*100:.2f}%")
            close_position(symbol.replace("USD", "/USD"))
            closed.append(symbol)
    return closed


def execute_signal(symbol: str, signal: int, df, positions: dict, strategy: str = "") -> str:
    alpaca_symbol = symbol.replace("/", "")
    current_price = float(df["close"].iloc[-1])
    has_position = alpaca_symbol in (p["symbol"] for p in positions)

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
