import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px

DB_PATH = "trading_log.db"

st.set_page_config(page_title="Crypto Trading Brain", layout="wide")
st.title("Crypto Trading Research Dashboard")


def load_backtests():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM backtest_runs ORDER BY timestamp DESC", conn)
    conn.close()
    return df


def load_insights():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM agent_insights ORDER BY timestamp DESC", conn)
    conn.close()
    return df


bt = load_backtests()
insights = load_insights()

if bt.empty:
    st.warning("No data yet. Run main.py first.")
    st.stop()

latest_ts = bt["timestamp"].max()
latest = bt[bt["timestamp"] == latest_ts]

st.subheader(f"Latest Run: {latest_ts[:19]} UTC")

col1, col2, col3 = st.columns(3)
for i, pair in enumerate(["BTC/USD", "ETH/USD", "SOL/USD"]):
    data = latest[latest["pair"] == pair]
    col = [col1, col2, col3][i]
    with col:
        st.markdown(f"**{pair}**")
        if not data.empty:
            best = data.loc[data["total_return"].idxmax()]
            st.metric("Best Strategy", best["strategy"])
            st.metric("Total Return", f"{best['total_return']:.2f}%")
            st.metric("Sharpe", f"{best['sharpe']:.2f}")

st.divider()
st.subheader("Strategy Performance Over Time")

pairs = bt["pair"].unique().tolist()
selected_pair = st.selectbox("Select Pair", pairs)
pair_data = bt[bt["pair"] == selected_pair].copy()
pair_data["timestamp"] = pd.to_datetime(pair_data["timestamp"])

fig = px.line(
    pair_data, x="timestamp", y="total_return", color="strategy",
    title=f"{selected_pair} — Total Return % by Strategy",
    labels={"total_return": "Total Return (%)", "timestamp": "Date"}
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("All Strategy Metrics")
cols_to_show = ["timestamp", "pair", "strategy", "trades", "win_rate", "avg_pnl", "total_return", "sharpe"]
available = [c for c in cols_to_show if c in bt.columns]
st.dataframe(bt[available].sort_values("timestamp", ascending=False), use_container_width=True)

st.divider()
st.subheader("AI Brain Insights")
for _, row in insights.head(10).iterrows():
    with st.expander(f"{row['pair']} — {row['timestamp'][:19]}"):
        st.write(row["insight"])
