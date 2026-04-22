import sqlite3
import traceback
from datetime import datetime, timezone, timedelta
from data_fetcher import get_bars
from indicators import add_indicators
from strategies import STRATEGIES
from trader import get_positions, manage_exits, execute_signal
from fear_greed import is_safe_to_buy
from logger import init_db, log_trade_signal, log_completed_trade
from config import PAIRS

DB_PATH = "trading_log.db"


def get_best_strategy(pair: str) -> str:
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("""
            SELECT strategy FROM backtest_runs
            WHERE pair=? AND trades > 2 AND sharpe > 0
            ORDER BY timestamp DESC, sharpe DESC LIMIT 1
        """, (pair,)).fetchone()
        conn.close()
        if row:
            return row[0]
    except Exception:
        pass
    return "EMA Crossover"


def was_recently_signaled(pair: str, signal: str, hours: int = 24) -> bool:
    """Prevent same signal firing more than once per 24 hours per pair."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        row = conn.execute("""
            SELECT id FROM trade_signals
            WHERE pair=? AND signal=? AND timestamp > ?
            ORDER BY timestamp DESC LIMIT 1
        """, (pair, signal, cutoff)).fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


def run():
    init_db()
    now = datetime.now(timezone.utc)
    print(f"\n[{now.strftime('%Y-%m-%d %H:%M')} UTC] Hourly trader running...")

    print("\nChecking Fear & Greed...")
    safe_to_buy = is_safe_to_buy(threshold=80)
    if not safe_to_buy:
        print("  Extreme greed — skipping all buys.")

    print("\nManaging exits...")
    positions = get_positions()
    closed = manage_exits(positions)
    for symbol in closed:
        log_completed_trade(symbol)
    if not closed:
        print("  No exits triggered.")
    positions = get_positions()
    open_symbols = set(positions.keys())  # positions is a dict keyed by symbol

    for pair in PAIRS:
        alpaca_symbol = pair.replace("/", "")
        best = get_best_strategy(pair)
        print(f"\n{pair} → strategy: [{best}]")

        df = get_bars(pair)
        if df.empty or len(df) < 30:
            print("  Not enough data.")
            continue

        df = add_indicators(df)
        strategy_fn = STRATEGIES.get(best, STRATEGIES["EMA Crossover"])

        try:
            signals = strategy_fn(df)
            signal = int(signals.iloc[-1])
            price = float(df["close"].iloc[-1])
            has_position = alpaca_symbol in open_symbols

            if signal == 1:
                if not safe_to_buy:
                    print(f"  BUY blocked — Fear & Greed gate")
                elif has_position:
                    print(f"  BUY skipped — already have position")
                elif was_recently_signaled(pair, "BUY", hours=24):
                    print(f"  BUY skipped — already fired in last 24h (cooldown)")
                else:
                    print(f"  BUY signal @ ${price:,.2f}")
                    result = execute_signal(pair, signal, df, positions, strategy=best)
                    log_trade_signal(pair, best, "BUY", price)
                    print(f"  Order result: {result}")

            elif signal == -1:
                if not has_position:
                    print(f"  SELL skipped — no position to close")
                elif was_recently_signaled(pair, "SELL", hours=6):
                    print(f"  SELL skipped — already sold in last 6h (cooldown)")
                else:
                    print(f"  SELL signal @ ${price:,.2f}")
                    result = execute_signal(pair, signal, df, positions, strategy=best)
                    log_trade_signal(pair, best, "SELL", price)
                    print(f"  Order result: {result}")

            else:
                print(f"  HOLD @ ${price:,.2f}")

        except Exception as e:
            print(f"  ERROR: {e}")
            traceback.print_exc()

    print("\nDone.")


if __name__ == "__main__":
    run()
