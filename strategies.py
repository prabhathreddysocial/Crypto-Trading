import pandas as pd


def signal_ema_trend(df: pd.DataFrame) -> pd.Series:
    """
    EMA Trend + Pullback (replaces edge-triggered EMA Crossover).
    BUY: ema9 > ema21 > ema50 (uptrend) AND price pulled back below ema9 AND RSI 35-65.
    SELL: ema9 drops below ema21 (trend broken).
    Fires on every bar where conditions hold — not just on the crossover bar.
    Expects ~5-20x more signals than a pure crossover strategy.
    """
    uptrend = (df["ema9"] > df["ema21"]) & (df["ema21"] > df["ema50"])
    pullback = df["close"] < df["ema9"]
    rsi_ok = df["rsi"].between(35, 68)
    buy = uptrend & pullback & rsi_ok
    sell = df["ema9"] < df["ema21"]
    return buy.astype(int) - sell.astype(int)


def signal_rsi_mean_reversion(df: pd.DataFrame) -> pd.Series:
    """
    RSI Mean Reversion with trend filter to avoid catching falling knives.
    BUY: RSI < 38 AND price above EMA50 (not in a structural downtrend).
    SELL: RSI > 65.
    RSI threshold raised from 32 → 38 to fire more often.
    """
    above_ma = df["close"] > df["ema50"]
    buy = (df["rsi"] < 38) & above_ma
    sell = df["rsi"] > 65
    return buy.astype(int) - sell.astype(int)


def signal_volume_breakout(df: pd.DataFrame) -> pd.Series:
    """
    Volume Breakout: volume spike in direction of trend.
    BUY: uptrend + vol_ratio >= 1.5 (lowered from 1.8) + RSI not overbought.
    SELL: downtrend + vol_ratio >= 1.3 (lowered from 1.5).
    """
    uptrend = df["ema9"] > df["ema21"]
    buy = uptrend & (df["vol_ratio"] >= 1.5) & (df["rsi"] < 72)
    sell = ~uptrend & (df["vol_ratio"] >= 1.3)
    return buy.astype(int) - sell.astype(int)


def signal_bollinger_bounce(df: pd.DataFrame) -> pd.Series:
    """
    Bollinger Bounce: buy near lower band, sell near upper band.
    Uses 102% / 98% proximity instead of exact touch for more signals.
    Adds RSI confirmation to avoid downtrend entries.
    """
    near_lower = df["close"] <= df["bb_lower"] * 1.002
    near_upper = df["close"] >= df["bb_upper"] * 0.998
    rsi_oversold = df["rsi"] < 45
    buy = near_lower & rsi_oversold
    sell = near_upper
    return buy.astype(int) - sell.astype(int)


def signal_macd_momentum(df: pd.DataFrame) -> pd.Series:
    """
    MACD Momentum: state-based (macd > 0) instead of edge-triggered zero-cross.
    BUY: macd > 0 AND positive and rising AND RSI not overbought.
    SELL: macd < 0.
    Fires on every bar in a momentum regime, not just on the crossover bar.
    """
    macd_positive = df["macd"] > 0
    macd_rising = df["macd"] > df["macd"].shift(1)
    rsi_ok = df["rsi"] < 70
    buy = macd_positive & macd_rising & rsi_ok
    sell = df["macd"] < 0
    return buy.astype(int) - sell.astype(int)


STRATEGIES = {
    "EMA Trend": signal_ema_trend,
    "RSI Mean Reversion": signal_rsi_mean_reversion,
    "Volume Breakout": signal_volume_breakout,
    "Bollinger Bounce": signal_bollinger_bounce,
    "MACD Momentum": signal_macd_momentum,
}
