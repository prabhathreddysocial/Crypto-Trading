import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import sys
sys.path.append("/home/srisaiprabhathreddygudipalli/Crypto-Trading")
from data_fetcher import get_bars
from config import ALPACA_KEY, ALPACA_SECRET, BASE_URL

DB_PATH = "trading_log.db"
BASELINE = 1000
HEADERS = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET}

st.set_page_config(page_title="Crypto Trading Brain", layout="wide")
st.title("Crypto Trading Research Dashboard")


def load_backtests():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM backtest_runs ORDER BY timestamp DESC", conn)
    conn.close()
    return df


def load_signals():
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql("SELECT * FROM trade_signals ORDER BY timestamp ASC", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df


def load_completed_trades():
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql("SELECT * FROM completed_trades ORDER BY exit_time DESC", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df


def get_best_strategy_per_pair():
    conn = sqlite3.connect(DB_PATH)
    result = {}
    try:
        for pair in ["BTC/USD", "ETH/USD", "SOL/USD"]:
            row = conn.execute("""
                SELECT strategy FROM backtest_runs
                WHERE pair=? AND trades > 1
                ORDER BY timestamp DESC, sharpe DESC LIMIT 1
            """, (pair,)).fetchone()
            result[pair] = row[0] if row else "EMA Crossover"
    except Exception:
        pass
    conn.close()
    return result


def load_insights():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM agent_insights ORDER BY timestamp DESC", conn)
    conn.close()
    return df


def get_positions():
    try:
        r = requests.get(f"{BASE_URL}/v2/positions", headers=HEADERS)
        return r.json()
    except Exception:
        return []


def get_account():
    try:
        r = requests.get(f"{BASE_URL}/v2/account", headers=HEADERS)
        return r.json()
    except Exception:
        return {}


bt = load_backtests()
signals = load_signals()
insights = load_insights()
completed = load_completed_trades()
positions = get_positions()
account = get_account()
best_strategies = get_best_strategy_per_pair()

if bt.empty:
    st.warning("No data yet. Run hourly_trader.py first.")
    st.stop()

# --- Account Summary ---
st.subheader("Account Summary")
c1, c2, c3, c4 = st.columns(4)
equity = float(account.get("equity", 0))
cash = float(account.get("cash", 0))
deployed = equity - cash
total_pnl = completed["pnl_usd"].sum() if not completed.empty else 0
c1.metric("Total Equity", f"${equity:,.2f}")
c2.metric("Cash Available", f"${cash:,.2f}")
c3.metric("Deployed", f"${deployed:,.2f}")
c4.metric("Total Realised P&L", f"${total_pnl:+.2f}")

# Active strategies
st.markdown("**Active Strategy per Pair:**")
s1, s2, s3 = st.columns(3)
for col, pair in zip([s1, s2, s3], ["BTC/USD", "ETH/USD", "SOL/USD"]):
    col.info(f"**{pair}**\n\n{best_strategies.get(pair, 'EMA Crossover')}")

st.divider()

# --- Open Positions ---
st.subheader("Open Positions")
if not positions or isinstance(positions, dict):
    st.info("No open positions right now — bot is watching and waiting for signals.")
else:
    for pos in positions:
        symbol = pos["symbol"]
        qty = float(pos["qty"])
        entry = float(pos["avg_entry_price"])
        current = float(pos["current_price"])
        unreal_pl = float(pos["unrealized_pl"])
        unreal_plpc = float(pos["unrealized_plpc"]) * 100
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Symbol", symbol)
        col2.metric("Entry Price", f"${entry:,.2f}")
        col3.metric("Current Price", f"${current:,.2f}")
        color = "green" if unreal_pl >= 0 else "red"
        col4.metric("Unrealized P&L", f"${unreal_pl:,.2f}", f"{unreal_plpc:+.2f}%")
        col5.metric("Qty", f"{qty:.6f}")

st.divider()

# --- Price Charts ---
st.subheader("Price Charts — Last 30 Days")

for pair in ["BTC/USD", "ETH/USD", "SOL/USD"]:
    st.markdown(f"#### {pair}")
    with st.spinner(f"Loading {pair}..."):
        df = get_bars(pair, days=30)

    if df.empty:
        st.warning(f"No data for {pair}")
        continue

    df.index = pd.to_datetime(df.index, utc=True)

    fig = go.Figure()

    # Price line
    fig.add_trace(go.Scatter(
        x=df.index, y=df["close"],
        mode="lines", name="Price",
        line=dict(color="#4C9BE8", width=1.5)
    ))

    # Buy/sell signals + first purchase baseline
    if not signals.empty:
        pair_sigs = signals[signals["pair"] == pair].copy()
        pair_sigs["timestamp"] = pd.to_datetime(pair_sigs["timestamp"], utc=True)

        buys = pair_sigs[pair_sigs["signal"] == "BUY"]
        sells = pair_sigs[pair_sigs["signal"] == "SELL"]

        # Draw baseline at first ever buy
        if not buys.empty:
            first_buy_price = float(buys.iloc[0]["price"])
            first_buy_time = buys.iloc[0]["timestamp"]
            fig.add_shape(type="line",
                x0=first_buy_time, x1=df.index[-1],
                y0=first_buy_price, y1=first_buy_price,
                line=dict(color="gray", dash="dash", width=1)
            )
            fig.add_annotation(
                x=df.index[-1], y=first_buy_price,
                text=f"First buy ${first_buy_price:,.2f}",
                showarrow=False, xanchor="right",
                font=dict(color="gray", size=11)
            )

        if not buys.empty:
            fig.add_trace(go.Scatter(
                x=buys["timestamp"], y=buys["price"],
                mode="markers", name="BUY",
                marker=dict(symbol="triangle-up", size=14, color="green")
            ))
        if not sells.empty:
            fig.add_trace(go.Scatter(
                x=sells["timestamp"], y=sells["price"],
                mode="markers", name="SELL",
                marker=dict(symbol="triangle-down", size=14, color="red")
            ))

    # Mark current open position
    pair_symbol = pair.replace("/", "")
    for pos in (positions if isinstance(positions, list) else []):
        if pos["symbol"] == pair_symbol:
            fig.add_hline(
                y=float(pos["avg_entry_price"]),
                line_dash="dot", line_color="orange",
                annotation_text=f"Open @ ${float(pos['avg_entry_price']):,.2f}",
                annotation_position="top right"
            )

    fig.update_layout(
        height=320, margin=dict(l=0, r=0, t=30, b=0),
        xaxis_title="Date", yaxis_title="Price (USD)",
        legend=dict(orientation="h")
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- Strategy Backtest Performance ---
st.subheader("Strategy Backtest Performance")
pairs_list = bt["pair"].unique().tolist()
selected_pair = st.selectbox("Select Pair", pairs_list)
pair_data = bt[bt["pair"] == selected_pair].copy()
pair_data["timestamp"] = pd.to_datetime(pair_data["timestamp"])
fig2 = px.line(
    pair_data, x="timestamp", y="total_return", color="strategy",
    title=f"{selected_pair} — Total Return % by Strategy (Backtest)",
)
st.plotly_chart(fig2, use_container_width=True)

st.divider()

# --- Completed Trades Table ---
st.subheader("Transaction History")
if not completed.empty:
    display = completed.copy()
    display["entry_time"] = display["entry_time"].str[:16]
    display["exit_time"] = display["exit_time"].str[:16]
    display["pnl_usd"] = display["pnl_usd"].apply(lambda x: f"${x:+.2f}")
    display["pnl_pct"] = display["pnl_pct"].apply(lambda x: f"{x:+.2f}%")
    display["entry_price"] = display["entry_price"].apply(lambda x: f"${x:,.2f}")
    display["exit_price"] = display["exit_price"].apply(lambda x: f"${x:,.2f}")
    display = display.rename(columns={
        "pair": "Pair", "strategy": "Strategy",
        "entry_time": "Buy Time", "exit_time": "Sell Time",
        "entry_price": "Buy Price", "exit_price": "Sell Price",
        "pnl_usd": "P&L ($)", "pnl_pct": "P&L (%)", "result": "Result"
    })
    def color_result(val):
        color = "green" if val == "WIN" else "red"
        return f"color: {color}; font-weight: bold"
    st.dataframe(
        display[["Pair","Strategy","Buy Time","Buy Price","Sell Time","Sell Price","P&L ($)","P&L (%)","Result"]].style.applymap(color_result, subset=["Result"]),
        use_container_width=True, hide_index=True
    )
else:
    st.info("No completed trades yet — first trade will appear here once a buy and sell both happen.")

st.divider()

# --- AI Insights ---
st.subheader("AI Brain Insights")
for _, row in insights.head(10).iterrows():
    with st.expander(f"{row['pair']} — {row['timestamp'][:19]}"):
        st.write(row["insight"])
