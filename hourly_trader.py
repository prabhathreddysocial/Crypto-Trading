import sqlite3
import traceback
from datetime import datetime, timezone, timedelta
from data_fetcher import get_bars
from indicators import add_indicators
from strategies import STRATEGIES
from trader import get_positions, manage_exits, execute_signal
from fear_greed import is_safe_to_buy
from market_data import is_market_safe_to_buy
from logger import init_db, log_trade_signal, log_completed_trade
from config import PAIRS

DB_PATH = "trading_log.db"

# Renamed strategy for DB compatibility (old "EMA Crossover" rows → default to "EMA Trend" now)
DEFAULT_STRATEGY = "EMA Trend"


def get_best_strategy(pair: str) -> str:
    """
    Pick the highest-Sharpe strategy from recent backtests.
    Requires at least 5 trades and Sharpe > 0.5 to be trusted.
    Falls back to DEFAULT_STRATEGY if no reliable data exists.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("""
            SELECT strategy FROM backtest_runs
            WHERE pair=? AND trades >= 5 AND sharpe > 0.5
            ORDER BY timestamp DESC, sharpe DESC LIMIT 1
        """, (pair,)).fetchone()
        conn.close()
        if row and row[0] in STRATEGIES:
            return row[0]
    except Exception:
        pass
    return DEFAULT_STRATEGY


def get_recent_signal(signals, lookback: int = 3) -> int:
    """
    Instead of only checking the last bar (iloc[-1]), look back N bars
    and return the most recent non-zero signal. This recovers signals
    that fired on a bar the cron missed or ran slightly late on.
    Returns 0 (hold) if no signal in the window.
    """
    for i in range(1, lookback + 1):
        sig = int(signals.iloc[-i])
        if sig != 0:
            return sig
    return 0


def was_recently_signaled(pair: str, signal: str, hours: int = 4) -> bool:
    """Prevent same signal firing within cooldown window per pair."""
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

    # Refresh positions after any exits
    positions = get_positions()
    open_symbols = set(positions.keys())

    for pair in PAIRS:
        alpaca_symbol = pair.replace("/", "")
        best = get_best_strategy(pair)
        print(f"\n{pair} → strategy: [{best}]")

        df = get_bars(pair)
        if df.empty or len(df) < 50:
            print("  Not enough data.")
            continue

        df = add_indicators(df)
        strategy_fn = STRATEGIES.get(best, STRATEGIES[DEFAULT_STRATEGY])

        try:
            signals = strategy_fn(df)

            # Use 3-bar lookback so we don't miss signals from the last few hours
            signal = get_recent_signal(signals, lookback=3)
            price = float(df["close"].iloc[-1])
            last_bar_ts = df.index[-1]
            has_position = alpaca_symbol in open_symbols

            print(f"  Last bar: {last_bar_ts} | Price: ${price:,.2f} | Signal: {signal:+d} | Has position: {has_position}")

            if signal == 1:
                if not safe_to_buy:
                    print(f"  BUY blocked — Fear & Greed gate (extreme greed)")
                elif has_position:
                    print(f"  BUY skipped — already have position")
                elif was_recently_signaled(pair, "BUY", hours=4):
                    print(f"  BUY skipped — fired within last 4h (cooldown)")
                elif not is_market_safe_to_buy(pair):
                    print(f"  BUY blocked — market data gate (funding/OI)")
                else:
                    print(f"  ✅ BUY signal @ ${price:,.2f}")
                    result = execute_signal(pair, signal, df, positions, strategy=best)
                    log_trade_signal(pair, best, "BUY", price)
                    print(f"  Order result: {result}")

            elif signal == -1:
                if not has_position:
                    print(f"  SELL skipped — no position to close")
                elif was_recently_signaled(pair, "SELL", hours=2):
                    print(f"  SELL skipped — fired within last 2h (cooldown)")
                else:
                    print(f"  ✅ SELL signal @ ${price:,.2f}")
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
