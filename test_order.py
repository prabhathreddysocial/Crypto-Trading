"""
Quick smoke-test for Alpaca paper trading order pipeline.
Runs three checks:
  1. Account connectivity + buying power
  2. Current positions (dict key format)
  3. Places a tiny REAL test order for BTC/USD ($10 notional) and prints result
Run once from the VM:  python test_order.py
"""
import requests
from config import ALPACA_KEY, ALPACA_SECRET, BASE_URL

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET,
}

print("=" * 55)
print("STEP 1 — Account connectivity")
print("=" * 55)
r = requests.get(f"{BASE_URL}/v2/account", headers=HEADERS)
if r.status_code != 200:
    print(f"  FAIL: {r.status_code} {r.text}")
    exit(1)
acct = r.json()
print(f"  Status      : {acct.get('status')}")
print(f"  Buying power: ${float(acct.get('buying_power', 0)):,.2f}")
print(f"  Cash        : ${float(acct.get('cash', 0)):,.2f}")

print()
print("=" * 55)
print("STEP 2 — Open positions (checking dict key format)")
print("=" * 55)
r = requests.get(f"{BASE_URL}/v2/positions", headers=HEADERS)
positions_raw = r.json()
if isinstance(positions_raw, list):
    positions = {p["symbol"]: p for p in positions_raw}
    print(f"  {len(positions)} open position(s)")
    for sym, p in positions.items():
        print(f"    {sym}: qty={p['qty']} unrealized_pl={p['unrealized_pl']}")
    if not positions:
        print("  (none — expected for a fresh account)")
else:
    print(f"  Unexpected response: {positions_raw}")

print()
print("=" * 55)
print("STEP 3 — Place a $10 test BUY order for BTC/USD")
print("=" * 55)
# Using notional (dollar amount) instead of qty to avoid precision issues
payload = {
    "symbol": "BTCUSD",
    "notional": "10",          # $10 worth — tiny, safe for a smoke test
    "side": "buy",
    "type": "market",
    "time_in_force": "gtc",
}
r = requests.post(f"{BASE_URL}/v2/orders", headers=HEADERS, json=payload)
print(f"  HTTP status : {r.status_code}")
print(f"  Response    : {r.text[:500]}")

if r.status_code in (200, 201):
    order = r.json()
    print()
    print(f"  ✅ ORDER PLACED SUCCESSFULLY")
    print(f"     ID     : {order.get('id')}")
    print(f"     Status : {order.get('status')}")
    print(f"     Symbol : {order.get('symbol')}")
    print(f"     Side   : {order.get('side')}")
    print(f"     Notional: {order.get('notional')}")

    # Cancel it right away so it doesn't sit on the books
    print()
    print("  Cancelling test order...")
    c = requests.delete(f"{BASE_URL}/v2/orders/{order['id']}", headers=HEADERS)
    print(f"  Cancel status: {c.status_code} {'✅' if c.status_code in (200, 204) else '⚠️ ' + c.text[:200]}")
else:
    print()
    print("  ❌ ORDER FAILED — see response above for error details")

print()
print("=" * 55)
print("STEP 4 — Open orders after test")
print("=" * 55)
r = requests.get(f"{BASE_URL}/v2/orders?status=open", headers=HEADERS)
open_orders = r.json()
print(f"  {len(open_orders)} open order(s) remaining")
for o in open_orders:
    print(f"    {o.get('symbol')} {o.get('side')} {o.get('status')}")
