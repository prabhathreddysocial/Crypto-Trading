from data_fetcher import get_bars
from backtest import run_all
from agent import analyze_backtest
from logger import init_db, log_backtest, log_insight
from config import PAIRS
from datetime import datetime, timezone


def run():
    init_db()
    print(f"\n[{datetime.now(timezone.utc).strftime('%Y-%m-%d')}] Daily AI summary running...")

    for pair in PAIRS:
        print(f"\nAnalyzing {pair}...")
        df = get_bars(pair)
        if df.empty:
            continue

        results = run_all(df)
        log_backtest(pair, results)

        insight = analyze_backtest(pair, results)
        print(f"AI Insight: {insight[:300]}...")
        log_insight(pair, insight)

    print("\nDaily summary done.")


if __name__ == "__main__":
    run()
