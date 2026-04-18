import sqlite3
from data_fetcher import get_bars
from indicators import add_indicators
from strategies import STRATEGIES
from trader import get_positions, manage_exits, execute_signal
from fear_greed import is_safe_to_buy
from logger import init_db, log_trade_signal, log_completed_trade
from config import PAIRS
from datetime import datetime, timezone

DB_PATH = "trading_log.db"


def get_best_strategy(pair: str) -> str:
    """Pick best strategy for this pair based on latest backtest Sharpe ratio."""
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("""
            SELECT strategy FROM backtest_runs
            WHERE pair = ? AND trades > 1
            ORDER BY timestamp DESC, sharpe DESC
            LIMIT 1
        """, (pair,)).fetchone()
        conn.close()
        if row:
            return row[0]
    except Exception:
        pass
    return "EMA Crossover"  # default


def run():
    init_db()
    now = datetime.now(timezone.utc)
    print(f"\n[{now.strftime('%Y-%m-%d %H:%M')} UTC] Hourly trader running...")

    print("\nChecking Fear & Greed...")
    safe_to_buy = is_safe_to_buy(threshold=80)
    if not safe_to_buy:
        print("  Market greed too high — skipping all buys this hour.")

    print("\nManaging exits...")
    positions = get_positions()
    closed = manage_exits(positions)
    for symbol in closed:
        log_completed_trade(symbol)
    if not closed:
        print("  No exits triggered.")
    positions = get_positions()

    for pair in PAIRS:
        best = get_best_strategy(pair)
        print(f"\n{pair} — using [{best}]:")

        df = get_bars(pair)
        if df.empty or len(df) < 30:
            print("  Not enough data, skipping.")
            continue

        df = add_indicators(df)
        strategy_fn = STRATEGIES.get(best, STRATEGIES["EMA Crossover"])

        try:
            signals = strategy_fn(df)
            signal = int(signals.iloc[-1])
            price = float(df["close"].iloc[-1])

            if signal == 1 and not safe_to_buy:
                print(f"  BUY blocked by Fear & Greed gate")
                log_trade_signal(pair, best, "BLOCKED", price)
            else:
                label = {1: "BUY", -1: "SELL", 0: "HOLD"}.get(signal, "HOLD")
                print(f"  Signal: {label} @ ${price:,.2f}")
                if signal != 0:
                    action = execute_signal(pair, signal, df, positions, strategy=best)
                    log_trade_signal(pair, best, label, price)

        except Exception as e:
            print(f"  Error: {e}")

    print("\nDone.")


if __name__ == "__main__":
    run()
