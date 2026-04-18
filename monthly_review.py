import sqlite3
from agent import ask_brain
from logger import init_db
from datetime import datetime, timezone, timedelta

DB_PATH = "trading_log.db"


def get_month_weekly_summaries():
    conn = sqlite3.connect(DB_PATH)
    month_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    rows = conn.execute("""
        SELECT timestamp, content FROM memory
        WHERE type='weekly' AND timestamp > ?
        ORDER BY timestamp ASC
    """, (month_ago,)).fetchall()
    conn.close()
    return rows


def get_month_trades():
    conn = sqlite3.connect(DB_PATH)
    month_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    try:
        rows = conn.execute("""
            SELECT pair, strategy, pnl_pct, result, entry_time
            FROM completed_trades WHERE exit_time > ?
            ORDER BY exit_time ASC
        """, (month_ago,)).fetchall()
    except Exception:
        rows = []
    conn.close()
    return rows


def get_prev_monthly():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("""
        SELECT content FROM memory WHERE type='monthly'
        ORDER BY timestamp DESC LIMIT 1
    """).fetchone()
    conn.close()
    return row[0] if row else None


def save_memory(type_: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO memory VALUES (NULL,?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), type_, "ALL", content)
    )
    conn.commit()
    conn.close()


def run():
    init_db()
    print(f"\n[{datetime.now(timezone.utc).strftime('%Y-%m')}] Monthly review running...")

    weekly = get_month_weekly_summaries()
    trades = get_month_trades()
    prev_monthly = get_prev_monthly()

    weekly_text = "\n\n---\n".join([f"WEEK OF {r[0][:10]}:\n{r[1]}" for r in weekly])
    if not weekly_text:
        weekly_text = "No weekly summaries yet."

    trades_text = f"Total trades: {len(trades)}\n"
    wins = [t for t in trades if t[3] == "WIN"]
    losses = [t for t in trades if t[3] == "LOSS"]
    trades_text += f"Wins: {len(wins)}, Losses: {len(losses)}\n"
    if trades:
        avg_pnl = sum(t[2] for t in trades) / len(trades)
        trades_text += f"Average P&L per trade: {avg_pnl:+.2f}%\n"
        by_strategy = {}
        for t in trades:
            s = t[1]
            by_strategy.setdefault(s, []).append(t[2])
        for s, pnls in by_strategy.items():
            trades_text += f"  {s}: {len(pnls)} trades, avg {sum(pnls)/len(pnls):+.2f}%\n"

    prev_context = f"\nPREVIOUS MONTHLY KNOWLEDGE:\n{prev_monthly}" if prev_monthly else ""

    prompt = f"""You are a quantitative crypto trading AI building a long-term knowledge base.

This is your MONTHLY REVIEW. Your job is to consolidate what you've learned into confirmed knowledge.

WEEKLY SUMMARIES THIS MONTH:
{weekly_text}

TRADE PERFORMANCE THIS MONTH:
{trades_text}
{prev_context}

Build your monthly knowledge base by answering:

1. CONFIRMED RULES (rules that held true across multiple weeks — not just one):
   Format: "CONFIRMED: [rule] — Evidence: [which weeks, which numbers]"

2. UNCONFIRMED HYPOTHESES (seen once, need more data):
   Format: "HYPOTHESIS: [pattern] — Seen: [when] — Need: [what data to confirm]"

3. DISPROVED BELIEFS (something we thought worked but data showed otherwise):
   Format: "DISPROVED: [old belief] — Reality: [what actually happened]"

4. BEST STRATEGY THIS MONTH per pair — not just today, but consistently over the month.

5. MARKET REGIME: What type of market has crypto been in this month? (trending up/down, sideways, volatile). How does this affect which strategies we should use?

6. KNOWLEDGE GAPS: What questions do we still not have enough data to answer? What should we be tracking that we aren't?

7. NEXT MONTH PRIORITIES: Based on everything, what should we focus on testing next month?

Only state confirmed things with evidence. Be skeptical. Mark uncertainty clearly."""

    summary = ask_brain(prompt)
    save_memory("monthly", summary)
    print(f"\nMonthly review saved:\n{summary[:500]}...")
    print("\nMonthly review done.")


if __name__ == "__main__":
    run()
