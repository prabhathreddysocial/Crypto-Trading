import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
from config import ALPACA_KEY, ALPACA_SECRET, DATA_URL, LOOKBACK_DAYS


def get_bars(symbol: str, timeframe: str = "1H", days: int = LOOKBACK_DAYS) -> pd.DataFrame:
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    headers = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET}
    params = {"symbols": symbol, "timeframe": timeframe, "start": start, "limit": 10000}

    bars = []
    symbol_key = symbol.replace("/", "")
    r = requests.get(f"{DATA_URL}/bars", headers=headers, params=params)
    r.raise_for_status()
    data = r.json()
    bars.extend(data.get("bars", {}).get(symbol_key, []))

    if not bars:
        return pd.DataFrame()

    df = pd.DataFrame(bars)
    df["t"] = pd.to_datetime(df["t"])
    df.set_index("t", inplace=True)
    df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}, inplace=True)
    return df[["open", "high", "low", "close", "volume"]].sort_index()


def get_account(session=None) -> dict:
    import requests as req
    from config import BASE_URL
    headers = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET}
    r = req.get(f"{BASE_URL}/v2/account", headers=headers)
    r.raise_for_status()
    return r.json()
