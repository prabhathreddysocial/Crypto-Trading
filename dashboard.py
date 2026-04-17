import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sys
sys.path.append("/home/srisaiprabhathreddygudipalli/Crypto-Trading")
from data_fetcher import get_bars

DB_PATH = "trading_log.db"
BASELINE = 1000

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


def load_insights():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM agent_insights ORDER BY timestamp DESC", conn)
    conn.close()
    return df


bt = load_backtests()
signals = load_signals()
insights = load_insights()

if bt.empty:
    st.warning("No data yet. Run hourly_trader.py first.")
    st.stop()

st.subheader(f"Latest Run: {bt['timestamp'].max()[:19]} UTC")

col1, col2, col3 = st.columns(3)
for i, pair in enumerate(["BTC/USD", "ETH/USD", "SOL/USD"]):
    data = bt[bt["pair"] == pair].sort_values("timestamp")
    col = [col1, col2, col3][i]
    with col:
        st.markdown(f"**{pair}**")
        if not data.empty:
            best = data.loc[data["total_return"].idxmax()]
            st.metric("Best Strategy", best["strategy"])
            st.metric("Total Return", f"{best['total_return']:.2f}%")
            st.metric("Sharpe", f"{best['sharpe']:.2f}")

st.divider()
st.subheader("Price Charts with Buy/Sell Signals")

for pair in ["BTC/USD", "ETH/USD", "SOL/USD"]:
    st.markdown(f"#### {pair}")
    with st.spinner(f"Loading {pair} data..."):
        df = get_bars(pair, days=30)

    if df.empty:
        st.warning(f"No price data for {pair}")
        continue

    df.index = pd.to_datetime(df.index, utc=True)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df["close"],
        mode="lines", name="Price",
        line=dict(color="#4C9BE8", width=1.5)
    ))

    if not signals.empty:
        pair_sigs = signals[signals["pair"] == pair].copy()
        pair_sigs["timestamp"] = pd.to_datetime(pair_sigs["timestamp"], utc=True)

        buys = pair_sigs[pair_sigs["signal"] == "BUY"]
        sells = pair_sigs[pair_sigs["signal"] == "SELL"]

        if not buys.empty:
            fig.add_trace(go.Scatter(
                x=buys["timestamp"], y=buys["price"],
                mode="markers", name="BUY",
                marker=dict(symbol="triangle-up", size=12, color="green")
            ))
        if not sells.empty:
            fig.add_trace(go.Scatter(
                x=sells["timestamp"], y=sells["price"],
                mode="markers", name="SELL",
                marker=dict(symbol="triangle-down", size=12, color="red")
            ))

    fig.update_layout(
        height=300, margin=dict(l=0, r=0, t=30, b=0),
        xaxis_title="Date", yaxis_title="Price (USD)",
        legend=dict(orientation="h")
    )
    st.plotly_chart(fig, use_container_width=True)

    if not signals.empty and not pair_sigs.empty:
        st.markdown(f"**${BASELINE:,} baseline — simulated P&L per strategy**")
        strategy_cols = st.columns(len(pair_sigs["strategy"].unique()))
        for idx, strategy in enumerate(pair_sigs["strategy"].unique()):
            strat_sigs = pair_sigs[pair_sigs["strategy"] == strategy].sort_values("timestamp")
            balance = BASELINE
            position_price = None
            for _, row in strat_sigs.iterrows():
                if row["signal"] == "BUY" and position_price is None:
                    position_price = row["price"]
                elif row["signal"] == "SELL" and position_price:
                    pnl_pct = (row["price"] - position_price) / position_price
                    balance *= (1 + pnl_pct)
                    position_price = None
            pnl = balance - BASELINE
            with strategy_cols[idx]:
                st.metric(strategy, f"${balance:,.2f}", f"{pnl:+.2f}")

st.divider()
st.subheader("Strategy Performance Over Time")
pairs = bt["pair"].unique().tolist()
selected_pair = st.selectbox("Select Pair", pairs)
pair_data = bt[bt["pair"] == selected_pair].copy()
pair_data["timestamp"] = pd.to_datetime(pair_data["timestamp"])
fig2 = px.line(
    pair_data, x="timestamp", y="total_return", color="strategy",
    title=f"{selected_pair} — Backtest Total Return % by Strategy",
)
st.plotly_chart(fig2, use_container_width=True)

st.divider()
st.subheader("All Trade Signals")
if not signals.empty:
    st.dataframe(signals.sort_values("timestamp", ascending=False), use_container_width=True)
else:
    st.info("No trade signals yet — waiting for first hourly run to fire a signal.")

st.divider()
st.subheader("AI Brain Insights")
for _, row in insights.head(10).iterrows():
    with st.expander(f"{row['pair']} — {row['timestamp'][:19]}"):
        st.write(row["insight"])
