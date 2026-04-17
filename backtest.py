import pandas as pd
from indicators import add_indicators
from strategies import STRATEGIES


def run_backtest(df: pd.DataFrame, strategy_fn, take_profit=0.06, stop_loss=0.03) -> dict:
    df = add_indicators(df)
    signals = strategy_fn(df)

    position = None
    entry_price = 0.0
    trades = []

    for i, (ts, row) in enumerate(df.iterrows()):
        sig = signals.iloc[i]
        price = row["close"]

        if position:
            pnl = (price - entry_price) / entry_price
            if pnl >= take_profit or pnl <= -stop_loss:
                trades.append({"entry": entry_price, "exit": price, "pnl": pnl, "ts": ts})
                position = None

        if not position and sig == 1:
            position = "long"
            entry_price = price

    if not trades:
        return {"trades": 0, "win_rate": 0, "avg_pnl": 0, "total_return": 0, "sharpe": 0}

    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    win_rate = len(wins) / len(pnls)
    avg_pnl = sum(pnls) / len(pnls)
    total_return = sum(pnls)

    import statistics
    sharpe = (avg_pnl / statistics.stdev(pnls)) * (252 ** 0.5) if len(pnls) > 1 else 0

    return {
        "trades": len(trades),
        "win_rate": round(win_rate * 100, 1),
        "avg_pnl": round(avg_pnl * 100, 2),
        "total_return": round(total_return * 100, 2),
        "sharpe": round(sharpe, 2),
    }


def run_all(df: pd.DataFrame) -> dict:
    results = {}
    for name, fn in STRATEGIES.items():
        try:
            results[name] = run_backtest(df, fn)
        except Exception as e:
            results[name] = {"error": str(e)}
    return results
