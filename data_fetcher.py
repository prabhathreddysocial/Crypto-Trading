import pandas as pd
from datetime import datetime, timezone, timedelta
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from config import ALPACA_KEY, ALPACA_SECRET, LOOKBACK_DAYS


def get_bars(symbol: str, days: int = LOOKBACK_DAYS) -> pd.DataFrame:
    client = CryptoHistoricalDataClient(ALPACA_KEY, ALPACA_SECRET)
    start = datetime.now(timezone.utc) - timedelta(days=days)
    request = CryptoBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Day, start=start)
    bars = client.get_crypto_bars(request)
    df = bars.df

    if df.empty:
        return pd.DataFrame()

    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(symbol, level="symbol")

    df = df.rename(columns={"open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"})
    return df[["open", "high", "low", "close", "volume"]].sort_index()


def get_account(session=None) -> dict:
    import requests as req
    from config import BASE_URL
    headers = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET}
    r = req.get(f"{BASE_URL}/v2/account", headers=headers)
    r.raise_for_status()
    return r.json()
