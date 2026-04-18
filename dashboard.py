import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime, timezone, timedelta
import sys
sys.path.append("/home/srisaiprabhathreddygudipalli/Crypto-Trading")
from data_fetcher import get_bars
from config import ALPACA_KEY, ALPACA_SECRET, BASE_URL

DB_PATH = "trading_log.db"
POSITION_SIZE = 1000
HEADERS = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET}
PAIR_COLORS = {"BTC/USD": "#F7931A", "ETH/USD": "#627EEA", "SOL/USD": "#9945FF"}

st.set_page_config(page_title="Crypto Trading Brain", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .main { background-color: #f8f9fb; }
    .block-container { padding: 1.5rem 2rem; }
    .metric-card {
        background: white;
        border-radius: 14px;
        padding: 18px 22px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.07);
        margin-bottom: 12px;
    }
    .metric-label {
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #888;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 26px;
        font-weight: 700;
        color: #1a1a2e;
        margin: 0;
    }
    .metric-sub {
        font-size: 13px;
        margin-top: 2px;
    }
    .green { color: #16a34a; }
    .red { color: #dc2626; }
    .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 6px; }
    .section-title {
        font-size: 16px;
        font-weight: 700;
        color: #1a1a2e;
        margin: 24px 0 12px 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .pair-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        margin-right: 6px;
    }
    .stDataFrame { border-radius: 12px; overflow: hidden; }
    div[data-testid="stHorizontalBlock"] { gap: 12px; }
</style>
""", unsafe_allow_html=True)


# --- Data loaders ---
def load_completed_trades():
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql("SELECT * FROM completed_trades ORDER BY exit_time DESC", conn)
    except Exception:
        df = pd.DataFrame()
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


def load_backtests():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM backtest_runs ORDER BY timestamp DESC", conn)
    conn.close()
    return df


def get_positions():
    try:
        r = requests.get(f"{BASE_URL}/v2/positions", headers=HEADERS, timeout=5)
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception:
        return []


def get_account():
    try:
        r = requests.get(f"{BASE_URL}/v2/account", headers=HEADERS, timeout=5)
        return r.json()
    except Exception:
        return {}


def get_best_strategy(pair):
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("""
            SELECT strategy FROM backtest_runs
            WHERE pair=? AND trades > 1
            ORDER BY timestamp DESC, sharpe DESC LIMIT 1
        """, (pair,)).fetchone()
        conn.close()
        return row[0] if row else "EMA Crossover"
    except Exception:
        conn.close()
        return "EMA Crossover"


# --- Load all data ---
account = get_account()
positions = get_positions()
completed = load_completed_trades()
signals = load_signals()
bt = load_backtests()

equity = float(account.get("equity", 100000))
cash = float(account.get("cash", 100000))
start_equity = 100000
all_time_pnl = equity - start_equity
all_time_pct = (all_time_pnl / start_equity) * 100
unrealized = sum(float(p.get("unrealized_pl", 0)) for p in positions)
deployed = equity - cash
today = datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M UTC")
wins = len(completed[completed["result"] == "WIN"]) if not completed.empty else 0
total_trades = len(completed)
win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
biggest = max(positions, key=lambda x: abs(float(x.get("market_value", 0))), default=None)
biggest_label = f"{biggest['symbol']} ({abs(float(biggest['market_value']))/equity*100:.1f}%)" if biggest else "—"

# --- Header ---
st.markdown(f"""
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
  <div>
    <span style="font-size:22px; font-weight:800; color:#1a1a2e;">📈 Crypto Trading Brain</span>
  </div>
  <div style="font-size:13px; color:#888;">{today} &nbsp;|&nbsp; Paper Trading</div>
</div>
""", unsafe_allow_html=True)

# --- Top metrics row ---
c1, c2, c3, c4, c5 = st.columns(5)
pnl_color = "green" if all_time_pnl >= 0 else "red"
unreal_color = "green" if unrealized >= 0 else "red"

with c1:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-label"><span class="dot" style="background:#6366f1;"></span>Portfolio Value</div>
        <div class="metric-value">${equity:,.2f}</div>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-label"><span class="dot" style="background:#f59e0b;"></span>All-time P&L</div>
        <div class="metric-value">${all_time_pnl:+,.2f}</div>
        <div class="metric-sub {'green' if all_time_pnl>=0 else 'red'}">{all_time_pct:+.2f}%</div>
    </div>""", unsafe_allow_html=True)
with c3:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-label"><span class="dot" style="background:#10b981;"></span>Unrealized P&L</div>
        <div class="metric-value {unreal_color}">${unrealized:+,.2f}</div>
    </div>""", unsafe_allow_html=True)
with c4:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-label"><span class="dot" style="background:#3b82f6;"></span>Cash Available</div>
        <div class="metric-value">${cash:,.2f}</div>
    </div>""", unsafe_allow_html=True)
with c5:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-label"><span class="dot" style="background:#8b5cf6;"></span>Deployed</div>
        <div class="metric-value">${deployed:,.2f}</div>
    </div>""", unsafe_allow_html=True)

c6, c7, c8, c9 = st.columns(4)
with c6:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-label"><span class="dot" style="background:#ec4899;"></span>Open Positions</div>
        <div class="metric-value">{len(positions)}</div>
    </div>""", unsafe_allow_html=True)
