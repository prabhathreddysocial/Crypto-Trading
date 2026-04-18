import sqlite3
from data_fetcher import get_bars
from backtest import run_all
from agent import analyze_backtest
from logger import init_db, log_backtest, log_insight
from config import PAIRS
from datetime import datetime, timezone

DB_PATH = "trading_log.db"


def get_history(pair: str) -> list:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT timestamp, insight FROM agent_insights
        WHERE pair=? ORDER BY timestamp DESC LIMIT 5
    """, (pair,)).fetchall()
    conn.close()
    return [{"timestamp": r[0], "insight": r[1]} for r in rows]


def get_long_term_memory() -> str:
    conn = sqlite3.connect(DB_PATH)
    try:
        weekly = conn.execute("""
            SELECT content FROM memory WHERE type='weekly'
            ORDER BY timestamp DESC LIMIT 1
        """).fetchone()
        monthly = conn.execute("""
            SELECT content FROM memory WHERE type='monthly'
            ORDER BY timestamp DESC LIMIT 1
        """).fetchone()
    except Exception:
        weekly, monthly = None, None
    conn.close()
    parts = []
    if monthly:
        parts.append(f"MONTHLY KNOWLEDGE:\n{monthly[0][:600]}")
    if weekly:
        parts.append(f"LAST WEEKLY REVIEW:\n{weekly[0][:400]}")
    return "\n\n".join(parts) if parts else ""


def get_trades(pair: str) -> list:
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("""
            SELECT entry_time, exit_time, entry_price, exit_price, pnl_pct, result
            FROM completed_trades WHERE pair=? ORDER BY exit_time DESC LIMIT 10
        """, (pair,)).fetchall()
    except Exception:
        rows = []
    conn.close()
    return [{"entry_time": r[0], "exit_time": r[1], "entry_price": r[2],
             "exit_price": r[3], "pnl_pct": r[4], "result": r[5]} for r in rows]


def run():
    init_db()
    print(f"\n[{datetime.now(timezone.utc).strftime('%Y-%m-%d')}] Daily AI summary...")

    for pair in PAIRS:
        print(f"\nAnalyzing {pair}...")
        df = get_bars(pair)
        if df.empty:
            continue

        results = run_all(df)
        log_backtest(pair, results)

        history = get_history(pair)
        trades = get_trades(pair)
        memory = get_long_term_memory()

        insight = analyze_backtest(pair, results, history=history, trades=trades, memory=memory)
        print(f"\n{insight}\n")
        log_insight(pair, insight)

    print("Daily summary done.")


if __name__ == "__main__":
    run()
