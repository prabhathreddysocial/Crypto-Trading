from data_fetcher import get_bars
from indicators import add_indicators
from strategies import STRATEGIES
from trader import get_positions, manage_exits, execute_signal
from fear_greed import is_safe_to_buy
from logger import init_db, log_trade_signal
from config import PAIRS
from datetime import datetime, timezone


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
    if not closed:
        print("  No exits triggered.")
    positions = get_positions()

    for pair in PAIRS:
        print(f"\n{pair}:")
        df = get_bars(pair)
        if df.empty or len(df) < 30:
            print("  Not enough data, skipping.")
            continue

        df = add_indicators(df)

        for name, strategy_fn in STRATEGIES.items():
            try:
                signals = strategy_fn(df)
                signal = int(signals.iloc[-1])

                if signal == 1 and not safe_to_buy:
                    print(f"  [{name}] BUY signal blocked by Fear & Greed gate")
                    log_trade_signal(pair, name, "BLOCKED", float(df["close"].iloc[-1]))
                    continue

                label = {1: "BUY", -1: "SELL", 0: "HOLD"}.get(signal, "HOLD")
                print(f"  [{name}] {label}")

                if signal != 0:
                    execute_signal(pair, signal, df, positions, strategy=name)
                    log_trade_signal(pair, name, label, float(df["close"].iloc[-1]))

            except Exception as e:
                print(f"  [{name}] Error: {e}")

    print("\nDone.")


if __name__ == "__main__":
    run()
