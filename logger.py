import sqlite3
import json
from datetime import datetime

DB_PATH = "trading_log.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
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