with c7:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-label"><span class="dot" style="background:#10b981;"></span>Win Rate</div>
        <div class="metric-value">{win_rate:.0f}%</div>
        <div class="metric-sub" style="color:#888;">{wins}W / {total_trades - wins}L</div>
    </div>""", unsafe_allow_html=True)
with c8:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-label"><span class="dot" style="background:#f97316;"></span>Total Trades</div>
        <div class="metric-value">{total_trades}</div>
    </div>""", unsafe_allow_html=True)
with c9:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-label"><span class="dot" style="background:#64748b;"></span>Biggest Holding</div>
        <div class="metric-value" style="font-size:18px;">{biggest_label}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("---")

# --- Price Charts (past 7 days) ---
st.markdown('<div class="section-title">📊 Price Charts — Past 7 Days</div>', unsafe_allow_html=True)

chart_cols = st.columns(3)
for idx, pair in enumerate(["BTC/USD", "ETH/USD", "SOL/USD"]):
    with chart_cols[idx]:
        color = PAIR_COLORS[pair]
        best_strat = get_best_strategy(pair)
        df = get_bars(pair, days=7)

        if df.empty:
            st.warning(f"No data for {pair}")
            continue

        df.index = pd.to_datetime(df.index, utc=True)
        current_price = float(df["close"].iloc[-1])
        start_price = float(df["close"].iloc[0])
        change_pct = (current_price - start_price) / start_price * 100
        change_color = "#16a34a" if change_pct >= 0 else "#dc2626"

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df.index, y=df["close"],
            mode="lines", name="Price",
            line=dict(color=color, width=2),
            fill="tozeroy",
            fillcolor=f"rgba{tuple(list(bytes.fromhex(color[1:])) + [20])}"
        ))

        # Buy/sell markers
        if not signals.empty:
            ps = signals[signals["pair"] == pair].copy()
            ps["timestamp"] = pd.to_datetime(ps["timestamp"], utc=True)
            ps = ps[ps["timestamp"] >= df.index[0]]
            buys = ps[ps["signal"] == "BUY"]
            sells = ps[ps["signal"] == "SELL"]
            if not buys.empty:
                fig.add_trace(go.Scatter(
                    x=buys["timestamp"], y=buys["price"],
                    mode="markers", name="BUY", showlegend=False,
                    marker=dict(symbol="triangle-up", size=12, color="#16a34a")
                ))
            if not sells.empty:
                fig.add_trace(go.Scatter(
                    x=sells["timestamp"], y=sells["price"],
                    mode="markers", name="SELL", showlegend=False,
                    marker=dict(symbol="triangle-down", size=12, color="#dc2626")
                ))

        # Open position line
        pair_sym = pair.replace("/", "")
        for pos in positions:
            if pos["symbol"] == pair_sym:
                ep = float(pos["avg_entry_price"])
                fig.add_hline(y=ep, line_dash="dot", line_color="orange",
                    annotation_text=f"Open @ ${ep:,.0f}",
                    annotation_position="top left",
                    annotation_font_size=10)

        fig.update_layout(
            height=220, margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor="white", paper_bgcolor="white",
            xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=9)),
            yaxis=dict(showgrid=True, gridcolor="#f0f0f0", zeroline=False, tickfont=dict(size=9)),
            showlegend=False
        )

        st.markdown(f"""
        <div style="background:white; border-radius:14px; padding:14px 16px; box-shadow:0 1px 4px rgba(0,0,0,0.07);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                <span style="font-weight:700; font-size:15px; color:#1a1a2e;">{pair}</span>
                <span style="font-size:11px; color:#888;">Strategy: {best_strat}</span>
            </div>
            <div style="font-size:22px; font-weight:800; color:#1a1a2e;">${current_price:,.2f}</div>
            <div style="font-size:13px; color:{change_color}; font-weight:600;">{change_pct:+.2f}% this week</div>
        </div>
        """, unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

st.markdown("---")

# --- Open Positions ---
st.markdown('<div class="section-title">🔓 Open Positions</div>', unsafe_allow_html=True)
if positions:
    for pos in positions:
        sym = pos["symbol"]
        pair = sym[:3] + "/" + sym[3:]
        qty = float(pos["qty"])
        entry = float(pos["avg_entry_price"])
        current = float(pos["current_price"])
        pl = float(pos["unrealized_pl"])
        plpct = float(pos["unrealized_plpc"]) * 100
        color = "#16a34a" if pl >= 0 else "#dc2626"
        arrow = "▲" if pl >= 0 else "▼"
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.markdown(f"**{sym}**")
        c2.markdown(f"Entry: **${entry:,.2f}**")
        c3.markdown(f"Now: **${current:,.2f}**")
        c4.markdown(f"<span style='color:{color}; font-weight:700;'>{arrow} ${pl:+,.2f}</span>", unsafe_allow_html=True)
        c5.markdown(f"<span style='color:{color}; font-weight:700;'>{plpct:+.2f}%</span>", unsafe_allow_html=True)
else:
    st.info("No open positions — bot is watching for signals.")

st.markdown("---")

# --- Transaction History ---
st.markdown('<div class="section-title">📋 Transaction History</div>', unsafe_allow_html=True)
if not completed.empty:
    display = completed.copy()
    display["entry_time"] = display["entry_time"].str[:16]
    display["exit_time"] = display["exit_time"].str[:16]

    def fmt_row(row):
        pl_color = "#16a34a" if row["pnl_usd"] >= 0 else "#dc2626"
        res_color = "#16a34a" if row["result"] == "WIN" else "#dc2626"
        pair_color = PAIR_COLORS.get(row["pair"], "#888")
        return f"""
        <tr style="border-bottom:1px solid #f0f0f0;">
            <td style="padding:10px 8px;"><span style="background:{pair_color}22; color:{pair_color}; padding:2px 8px; border-radius:10px; font-weight:600; font-size:12px;">{row['pair']}</span></td>
            <td style="padding:10px 8px; font-size:12px; color:#555;">{row['strategy']}</td>
            <td style="padding:10px 8px; font-size:12px;">{row['entry_time']}</td>
            <td style="padding:10px 8px; font-weight:600;">${row['entry_price']:,.2f}</td>
            <td style="padding:10px 8px; font-size:12px;">{row['exit_time']}</td>
            <td style="padding:10px 8px; font-weight:600;">${row['exit_price']:,.2f}</td>
            <td style="padding:10px 8px; font-weight:700; color:{pl_color};">${row['pnl_usd']:+.2f}</td>
            <td style="padding:10px 8px; font-weight:700; color:{pl_color};">{row['pnl_pct']:+.2f}%</td>
            <td style="padding:10px 8px;"><span style="color:{res_color}; font-weight:700;">{row['result']}</span></td>
        </tr>"""

    rows_html = "".join(display.apply(fmt_row, axis=1))
    st.markdown(f"""
    <div style="background:white; border-radius:14px; padding:16px; box-shadow:0 1px 4px rgba(0,0,0,0.07); overflow-x:auto;">
        <table style="width:100%; border-collapse:collapse;">
            <thead>
                <tr style="border-bottom:2px solid #f0f0f0;">
                    <th style="text-align:left; padding:8px; font-size:11px; color:#888; text-transform:uppercase; letter-spacing:0.05em;">Pair</th>
                    <th style="text-align:left; padding:8px; font-size:11px; color:#888; text-transform:uppercase; letter-spacing:0.05em;">Strategy</th>
                    <th style="text-align:left; padding:8px; font-size:11px; color:#888; text-transform:uppercase; letter-spacing:0.05em;">Buy Time</th>
                    <th style="text-align:left; padding:8px; font-size:11px; color:#888; text-transform:uppercase; letter-spacing:0.05em;">Buy Price</th>
                    <th style="text-align:left; padding:8px; font-size:11px; color:#888; text-transform:uppercase; letter-spacing:0.05em;">Sell Time</th>
                    <th style="text-align:left; padding:8px; font-size:11px; color:#888; text-transform:uppercase; letter-spacing:0.05em;">Sell Price</th>
                    <th style="text-align:left; padding:8px; font-size:11px; color:#888; text-transform:uppercase; letter-spacing:0.05em;">P&L ($)</th>
                    <th style="text-align:left; padding:8px; font-size:11px; color:#888; text-transform:uppercase; letter-spacing:0.05em;">P&L (%)</th>
                    <th style="text-align:left; padding:8px; font-size:11px; color:#888; text-transform:uppercase; letter-spacing:0.05em;">Result</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div style="background:white; border-radius:14px; padding:24px; box-shadow:0 1px 4px rgba(0,0,0,0.07); text-align:center; color:#888;">
        No completed trades yet — first trade will appear here once a buy and sell both happen.
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# --- AI Insights ---
st.markdown('<div class="section-title">🤖 AI Brain Insights</div>', unsafe_allow_html=True)
conn = sqlite3.connect(DB_PATH)
try:
    ins = pd.read_sql("SELECT * FROM agent_insights ORDER BY timestamp DESC LIMIT 6", conn)
except Exception:
    ins = pd.DataFrame()
conn.close()

if not ins.empty:
    cols = st.columns(3)
    for i, (_, row) in enumerate(ins.iterrows()):
        with cols[i % 3]:
            pair_color = PAIR_COLORS.get(row["pair"], "#888")
            st.markdown(f"""
            <div style="background:white; border-radius:14px; padding:16px; box-shadow:0 1px 4px rgba(0,0,0,0.07); margin-bottom:12px;">
                <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                    <span style="background:{pair_color}22; color:{pair_color}; padding:2px 10px; border-radius:10px; font-weight:700; font-size:12px;">{row['pair']}</span>
                    <span style="font-size:11px; color:#aaa;">{row['timestamp'][:16]}</span>
                </div>
                <div style="font-size:13px; color:#444; line-height:1.5;">{row['insight'][:300]}...</div>
            </div>
            """, unsafe_allow_html=True)
