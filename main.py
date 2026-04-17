import json
from data_fetcher import get_bars, get_account
from backtest import run_all
from agent import analyze_backtest
from logger import init_db, log_backtest, log_insight
from trader import get_positions, manage_exits, execute_signal
from indicators import add_indicators
from strategies import signal_ema_crossover
from config import PAIRS


def print_results(pair: str, results: dict):
    print(f"\n{'='*50}")
    print(f"  {pair} — Backtest Results")
    print(f"{'='*50}")
    print(f"{'Strategy':<25} {'Trades':>6} {'Win%':>6} {'Avg%':>7} {'Total%':>8} {'Sharpe':>7} {'Sortino':>8} {'MaxDD%':>7}")
    print("-" * 75)
    for name, m in results.items():
        if "error" in m:
            print(f"{name:<25}  ERROR: {m['error']}")
        else:
            print(f"{name:<25} {m['trades']:>6} {m['win_rate']:>5.1f}% {m['avg_pnl']:>6.2f}% {m['total_return']:>7.2f}% {m['sharpe']:>7.2f} {m['sortino']:>8.2f} {m['max_drawdown']:>6.2f}%")


def main():
    init_db()

    account = get_account()
    equity = float(account["equity"])
    print(f"\nAccount equity: ${equity:,.2f}")

    print("\n--- Managing exits ---")
    positions = get_positions()
    closed = manage_exits(positions)
    if not closed:
        print("  No exits triggered.")
    positions = get_positions()

    for pair in PAIRS:
        print(f"\nFetching data for {pair}...")
        df = get_bars(pair)

        if df.empty:
            print(f"  No data for {pair}, skipping.")
            continue

        print(f"  Got {len(df)} bars ({df.index[0].date()} to {df.index[-1].date()})")

        results = run_all(df)
        print_results(pair, results)
        log_backtest(pair, results)

        print(f"\n--- EMA Crossover Signal for {pair} ---")
        df_ind = add_indicators(df)
        signals = signal_ema_crossover(df_ind)
        latest_signal = int(signals.iloc[-1])
        signal_label = {1: "BUY", -1: "SELL", 0: "HOLD"}.get(latest_signal, "HOLD")
        print(f"  Signal: {signal_label}")
        action = execute_signal(pair, latest_signal, df_ind, positions)
        print(f"  Action: {action.upper()}")

        print(f"\nAsking AI brain to analyze {pair}...")
        insight = analyze_backtest(pair, results)
        print(f"\n--- AI Insight for {pair} ---\n{insight}")
        log_insight(pair, insight)

    print("\nDone. Results saved to trading_log.db")


if __name__ == "__main__":
    main()
