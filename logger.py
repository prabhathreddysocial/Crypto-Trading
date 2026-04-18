import sqlite3
import json
from datetime import datetime

DB_PATH = "trading_log.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS completed_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair TEXT,
            strategy TEXT,
            entry_time TEXT,
            exit_time TEXT,
            entry_price REAL,
            exit_price REAL,
            pnl_usd REAL,
            pnl_pct REAL,
            result TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trade_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            pair TEXT,
            strategy TEXT,
            signal TEXT,
            price REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS backtest_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            pair TEXT,
            strategy TEXT,
            trades INTEGER,
            win_rate REAL,
            avg_pnl REAL,
            total_return REAL,
            sharpe REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_insights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            pair TEXT,
            insight TEXT
        )
    """)
    conn.commit()
    conn.close()


def log_completed_trade(symbol: str):
    """Match last BUY with last SELL for a pair and log the round trip."""
    pair = symbol if "/" in symbol else symbol.replace("USD", "/USD")
    conn = sqlite3.connect(DB_PATH)
    buy = conn.execute("""
        SELECT timestamp, price, strategy FROM trade_signals
        WHERE pair=? AND signal='BUY' ORDER BY timestamp DESC LIMIT 1
    """, (pair,)).fetchone()
    sell = conn.execute("""
        SELECT timestamp, price FROM trade_signals
        WHERE pair=? AND signal='SELL' ORDER BY timestamp DESC LIMIT 1
    """, (pair,)).fetchone()
    if buy and sell:
        entry_price = buy[1]
        exit_price = sell[1]
        strategy = buy[2]
        pnl_pct = (exit_price - entry_price) / entry_price * 100
        pnl_usd = 1000 * pnl_pct / 100
        result = "WIN" if pnl_pct > 0 else "LOSS"
        conn.execute(
            "INSERT INTO completed_trades VALUES (NULL,?,?,?,?,?,?,?,?,?)",
            (pair, strategy, buy[0], sell[0], entry_price, exit_price,
             round(pnl_usd, 2), round(pnl_pct, 2), result)
        )
        conn.commit()
    conn.close()


def log_trade_signal(pair: str, strategy: str, signal: str, price: float):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO trade_signals VALUES (NULL,?,?,?,?,?)",
        (datetime.utcnow().isoformat(), pair, strategy, signal, price)
    )
    conn.commit()
    conn.close()


def log_backtest(pair: str, results: dict):
    conn = sqlite3.connect(DB_PATH)
    ts = datetime.utcnow().isoformat()
    for strategy, metrics in results.items():
        if "error" not in metrics:
            conn.execute(
                "INSERT INTO backtest_runs VALUES (NULL,?,?,?,?,?,?,?,?)",
                (ts, pair, strategy, metrics["trades"], metrics["win_rate"],
                 metrics["avg_pnl"], metrics["total_return"], metrics["sharpe"])
            )
    conn.commit()
    conn.close()


def log_insight(pair: str, insight: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO agent_insights VALUES (NULL,?,?,?)",
        (datetime.utcnow().isoformat(), pair, insight)
    )
    conn.commit()
    conn.close()
