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
    std = statistics.stdev(pnls) if len(pnls) > 1 else 0
    sharpe = (avg_pnl / std) * (252 ** 0.5) if std else 0

    downside = [p for p in pnls if p < 0]
    down_std = statistics.stdev(downside) if len(downside) > 1 else 0
    sortino = (avg_pnl / down_std) * (252 ** 0.5) if down_std else 0

    cumulative = 0
    peak = 0
    max_dd = 0
    for p in pnls:
        cumulative += p
        if cumulative > peak:
            peak = cumulative
        dd = (peak - cumulative) / (1 + peak) if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    return {
        "trades": len(trades),
        "win_rate": round(win_rate * 100, 1),
        "avg_pnl": round(avg_pnl * 100, 2),
        "total_return": round(total_return * 100, 2),
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "max_drawdown": round(max_dd * 100, 2),
    }


def run_all(df: pd.DataFrame) -> dict:
    results = {}
    for name, fn in STRATEGIES.items():
        try:
            results[name] = run_backtest(df, fn)
        except Exception as e:
            results[name] = {"error": str(e)}
    return results
