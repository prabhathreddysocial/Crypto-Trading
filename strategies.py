import pandas as pd


def signal_ema_crossover(df: pd.DataFrame) -> pd.Series:
    """Buy when EMA9 crosses above EMA21, sell when crosses below."""
    buy = (df["ema9"] > df["ema21"]) & (df["ema9"].shift(1) <= df["ema21"].shift(1))
    sell = (df["ema9"] < df["ema21"]) & (df["ema9"].shift(1) >= df["ema21"].shift(1))
    return buy.astype(int) - sell.astype(int)


def signal_rsi_mean_reversion(df: pd.DataFrame) -> pd.Series:
    """Buy on RSI oversold, sell on overbought."""
    buy = df["rsi"] < 32
    sell = df["rsi"] > 70
    return buy.astype(int) - sell.astype(int)


def signal_volume_breakout(df: pd.DataFrame) -> pd.Series:
    """Buy on volume spike + uptrend, sell on downtrend."""
    uptrend = df["ema9"] > df["ema21"]
    buy = uptrend & (df["vol_ratio"] >= 1.8) & (df["rsi"] < 75)
    sell = ~uptrend & (df["vol_ratio"] >= 1.5)
    return buy.astype(int) - sell.astype(int)


def signal_bollinger_bounce(df: pd.DataFrame) -> pd.Series:
    """Buy at lower BB, sell at upper BB."""
    buy = df["close"] <= df["bb_lower"]
    sell = df["close"] >= df["bb_upper"]
    return buy.astype(int) - sell.astype(int)


def signal_macd_momentum(df: pd.DataFrame) -> pd.Series:
    """Buy on MACD crossover above zero, sell below."""
    buy = (df["macd"] > 0) & (df["macd"].shift(1) <= 0)
    sell = (df["macd"] < 0) & (df["macd"].shift(1) >= 0)
    return buy.astype(int) - sell.astype(int)


STRATEGIES = {
    "EMA Crossover": signal_ema_crossover,
    "RSI Mean Reversion": signal_rsi_mean_reversion,
    "Volume Breakout": signal_volume_breakout,
    "Bollinger Bounce": signal_bollinger_bounce,
    "MACD Momentum": signal_macd_momentum,
}
