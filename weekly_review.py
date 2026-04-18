import sqlite3
import json
from agent import ask_brain
from logger import init_db
from datetime import datetime, timezone, timedelta

DB_PATH = "trading_log.db"


def init_memory_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            type TEXT,
            pair TEXT,
            content TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_week_insights():
    conn = sqlite3.connect(DB_PATH)
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    rows = conn.execute("""
        SELECT pair, timestamp, insight FROM agent_insights
        WHERE timestamp > ? ORDER BY timestamp ASC
    """, (week_ago,)).fetchall()
    conn.close()
    return rows


def get_week_trades():
    conn = sqlite3.connect(DB_PATH)
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    try:
        rows = conn.execute("""
            SELECT pair, strategy, entry_price, exit_price, pnl_pct, result, entry_time
            FROM completed_trades WHERE exit_time > ? ORDER BY exit_time ASC
        """, (week_ago,)).fetchall()
    except Exception:
        rows = []
    conn.close()
    return rows


def get_week_backtest_trend():
    conn = sqlite3.connect(DB_PATH)
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    rows = conn.execute("""
        SELECT pair, strategy, AVG(sharpe) as avg_sharpe,
               AVG(win_rate) as avg_win, AVG(total_return) as avg_return,
               COUNT(*) as days
        FROM backtest_runs WHERE timestamp > ? AND trades > 1
        GROUP BY pair, strategy ORDER BY pair, avg_sharpe DESC
    """, (week_ago,)).fetchall()
    conn.close()
    return rows


def get_last_monthly():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("""
        SELECT content FROM memory WHERE type='monthly'
        ORDER BY timestamp DESC LIMIT 1
    """).fetchone()
    conn.close()
    return row[0] if row else None


def save_memory(type_: str, pair: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO memory VALUES (NULL,?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), type_, pair, content)
    )
    conn.commit()
    conn.close()


def run():
    init_db()
    init_memory_table()
    print(f"\n[{datetime.now(timezone.utc).strftime('%Y-%m-%d')}] Weekly review running...")

    insights = get_week_insights()
    trades = get_week_trades()
    backtest_trend = get_week_backtest_trend()
    last_monthly = get_last_monthly()

    insights_text = "\n".join([f"[{r[1][:10]}] {r[0]}: {r[2][:200]}" for r in insights])
    trades_text = "\n".join([
        f"{r[6][:10]} | {r[0]} | {r[1]} | Buy ${r[2]:,.2f} → Sell ${r[3]:,.2f} | {r[4]:+.2f}% | {r[5]}"
        for r in trades
    ]) if trades else "No completed trades this week."
    bt_text = "\n".join([
        f"{r[0]} | {r[1]} | Avg Sharpe: {r[2]:.2f} | Avg Win%: {r[3]:.1f}% | Avg Return: {r[4]:.2f}% | {r[5]} days"
        for r in backtest_trend
    ]) if backtest_trend else "No backtest data."

    monthly_context = f"\nLONG-TERM MEMORY (last monthly review):\n{last_monthly}" if last_monthly else ""

    prompt = f"""You are a quantitative crypto trading AI building long-term knowledge.

This is your WEEKLY REVIEW. Your job is NOT to summarize — it is to LEARN and build knowledge.

WEEK BACKTEST PERFORMANCE (averaged across all daily runs):
{bt_text}

ACTUAL TRADES THIS WEEK:
{trades_text}

DAILY INSIGHTS THIS WEEK:
{insights_text}
{monthly_context}

Answer these questions to build your knowledge base:

1. WHAT WORKED THIS WEEK: Which strategies consistently had Sharpe > 1? On which pairs? What market conditions (trending/sideways/volatile) caused them to work? Cite exact numbers.

2. WHAT FAILED THIS WEEK: Which strategies had negative returns or Sharpe < 0? Why — was it bad signals, stop losses hit, wrong market condition?

3. PATTERNS IDENTIFIED: Did you see any repeating patterns? (e.g. "EMA Crossover fires well on BTC but not SOL", "RSI Mean Reversion only works when Fear & Greed < 30", "Volume Breakout fails on low-volume hours"). Only state patterns you can back with data from this week.

4. MARKET CONDITION THIS WEEK: Was the market trending or sideways? Volatile or calm? How do you know from the strategy performance?

5. RULE UPDATES: Based on this week, write 1-3 specific trading rules we should consider. Format: "IF [condition] THEN [action] BECAUSE [evidence from this week]"

6. WHAT TO WATCH NEXT WEEK: Based on patterns, what should we monitor?

Be specific with numbers. If data is insufficient (< 3 data points), say so."""

    summary = ask_brain(prompt)
    save_memory("weekly", "ALL", summary)
    print(f"\nWeekly review saved:\n{summary[:500]}...")
    print("\nWeekly review done.")


if __name__ == "__main__":
    run()
