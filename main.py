import json
from data_fetcher import get_bars, get_account
from backtest import run_all
from agent import analyze_backtest
from logger import init_db, log_backtest, log_insight
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
    print(f"\nAccount equity: ${float(account['equity']):,.2f}")

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

        print(f"\nAsking AI brain to analyze {pair}...")
        insight = analyze_backtest(pair, results)
        print(f"\n--- AI Insight for {pair} ---\n{insight}")
        log_insight(pair, insight)

    print("\nDone. Results saved to trading_log.db")


if __name__ == "__main__":
    main()
