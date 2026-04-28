"""
Crypto Paper Trading Bot — Dashboard
Streamlit + Plotly. Dark theme. Run with:  streamlit run dashboard.py
"""
import os
import sys
import sqlite3
from datetime import datetime, timedelta, timezone

# Load .env BEFORE reading any env vars — must be first
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Add project dir to path so local modules resolve correctly
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

# ----------------------------------------------------------------------------- 
# Optional imports (graceful degradation)
# -----------------------------------------------------------------------------
try:
    from streamlit_autorefresh import st_autorefresh
    _AUTOREFRESH = True
except Exception:
    _AUTOREFRESH = False

try:
    from alpaca.data.historical import CryptoHistoricalDataClient
    from alpaca.data.requests import CryptoBarsRequest
    from alpaca.data.timeframe import TimeFrame
    _ALPACA_SDK = True
except Exception:
    _ALPACA_SDK = False

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
DB_PATH = os.environ.get("TRADING_DB_PATH", "trading_log.db")
ALPACA_BASE = "https://paper-api.alpaca.markets"
ALPACA_KEY = os.environ.get("ALPACA_KEY", "")
ALPACA_SECRET = os.environ.get("ALPACA_SECRET", "")

PAIRS = ["BTC/USD", "ETH/USD", "SOL/USD"]
PAIR_TO_BINANCE = {"BTC/USD": "BTCUSDT", "ETH/USD": "ETHUSDT", "SOL/USD": "SOLUSDT"}

# Color palette — light theme
C = {
    "bg": "#F4F6F9",
    "card": "#FFFFFF",
    "border": "#E2E6ED",
    "text": "#1A1D23",
    "text_secondary": "#5A6478",
    "text_muted": "#9AA0AD",
    "blue": "#2563EB",
    "green": "#059669",
    "red": "#DC2626",
    "amber": "#D97706",
    "btc": "#F7931A",
    "eth": "#627EEA",
    "sol": "#9945FF",
}
PAIR_COLOR = {"BTC/USD": C["btc"], "ETH/USD": C["eth"], "SOL/USD": C["sol"]}

# Strategy + position-size defaults (used for empty-state scaffolding)
KNOWN_STRATEGIES = ["EMA Trend", "RSI Mean Reversion", "Volume Breakout", "Bollinger Bounce", "MACD Momentum"]

# Plotly base layout helpers
def _base_layout(**overrides):
    base = dict(
        paper_bgcolor=C["card"],
        plot_bgcolor="#FAFBFD",
        font=dict(color=C["text"], family="Inter, system-ui, sans-serif", size=12),
        margin=dict(l=8, r=8, t=24, b=8),
        xaxis=dict(gridcolor=C["border"], zerolinecolor=C["border"],
                   linecolor=C["border"], tickfont=dict(color=C["text_secondary"])),
        yaxis=dict(gridcolor=C["border"], zerolinecolor=C["border"],
                   linecolor=C["border"], tickfont=dict(color=C["text_secondary"])),
        hovermode="x unified",
        showlegend=False,
    )
    base.update(overrides)
    return base


# -----------------------------------------------------------------------------
# Page config + CSS
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Crypto Bot Dashboard",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

CUSTOM_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
    background-color: {C['bg']} !important;
    color: {C['text']};
    font-family: 'Inter', system-ui, sans-serif;
}}
[data-testid="stHeader"] {{ background: transparent !important; }}
[data-testid="stToolbar"] {{ background: transparent !important; }}

.block-container {{ padding-top: 1rem; padding-bottom: 2rem; max-width: 1480px; }}

.mono {{ font-family: 'JetBrains Mono', ui-monospace, monospace; font-feature-settings: 'tnum'; }}

.card {{
    background: {C['card']};
    border: 1px solid {C['border']};
    border-radius: 10px;
    padding: 14px 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    margin-bottom: 10px;
}}
.card-tight {{ padding: 10px 12px; }}
.card h4 {{ margin: 0 0 6px 0; font-size: 11px; font-weight: 500; letter-spacing: 0.05em;
           text-transform: uppercase; color: {C['text_secondary']}; }}
.card .big {{ font-size: 22px; font-weight: 600; color: {C['text']}; }}
.card .sub {{ font-size: 12px; color: {C['text_secondary']}; margin-top: 2px; }}

.muted {{ color: {C['text_muted']}; font-size: 12px; }}
.label-sm {{ font-size: 11px; letter-spacing: 0.05em; text-transform: uppercase;
             color: {C['text_secondary']}; }}

.section-title {{
    font-size: 13px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;
    color: {C['text_secondary']}; margin: 18px 0 8px 0;
}}

.dot {{ display: inline-block; width: 9px; height: 9px; border-radius: 50%;
        margin-right: 6px; vertical-align: middle; }}
.dot-green {{ background: {C['green']}; box-shadow: 0 0 6px {C['green']}80; }}
.dot-amber {{ background: {C['amber']}; box-shadow: 0 0 6px {C['amber']}80; }}
.dot-red   {{ background: {C['red']};   box-shadow: 0 0 6px {C['red']}80; }}

.pos {{ color: {C['green']}; }}
.neg {{ color: {C['red']}; }}
.neu {{ color: {C['text_secondary']}; }}

/* fill-bar + health-bar */
.bar-track {{ position: relative; height: 6px; background: {C['border']};
              border-radius: 3px; overflow: hidden; margin-top: 6px; }}
.bar-fill  {{ position: absolute; left: 0; top: 0; bottom: 0; background: {C['blue']}; }}

.hbar {{ position: relative; height: 22px; background: {C['border']};
         border-radius: 4px; overflow: hidden; }}
.hbar .zone-sl {{ position: absolute; left: 0; top: 0; bottom: 0; width: 33.33%;
                  background: rgba(246,70,93,0.18); }}
.hbar .zone-tp {{ position: absolute; left: 33.33%; top: 0; bottom: 0; width: 66.67%;
                  background: rgba(0,192,135,0.14); }}
.hbar .mid     {{ position: absolute; left: 33.33%; top: 0; bottom: 0; width: 1px;
                  background: {C['text_muted']}; }}
.hbar .marker  {{ position: absolute; top: -2px; bottom: -2px; width: 3px;
                  border-radius: 2px; }}
.hbar-legend   {{ display: flex; justify-content: space-between; font-size: 10px;
                  color: {C['text_muted']}; margin-top: 3px; font-family: 'JetBrains Mono', monospace; }}

.tag {{ display: inline-block; padding: 2px 8px; font-size: 10px; font-weight: 500;
        letter-spacing: 0.04em; text-transform: uppercase; border-radius: 4px;
        background: {C['border']}; color: {C['text_secondary']}; margin-left: 6px; }}
.badge-low    {{ background: rgba(0,192,135,0.15); color: {C['green']}; }}
.badge-normal {{ background: rgba(76,155,232,0.15); color: {C['blue']}; }}
.badge-high   {{ background: rgba(246,70,93,0.18); color: {C['red']}; }}

table.matrix {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
table.matrix th, table.matrix td {{ border: 1px solid {C['border']}; padding: 8px 10px;
                                    text-align: center; }}
table.matrix th {{ background: {C['bg']}; color: {C['text_secondary']};
                   font-weight: 500; font-size: 11px; letter-spacing: 0.05em;
                   text-transform: uppercase; }}
table.matrix td.row-label {{ text-align: left; color: {C['text_secondary']};
                              background: {C['bg']}; font-weight: 500; }}

.reading-pane {{ max-width: 760px; margin: 0 auto; line-height: 1.65; font-size: 14px;
                 color: {C['text']}; }}
.reading-pane p {{ margin: 0 0 12px 0; }}
.reading-pane h1, .reading-pane h2, .reading-pane h3 {{ color: {C['text']}; margin-top: 18px; }}

.fng-bar {{ position: relative; height: 8px; border-radius: 4px; margin: 8px 0;
            background: linear-gradient(90deg, {C['red']} 0%, {C['amber']} 50%, {C['green']} 100%); }}
.fng-marker {{ position: absolute; top: -3px; width: 3px; height: 14px;
               background: {C['text']}; border-radius: 2px; }}

/* dataframe overrides */
[data-testid="stDataFrame"] {{ background: {C['card']}; border: 1px solid {C['border']};
                                border-radius: 8px; }}

/* tab styling */
.stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid {C['border']}; }}
.stTabs [data-baseweb="tab"] {{ background: transparent; color: {C['text_secondary']};
                                 font-size: 13px; padding: 8px 14px; border-radius: 6px 6px 0 0; }}
.stTabs [aria-selected="true"] {{ background: {C['card']}; color: {C['text']}; }}

button[kind="secondary"], .stButton button {{
    background: {C['card']}; color: {C['text']}; border: 1px solid {C['border']};
    border-radius: 6px; font-size: 12px;
}}
.stButton button:hover {{ border-color: {C['blue']}; color: {C['blue']}; }}

/* mobile stack */
@media (max-width: 900px) {{
    [data-testid="stHorizontalBlock"] {{ flex-direction: column !important; }}
    [data-testid="column"] {{ width: 100% !important; flex: 1 1 100% !important;
                              min-width: 100% !important; }}
    .reading-pane {{ max-width: 100%; }}
    .block-container {{ padding-left: 0.6rem; padding-right: 0.6rem; }}
}}

footer, [data-testid="stStatusWidget"] {{ visibility: hidden; }}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# =============================================================================
# DATA LAYER — all cached, all defensive
# =============================================================================

def _conn():
    """Open a SQLite connection. Returns None if file missing/unreadable."""
    try:
        if not os.path.exists(DB_PATH):
            return None
        c = sqlite3.connect(DB_PATH, timeout=2.0)
        c.row_factory = sqlite3.Row
        return c
    except Exception:
        return None


def _table_exists(conn, name):
    try:
        cur = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        )
        return cur.fetchone() is not None
    except Exception:
        return False


def _columns(conn, table):
    try:
        return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    except Exception:
        return []


def _safe_query(query, params=()):
    """Run a query and return a DataFrame; empty DF on any error."""
    try:
        conn = _conn()
        if conn is None:
            return pd.DataFrame()
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def _first_col(cols, candidates, default=None):
    for c in candidates:
        if c in cols:
            return c
    return default


# ----- SQLite readers -------------------------------------------------------

@st.cache_data(ttl=300)
def db_trade_signals(limit=500):
    conn = _conn()
    if conn is None or not _table_exists(conn, "trade_signals"):
        if conn:
            conn.close()
        return pd.DataFrame(columns=["timestamp", "pair", "strategy", "signal", "price", "executed"])
    cols = _columns(conn, "trade_signals")
    ts_col = _first_col(cols, ["timestamp", "ts", "time", "created_at"])
    if not ts_col:
        conn.close()
        return pd.DataFrame()
    try:
        df = pd.read_sql_query(
            f"SELECT * FROM trade_signals ORDER BY {ts_col} DESC LIMIT {int(limit)}", conn
        )
    except Exception:
        df = pd.DataFrame()
    conn.close()
    if not df.empty and ts_col in df.columns:
        df["timestamp"] = pd.to_datetime(df[ts_col], errors="coerce", utc=True)
    return df


@st.cache_data(ttl=300)
def db_completed_trades(limit=2000):
    conn = _conn()
    if conn is None or not _table_exists(conn, "completed_trades"):
        if conn:
            conn.close()
        return pd.DataFrame()
    cols = _columns(conn, "completed_trades")
    ts_col = _first_col(cols, ["exit_time", "closed_at", "timestamp", "time", "exit_timestamp"])
    try:
        if ts_col:
            df = pd.read_sql_query(
                f"SELECT * FROM completed_trades ORDER BY {ts_col} DESC LIMIT {int(limit)}", conn
            )
        else:
            df = pd.read_sql_query(f"SELECT * FROM completed_trades LIMIT {int(limit)}", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    if not df.empty:
        for c in ("exit_time", "entry_time", "timestamp", "closed_at"):
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], errors="coerce", utc=True)
    return df


@st.cache_data(ttl=300)
def db_backtest_runs():
    conn = _conn()
    if conn is None or not _table_exists(conn, "backtest_runs"):
        if conn:
            conn.close()
        return pd.DataFrame()
    try:
        df = pd.read_sql_query("SELECT * FROM backtest_runs", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df


@st.cache_data(ttl=300)
def db_agent_insights(limit=200):
    conn = _conn()
    if conn is None or not _table_exists(conn, "agent_insights"):
        if conn:
            conn.close()
        return pd.DataFrame()
    cols = _columns(conn, "agent_insights")
    ts_col = _first_col(cols, ["timestamp", "created_at", "ts", "time", "date"])
    try:
        if ts_col:
            df = pd.read_sql_query(
                f"SELECT * FROM agent_insights ORDER BY {ts_col} DESC LIMIT {int(limit)}", conn
            )
        else:
            df = pd.read_sql_query(f"SELECT * FROM agent_insights LIMIT {int(limit)}", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    if not df.empty and ts_col and ts_col in df.columns:
        df["timestamp"] = pd.to_datetime(df[ts_col], errors="coerce", utc=True)
    return df


@st.cache_data(ttl=300)
def db_memory(limit=200):
    conn = _conn()
    if conn is None or not _table_exists(conn, "memory"):
        if conn:
            conn.close()
        return pd.DataFrame()
    cols = _columns(conn, "memory")
    ts_col = _first_col(cols, ["timestamp", "created_at", "ts", "time"])
    try:
        if ts_col:
            df = pd.read_sql_query(
                f"SELECT * FROM memory ORDER BY {ts_col} DESC LIMIT {int(limit)}", conn
            )
        else:
            df = pd.read_sql_query(f"SELECT * FROM memory LIMIT {int(limit)}", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    if not df.empty and ts_col and ts_col in df.columns:
        df["timestamp"] = pd.to_datetime(df[ts_col], errors="coerce", utc=True)
    return df


# ----- Alpaca paper API -----------------------------------------------------

def _alpaca_headers():
    return {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
        "accept": "application/json",
    }


@st.cache_data(ttl=60)
def alpaca_account():
    if not ALPACA_KEY or not ALPACA_SECRET:
        return {}
    try:
        r = requests.get(f"{ALPACA_BASE}/v2/account", headers=_alpaca_headers(), timeout=6)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


@st.cache_data(ttl=60)
def alpaca_positions():
    if not ALPACA_KEY or not ALPACA_SECRET:
        return []
    try:
        r = requests.get(f"{ALPACA_BASE}/v2/positions", headers=_alpaca_headers(), timeout=6)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []


@st.cache_data(ttl=300)
def alpaca_portfolio_history():
    if not ALPACA_KEY or not ALPACA_SECRET:
        return pd.DataFrame()
    try:
        r = requests.get(
            f"{ALPACA_BASE}/v2/account/portfolio/history",
            params={"period": "1M", "timeframe": "1H"},
            headers=_alpaca_headers(),
            timeout=8,
        )
        if r.status_code != 200:
            return pd.DataFrame()
        d = r.json()
        ts = d.get("timestamp", [])
        eq = d.get("equity", [])
        if not ts or not eq:
            return pd.DataFrame()
        df = pd.DataFrame(
            {
                "time": pd.to_datetime(ts, unit="s", utc=True),
                "equity": [float(x) if x is not None else np.nan for x in eq],
            }
        ).dropna()
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=60)
def alpaca_crypto_bars(symbol, days=7):
    """Fetch hourly bars for a crypto symbol like 'BTC/USD'."""
    if not _ALPACA_SDK or not ALPACA_KEY or not ALPACA_SECRET:
        return pd.DataFrame()
    try:
        client = CryptoHistoricalDataClient(ALPACA_KEY, ALPACA_SECRET)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        req = CryptoBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=TimeFrame.Hour,
            start=start,
            end=end,
        )
        bars = client.get_crypto_bars(req).df
        if bars is None or bars.empty:
            return pd.DataFrame()
        if isinstance(bars.index, pd.MultiIndex):
            bars = bars.xs(symbol, level=0) if symbol in bars.index.get_level_values(0) else bars.droplevel(0)
        bars = bars.reset_index().rename(columns={"timestamp": "time"})
        if "time" not in bars.columns:
            bars["time"] = bars.index
        bars["time"] = pd.to_datetime(bars["time"], utc=True, errors="coerce")
        return bars
    except Exception:
        return pd.DataFrame()


# ----- Public free APIs -----------------------------------------------------

@st.cache_data(ttl=300)
def fear_greed(limit=30):
    try:
        r = requests.get(f"https://api.alternative.me/fng/?limit={int(limit)}", timeout=5)
        if r.status_code != 200:
            return pd.DataFrame()
        data = r.json().get("data", [])
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["timestamp"] = pd.to_datetime(pd.to_numeric(df["timestamp"], errors="coerce"), unit="s", utc=True)
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def funding_rates():
    """Latest funding rates from Binance perp (free, no key)."""
    try:
        r = requests.get("https://fapi.binance.com/fapi/v1/premiumIndex", timeout=5)
        if r.status_code != 200:
            return {}
        rows = r.json()
        out = {}
        wanted = set(PAIR_TO_BINANCE.values())
        for row in rows:
            sym = row.get("symbol")
            if sym in wanted:
                try:
                    out[sym] = float(row.get("lastFundingRate", 0))
                except Exception:
                    pass
        return out
    except Exception:
        return {}


# ----- helpers --------------------------------------------------------------

def _fmt_money(v, decimals=2):
    try:
        return f"${float(v):,.{decimals}f}"
    except Exception:
        return "—"


def _fmt_pct(v, decimals=2, sign=True):
    try:
        x = float(v)
        s = f"{x:+.{decimals}f}%" if sign else f"{x:.{decimals}f}%"
        return s
    except Exception:
        return "—"


def _pnl_class(v):
    try:
        x = float(v)
        if x > 0:
            return "pos"
        if x < 0:
            return "neg"
    except Exception:
        pass
    return "neu"


def _atr_pct(bars, period=14):
    """ATR as % of last close, from an OHLC dataframe."""
    if bars is None or bars.empty or len(bars) < period + 1:
        return None
    try:
        high = bars["high"].astype(float)
        low = bars["low"].astype(float)
        close = bars["close"].astype(float)
        prev_close = close.shift(1)
        tr = pd.concat(
            [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(period).mean().iloc[-1]
        last = close.iloc[-1]
        if not last or np.isnan(atr):
            return None
        return float(atr / last * 100.0)
    except Exception:
        return None


def _sparkline(values, color):
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            y=list(values),
            mode="lines",
            line=dict(color=color, width=1.6),
            hoverinfo="skip",
        )
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0),
        height=44,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False,
    )
    return fig


def _empty_placeholder(text):
    st.markdown(
        f'<div class="card" style="text-align:center; color:{C["text_muted"]};">{text}</div>',
        unsafe_allow_html=True,
    )


# =============================================================================
# RENDER FUNCTIONS
# =============================================================================

def render_header():
    """Bot status, three pair tickers w/ sparkline, Fear & Greed mini bar."""
    try:
        # bot status from most recent trade_signals timestamp
        sigs = db_trade_signals(limit=1)
        now = datetime.now(timezone.utc)
        if not sigs.empty and "timestamp" in sigs.columns and pd.notna(sigs["timestamp"].iloc[0]):
            last = sigs["timestamp"].iloc[0].to_pydatetime()
            mins = (now - last).total_seconds() / 60.0
            if mins < 90:
                dot, label = "dot-green", f"Active · {int(mins)}m ago"
            elif mins < 360:
                dot, label = "dot-amber", f"Idle · {int(mins)}m ago"
            else:
                hrs = mins / 60.0
                dot, label = "dot-red", f"Stale · {hrs:.1f}h ago"
        else:
            dot, label = "dot-red", "No signals yet"

        cols = st.columns([2, 2, 2, 2, 2.2])

        with cols[0]:
            st.markdown(
                f'<div class="card card-tight" style="height:80px;">'
                f'<div class="label-sm">Bot Status</div>'
                f'<div style="margin-top:8px;font-size:14px;">'
                f'<span class="dot {dot}"></span>{label}'
                f'</div></div>',
                unsafe_allow_html=True,
            )

        # tickers
        for i, pair in enumerate(PAIRS):
            with cols[i + 1]:
                bars = alpaca_crypto_bars(pair, days=2)
                if bars is None or bars.empty or "close" not in bars.columns:
                    st.markdown(
                        f'<div class="card card-tight" style="height:80px;">'
                        f'<div class="label-sm" style="color:{PAIR_COLOR[pair]}">{pair}</div>'
                        f'<div class="muted" style="margin-top:18px;">No data</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    continue
                closes = bars["close"].astype(float).tolist()
                price = closes[-1]
                ago_24 = closes[-25] if len(closes) >= 25 else closes[0]
                pct = (price / ago_24 - 1.0) * 100.0 if ago_24 else 0.0
                pct_cls = "pos" if pct >= 0 else "neg"
                last30 = closes[-30:] if len(closes) >= 30 else closes
                spark_color = C["green"] if pct >= 0 else C["red"]
                st.markdown(
                    f'<div class="card card-tight" style="height:80px; position:relative;">'
                    f'<div style="display:flex; justify-content:space-between; align-items:baseline;">'
                    f'<span class="label-sm" style="color:{PAIR_COLOR[pair]}">{pair}</span>'
                    f'<span class="mono {pct_cls}" style="font-size:11px;">{_fmt_pct(pct)}</span>'
                    f'</div>'
                    f'<div class="mono" style="font-size:18px;font-weight:600;margin-top:2px;">'
                    f'${price:,.2f}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.plotly_chart(
                    _sparkline(last30, spark_color),
                    use_container_width=True,
                    config={"displayModeBar": False},
                    key=f"spark_{pair}",
                )

        # Fear & Greed mini bar
        with cols[4]:
            fg = fear_greed(limit=1)
            if fg is None or fg.empty:
                st.markdown(
                    f'<div class="card card-tight" style="height:80px;">'
                    f'<div class="label-sm">Fear &amp; Greed</div>'
                    f'<div class="muted" style="margin-top:18px;">Unavailable</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                v = int(fg["value"].iloc[-1])
                cls = fg["value_classification"].iloc[-1] if "value_classification" in fg.columns else ""
                st.markdown(
                    f'<div class="card card-tight" style="height:80px;">'
                    f'<div style="display:flex; justify-content:space-between;">'
                    f'<span class="label-sm">Fear &amp; Greed</span>'
                    f'<span class="mono" style="font-size:14px;font-weight:600;">{v}</span>'
                    f'</div>'
                    f'<div class="fng-bar"><div class="fng-marker" style="left:calc({v}% - 1px);"></div></div>'
                    f'<div class="muted" style="font-size:11px;">{cls}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
    except Exception as e:
        _empty_placeholder(f"Header unavailable")


def render_portfolio_strip():
    """5 cards: Equity, Today's P&L, Unrealized P&L, Cash, Deployed %."""
    try:
        acct = alpaca_account()
        positions = alpaca_positions()

        equity = float(acct.get("equity", 0) or 0)
        last_equity = float(acct.get("last_equity", 0) or 0)
        cash = float(acct.get("cash", 0) or 0)
        long_mv = float(acct.get("long_market_value", 0) or 0)

        today_pnl = equity - last_equity if last_equity else 0.0
        today_pnl_pct = (today_pnl / last_equity * 100.0) if last_equity else 0.0

        unreal = 0.0
        for p in positions:
            try:
                unreal += float(p.get("unrealized_pl", 0) or 0)
            except Exception:
                pass

        deployed_pct = (long_mv / equity * 100.0) if equity else 0.0

        cols = st.columns(5)
        with cols[0]:
            st.markdown(
                f'<div class="card"><h4>Equity</h4>'
                f'<div class="big mono">{_fmt_money(equity)}</div>'
                f'<div class="sub">Account total</div></div>',
                unsafe_allow_html=True,
            )
        with cols[1]:
            st.markdown(
                f'<div class="card"><h4>Today\'s P&amp;L</h4>'
                f'<div class="big mono {_pnl_class(today_pnl)}">{_fmt_money(today_pnl)}</div>'
                f'<div class="sub mono {_pnl_class(today_pnl_pct)}">{_fmt_pct(today_pnl_pct)}</div></div>',
                unsafe_allow_html=True,
            )
        with cols[2]:
            st.markdown(
                f'<div class="card"><h4>Unrealized P&amp;L</h4>'
                f'<div class="big mono {_pnl_class(unreal)}">{_fmt_money(unreal)}</div>'
                f'<div class="sub">{len(positions)} open position{"s" if len(positions)!=1 else ""}</div></div>',
                unsafe_allow_html=True,
            )
        with cols[3]:
            st.markdown(
                f'<div class="card"><h4>Cash</h4>'
                f'<div class="big mono">{_fmt_money(cash)}</div>'
                f'<div class="sub">Buying power</div></div>',
                unsafe_allow_html=True,
            )
        with cols[4]:
            fill_w = max(0.0, min(100.0, deployed_pct))
            st.markdown(
                f'<div class="card"><h4>Deployed</h4>'
                f'<div class="big mono">{_fmt_pct(deployed_pct, sign=False)}</div>'
                f'<div class="bar-track"><div class="bar-fill" style="width:{fill_w:.1f}%;"></div></div>'
                f'<div class="sub mono">{_fmt_money(long_mv)} in market</div></div>',
                unsafe_allow_html=True,
            )
    except Exception:
        _empty_placeholder("Portfolio data unavailable — check ALPACA_KEY / ALPACA_SECRET")


def render_equity_curve():
    """30-day equity area chart + 7×24 trade-count heatmap."""
    st.markdown('<div class="section-title">Equity & Activity</div>', unsafe_allow_html=True)
    try:
        col1, col2 = st.columns([1.6, 1])

        # ---- equity curve ----
        with col1:
            ph = alpaca_portfolio_history()
            fig = go.Figure()
            if ph is None or ph.empty:
                fig.add_annotation(
                    text="No portfolio history yet",
                    xref="paper", yref="paper", x=0.5, y=0.5,
                    showarrow=False, font=dict(color=C["text_muted"], size=13),
                )
            else:
                fig.add_trace(
                    go.Scatter(
                        x=ph["time"], y=ph["equity"], mode="lines",
                        line=dict(color=C["blue"], width=2),
                        fill="tozeroy", fillcolor="rgba(76,155,232,0.10)",
                        hovertemplate="%{x|%b %d %H:%M}<br>$%{y:,.2f}<extra></extra>",
                    )
                )
                ymin = float(ph["equity"].min()) * 0.995
                ymax = float(ph["equity"].max()) * 1.005
                fig.update_yaxes(range=[ymin, ymax])
            fig.update_layout(
                **_base_layout(
                    height=280,
                    title=dict(text="30-Day Equity", x=0.01, xanchor="left",
                               font=dict(size=12, color=C["text_secondary"])),
                )
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # ---- heatmap ----
        with col2:
            ct = db_completed_trades(limit=5000)
            grid = np.zeros((7, 24), dtype=int)
            if not ct.empty:
                ts_col = "exit_time" if "exit_time" in ct.columns else (
                    "entry_time" if "entry_time" in ct.columns else (
                        "timestamp" if "timestamp" in ct.columns else None
                    )
                )
                if ts_col:
                    times = pd.to_datetime(ct[ts_col], errors="coerce", utc=True).dropna()
                    for t in times:
                        grid[t.dayofweek, t.hour] += 1

            days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            hours = [f"{h:02d}" for h in range(24)]
            heat = go.Figure(
                go.Heatmap(
                    z=grid, x=hours, y=days,
                    colorscale=[
                        [0.0, C["card"]],
                        [0.01, "#1A2530"],
                        [0.4, "#1F4A6E"],
                        [1.0, C["blue"]],
                    ],
                    showscale=False,
                    hovertemplate="%{y} · %{x}:00<br>%{z} trades<extra></extra>",
                    xgap=1, ygap=1,
                )
            )
            heat.update_layout(
                **_base_layout(
                    height=280,
                    title=dict(text="Trade Activity (Day × Hour UTC)", x=0.01, xanchor="left",
                               font=dict(size=12, color=C["text_secondary"])),
                    xaxis=dict(showgrid=False, tickfont=dict(size=9, color=C["text_muted"])),
                    yaxis=dict(showgrid=False, tickfont=dict(size=10, color=C["text_secondary"])),
                )
            )
            st.plotly_chart(heat, use_container_width=True, config={"displayModeBar": False})
    except Exception:
        _empty_placeholder("Equity & activity unavailable")


def render_positions():
    """One card per open position with health bar."""
    st.markdown('<div class="section-title">Open Positions</div>', unsafe_allow_html=True)
    try:
        positions = alpaca_positions()
        if not positions:
            _empty_placeholder("No open positions")
            return

        # try to map symbol -> last strategy from trade_signals
        sigs = db_trade_signals(limit=500)
        strat_for = {}
        if not sigs.empty and "pair" in sigs.columns and "strategy" in sigs.columns:
            for _, r in sigs.iterrows():
                p = str(r.get("pair", "")).upper().replace("USDT", "USD")
                if p and p not in strat_for:
                    strat_for[p] = r.get("strategy", "")

        # render in rows of 3
        for i in range(0, len(positions), 3):
            row = positions[i:i + 3]
            cols = st.columns(3)
            for j, p in enumerate(row):
                with cols[j]:
                    sym = p.get("symbol", "")
                    pretty = sym
                    if "USD" in sym and "/" not in sym:
                        # e.g. BTCUSD -> BTC/USD
                        pretty = sym.replace("USD", "/USD")
                    try:
                        entry = float(p.get("avg_entry_price", 0) or 0)
                        current = float(p.get("current_price", 0) or 0)
                        qty = float(p.get("qty", 0) or 0)
                        upl = float(p.get("unrealized_pl", 0) or 0)
                        upl_pct = float(p.get("unrealized_plpc", 0) or 0) * 100.0
                    except Exception:
                        entry = current = qty = upl = upl_pct = 0.0

                    # health bar: track from -3% (SL) to +6% (TP)
                    sl_pct, tp_pct = -3.0, 6.0
                    span = tp_pct - sl_pct
                    pos_pct = max(sl_pct, min(tp_pct, upl_pct))
                    left = (pos_pct - sl_pct) / span * 100.0
                    # marker color by zone: red near SL, green near TP, amber middle
                    if upl_pct <= -1.5:
                        mc = C["red"]
                    elif upl_pct >= 3.0:
                        mc = C["green"]
                    elif upl_pct < 0:
                        mc = C["amber"]
                    else:
                        mc = C["blue"]

                    strat = strat_for.get(pretty.upper(), "—")
                    pcls = _pnl_class(upl)

                    st.markdown(
                        f'<div class="card">'
                        f'<div style="display:flex; justify-content:space-between; align-items:center;">'
                        f'<span style="font-weight:600; color:{PAIR_COLOR.get(pretty, C["text"])};">{pretty}</span>'
                        f'<span class="tag">{strat}</span>'
                        f'</div>'
                        f'<div style="display:grid; grid-template-columns:1fr 1fr; gap:6px; margin:10px 0;">'
                        f'  <div><div class="muted">Entry</div><div class="mono">${entry:,.2f}</div></div>'
                        f'  <div><div class="muted">Current</div><div class="mono">${current:,.2f}</div></div>'
                        f'  <div><div class="muted">Qty</div><div class="mono">{qty:.6g}</div></div>'
                        f'  <div><div class="muted">P&amp;L</div>'
                        f'    <div class="mono {pcls}">{_fmt_money(upl)} <span style="font-size:11px;">({_fmt_pct(upl_pct)})</span></div>'
                        f'  </div>'
                        f'</div>'
                        f'<div class="hbar">'
                        f'  <div class="zone-sl"></div><div class="zone-tp"></div><div class="mid"></div>'
                        f'  <div class="marker" style="left:calc({left:.2f}% - 1.5px); background:{mc};"></div>'
                        f'</div>'
                        f'<div class="hbar-legend"><span>SL −3%</span><span>0%</span><span>TP +6%</span></div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
    except Exception:
        _empty_placeholder("Positions unavailable")


def render_strategy_matrix():
    """Strategy × pair matrix of win-rate / count."""
    st.markdown('<div class="section-title">Strategy Matrix</div>', unsafe_allow_html=True)
    try:
        ct = db_completed_trades(limit=10000)
        bt = db_backtest_runs()

        # Determine strategies present
        strategies = set()
        if not ct.empty and "strategy" in ct.columns:
            strategies.update([s for s in ct["strategy"].dropna().astype(str).unique()])
        if not bt.empty and "strategy" in bt.columns:
            strategies.update([s for s in bt["strategy"].dropna().astype(str).unique()])
        if not strategies:
            strategies = set(KNOWN_STRATEGIES)
        strategies = sorted(strategies)

        def cell_for(strategy, pair):
            # 1) live completed trades
            wr, n = None, 0
            if not ct.empty and "strategy" in ct.columns and "pair" in ct.columns:
                sub = ct[(ct["strategy"] == strategy) & (ct["pair"] == pair)]
                n = len(sub)
                if n > 0:
                    pnl_col = _first_col(sub.columns.tolist(), ["pnl", "profit", "pnl_usd"])
                    pct_col = _first_col(sub.columns.tolist(), ["pnl_pct", "return_pct", "pct"])
                    res_col = _first_col(sub.columns.tolist(), ["result", "outcome"])
                    if pnl_col:
                        wins = (pd.to_numeric(sub[pnl_col], errors="coerce") > 0).sum()
                        wr = wins / n * 100.0
                    elif pct_col:
                        wins = (pd.to_numeric(sub[pct_col], errors="coerce") > 0).sum()
                        wr = wins / n * 100.0
                    elif res_col:
                        wins = sub[res_col].astype(str).str.lower().isin(["win", "won", "tp", "profit"]).sum()
                        wr = wins / n * 100.0
            # 2) fallback to backtest
            if wr is None and not bt.empty and "strategy" in bt.columns and "pair" in bt.columns:
                sub2 = bt[(bt["strategy"] == strategy) & (bt["pair"] == pair)]
                if not sub2.empty:
                    wcol = _first_col(sub2.columns.tolist(), ["win_rate", "winrate", "win_pct"])
                    ncol = _first_col(sub2.columns.tolist(), ["trade_count", "trades", "n_trades", "count"])
                    if wcol:
                        try:
                            wr = float(sub2[wcol].iloc[0])
                            if wr <= 1.0:
                                wr *= 100.0
                        except Exception:
                            wr = None
                    if ncol and n == 0:
                        try:
                            n = int(sub2[ncol].iloc[0])
                        except Exception:
                            pass
            return wr, n

        rows_html = []
        for strat in strategies:
            cells = [f'<td class="row-label">{strat}</td>']
            for pair in PAIRS:
                wr, n = cell_for(strat, pair)
                if wr is None:
                    bg = "transparent"
                    inner = '<span class="muted">—</span>'
                else:
                    if wr > 55:
                        bg = "rgba(0,192,135,0.15)"
                    elif wr >= 45:
                        bg = "rgba(240,185,11,0.13)"
                    else:
                        bg = "rgba(246,70,93,0.15)"
                    inner = (
                        f'<div class="mono" style="font-size:14px;font-weight:600;">{wr:.0f}%</div>'
                        f'<div class="muted" style="font-size:11px;">n={n}</div>'
                    )
                cells.append(f'<td style="background:{bg};">{inner}</td>')
            rows_html.append("<tr>" + "".join(cells) + "</tr>")

        header = "<tr><th>Strategy</th>" + "".join(
            f'<th style="color:{PAIR_COLOR[p]}">{p}</th>' for p in PAIRS
        ) + "</tr>"
        st.markdown(
            f'<div class="card" style="padding:14px;">'
            f'<table class="matrix">{header}{"".join(rows_html)}</table>'
            f'</div>',
            unsafe_allow_html=True,
        )
    except Exception:
        _empty_placeholder("Strategy matrix unavailable")


def render_price_charts():
    """7-day 1h candles + EMA21/EMA200 + volume + signal markers + open-position lines."""
    st.markdown('<div class="section-title">Price Charts (7d · 1h)</div>', unsafe_allow_html=True)
    try:
        positions = alpaca_positions()
        entries = {}
        for p in positions:
            sym = p.get("symbol", "")
            pretty = sym.replace("USD", "/USD") if "USD" in sym and "/" not in sym else sym
            try:
                entries[pretty] = float(p.get("avg_entry_price", 0) or 0)
            except Exception:
                pass

        sigs = db_trade_signals(limit=2000)

        cols = st.columns(3)
        for idx, pair in enumerate(PAIRS):
            with cols[idx]:
                bars = alpaca_crypto_bars(pair, days=7)
                if bars is None or bars.empty:
                    _empty_placeholder(f"{pair} — no bars")
                    continue

                bars = bars.sort_values("time").reset_index(drop=True)
                bars["ema21"] = bars["close"].ewm(span=21, adjust=False).mean()
                bars["ema200"] = bars["close"].ewm(span=200, adjust=False).mean()

                fig = make_subplots(
                    rows=2, cols=1, shared_xaxes=True,
                    row_heights=[0.78, 0.22], vertical_spacing=0.02,
                )
                fig.add_trace(
                    go.Candlestick(
                        x=bars["time"], open=bars["open"], high=bars["high"],
                        low=bars["low"], close=bars["close"],
                        increasing_line_color=C["green"], increasing_fillcolor=C["green"],
                        decreasing_line_color=C["red"], decreasing_fillcolor=C["red"],
                        name="Price", showlegend=False,
                    ),
                    row=1, col=1,
                )
                fig.add_trace(
                    go.Scatter(
                        x=bars["time"], y=bars["ema21"], mode="lines",
                        line=dict(color="rgba(76,155,232,0.55)", width=1.2),
                        name="EMA21", hoverinfo="skip", showlegend=False,
                    ),
                    row=1, col=1,
                )
                fig.add_trace(
                    go.Scatter(
                        x=bars["time"], y=bars["ema200"], mode="lines",
                        line=dict(color="rgba(240,185,11,0.55)", width=1.2),
                        name="EMA200", hoverinfo="skip", showlegend=False,
                    ),
                    row=1, col=1,
                )

                # volume colored by candle direction
                vol_colors = [
                    C["green"] if c >= o else C["red"]
                    for o, c in zip(bars["open"], bars["close"])
                ]
                if "volume" in bars.columns:
                    fig.add_trace(
                        go.Bar(
                            x=bars["time"], y=bars["volume"],
                            marker_color=vol_colors, opacity=0.55,
                            hoverinfo="skip", showlegend=False,
                        ),
                        row=2, col=1,
                    )

                # signal triangles
                if not sigs.empty and "pair" in sigs.columns:
                    sub = sigs[sigs["pair"].astype(str).str.upper() == pair.upper()]
                    if not sub.empty and "signal" in sub.columns:
                        cutoff = bars["time"].min()
                        sub = sub[sub["timestamp"] >= cutoff] if "timestamp" in sub.columns else sub
                        price_col = _first_col(sub.columns.tolist(), ["price", "entry_price", "fill_price"])
                        if price_col and "timestamp" in sub.columns:
                            buys = sub[sub["signal"].astype(str).str.upper().isin(["BUY", "LONG"])]
                            sells = sub[sub["signal"].astype(str).str.upper().isin(["SELL", "SHORT", "CLOSE"])]
                            if not buys.empty:
                                fig.add_trace(
                                    go.Scatter(
                                        x=buys["timestamp"], y=pd.to_numeric(buys[price_col], errors="coerce"),
                                        mode="markers",
                                        marker=dict(symbol="triangle-up", color=C["green"],
                                                    size=10, line=dict(width=0)),
                                        name="Buy", showlegend=False, hoverinfo="skip",
                                    ),
                                    row=1, col=1,
                                )
                            if not sells.empty:
                                fig.add_trace(
                                    go.Scatter(
                                        x=sells["timestamp"], y=pd.to_numeric(sells[price_col], errors="coerce"),
                                        mode="markers",
                                        marker=dict(symbol="triangle-down", color=C["red"],
                                                    size=10, line=dict(width=0)),
                                        name="Sell", showlegend=False, hoverinfo="skip",
                                    ),
                                    row=1, col=1,
                                )

                # entry line for open position
                if pair in entries and entries[pair] > 0:
                    fig.add_hline(
                        y=entries[pair], line_dash="dot",
                        line_color=C["amber"], line_width=1,
                        row=1, col=1,
                        annotation_text=f"Entry ${entries[pair]:,.2f}",
                        annotation_position="top right",
                        annotation_font=dict(color=C["amber"], size=10),
                    )

                fig.update_layout(
                    **_base_layout(
                        height=380,
                        title=dict(text=pair, x=0.01, xanchor="left",
                                   font=dict(size=13, color=PAIR_COLOR[pair])),
                    )
                )
                fig.update_xaxes(rangeslider_visible=False, gridcolor=C["border"], row=1, col=1)
                fig.update_xaxes(rangeslider_visible=False, gridcolor=C["border"], row=2, col=1)
                fig.update_yaxes(gridcolor=C["border"], row=1, col=1)
                fig.update_yaxes(gridcolor=C["border"], row=2, col=1, showticklabels=False)

                st.plotly_chart(fig, use_container_width=True,
                                config={"displayModeBar": False}, key=f"chart_{pair}")
    except Exception:
        _empty_placeholder("Price charts unavailable")


def render_activity():
    """Tabs: Trades / Signals."""
    st.markdown('<div class="section-title">Activity</div>', unsafe_allow_html=True)
    try:
        tab_trades, tab_signals = st.tabs(["Trades", "Signals"])

        with tab_trades:
            ct = db_completed_trades(limit=300)
            if ct.empty:
                _empty_placeholder("No completed trades yet")
            else:
                df = ct.copy()
                ts_col = _first_col(df.columns.tolist(), ["exit_time", "closed_at", "timestamp", "entry_time"])
                pnl_col = _first_col(df.columns.tolist(), ["pnl", "profit", "pnl_usd"])
                pct_col = _first_col(df.columns.tolist(), ["pnl_pct", "return_pct", "pct"])
                ec = _first_col(df.columns.tolist(), ["entry_price", "entry"])
                xc = _first_col(df.columns.tolist(), ["exit_price", "exit"])
                rc = _first_col(df.columns.tolist(), ["result", "outcome"])

                out = pd.DataFrame()
                if ts_col:
                    t = pd.to_datetime(df[ts_col], errors="coerce", utc=True)
                    now = datetime.now(timezone.utc)
                    out["time"] = t.apply(lambda x: _relative(x, now) if pd.notna(x) else "—")
                else:
                    out["time"] = "—"
                out["pair"] = df["pair"] if "pair" in df.columns else "—"
                out["strategy"] = df["strategy"] if "strategy" in df.columns else "—"
                out["entry"] = pd.to_numeric(df[ec], errors="coerce").map(lambda x: f"${x:,.2f}" if pd.notna(x) else "—") if ec else "—"
                out["exit"] = pd.to_numeric(df[xc], errors="coerce").map(lambda x: f"${x:,.2f}" if pd.notna(x) else "—") if xc else "—"
                out["P&L $"] = pd.to_numeric(df[pnl_col], errors="coerce").map(lambda x: f"{x:+,.2f}" if pd.notna(x) else "—") if pnl_col else "—"
                out["P&L %"] = pd.to_numeric(df[pct_col], errors="coerce").map(lambda x: f"{x:+.2f}%" if pd.notna(x) else "—") if pct_col else "—"
                if rc:
                    out["result"] = df[rc].astype(str)
                elif pnl_col:
                    out["result"] = pd.to_numeric(df[pnl_col], errors="coerce").map(
                        lambda x: "WIN" if pd.notna(x) and x > 0 else ("LOSS" if pd.notna(x) and x < 0 else "—")
                    )
                else:
                    out["result"] = "—"

                st.dataframe(out, use_container_width=True, hide_index=True, height=360)

        with tab_signals:
            sigs = db_trade_signals(limit=500)
            if sigs.empty:
                _empty_placeholder("No signals recorded")
            else:
                df = sigs.copy()
                ts_col = _first_col(df.columns.tolist(), ["timestamp", "ts", "time", "created_at"])
                pc = _first_col(df.columns.tolist(), ["price", "entry_price"])

                out = pd.DataFrame()
                if ts_col:
                    t = pd.to_datetime(df[ts_col], errors="coerce", utc=True)
                    now = datetime.now(timezone.utc)
                    out["time"] = t.apply(lambda x: _relative(x, now) if pd.notna(x) else "—")
                else:
                    out["time"] = "—"
                out["pair"] = df["pair"] if "pair" in df.columns else "—"
                out["strategy"] = df["strategy"] if "strategy" in df.columns else "—"
                out["signal"] = df["signal"] if "signal" in df.columns else "—"
                out["price"] = pd.to_numeric(df[pc], errors="coerce").map(lambda x: f"${x:,.2f}" if pd.notna(x) else "—") if pc else "—"
                if "executed" in df.columns:
                    out["executed"] = df["executed"].astype(str)

                st.dataframe(out, use_container_width=True, hide_index=True, height=360)
    except Exception:
        _empty_placeholder("Activity unavailable")


def _relative(ts, now):
    """Return 'Xm ago' / 'Xh ago' / 'Xd ago' relative string."""
    try:
        delta = (now - ts.to_pydatetime()) if hasattr(ts, "to_pydatetime") else (now - ts)
        s = delta.total_seconds()
        if s < 60:
            return f"{int(s)}s ago"
        if s < 3600:
            return f"{int(s/60)}m ago"
        if s < 86400:
            return f"{int(s/3600)}h ago"
        return f"{int(s/86400)}d ago"
    except Exception:
        return "—"


def render_sentiment():
    """3 cards: funding rates, fear & greed trend, ATR-based volatility."""
    st.markdown('<div class="section-title">Market Sentiment</div>', unsafe_allow_html=True)
    try:
        cols = st.columns(3)

        # ---- funding rates ----
        with cols[0]:
            rates = funding_rates()
            rows = []
            for pair in PAIRS:
                bsym = PAIR_TO_BINANCE[pair]
                v = rates.get(bsym)
                if v is None:
                    rows.append(
                        f'<div style="display:flex;justify-content:space-between;'
                        f'padding:6px 0;border-bottom:1px solid {C["border"]};">'
                        f'<span style="color:{PAIR_COLOR[pair]}">{pair}</span>'
                        f'<span class="muted mono">—</span></div>'
                    )
                    continue
                pct = v * 100.0
                # crowding: large positive = longs crowded; large negative = shorts crowded
                if pct > 0.05:
                    cval = C["red"]
                    tag = "Longs crowded"
                elif pct < -0.05:
                    cval = C["red"]
                    tag = "Shorts crowded"
                elif abs(pct) > 0.02:
                    cval = C["amber"]
                    tag = "Mild bias"
                else:
                    cval = C["green"]
                    tag = "Neutral"
                rows.append(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'padding:8px 0;border-bottom:1px solid {C["border"]};">'
                    f'<div><div style="color:{PAIR_COLOR[pair]};font-weight:500;">{pair}</div>'
                    f'<div class="muted" style="font-size:10px;">{tag}</div></div>'
                    f'<span class="mono" style="color:{cval};font-weight:600;">{pct:+.4f}%</span>'
                    f'</div>'
                )
            st.markdown(
                f'<div class="card"><h4>Funding Rates · 8h</h4>{"".join(rows)}'
                f'<div class="muted" style="margin-top:8px;font-size:10px;">Source: Binance perp</div></div>',
                unsafe_allow_html=True,
            )

        # ---- fear & greed trend ----
        with cols[1]:
            fg = fear_greed(limit=30)
            if fg is None or fg.empty:
                st.markdown(
                    f'<div class="card"><h4>Fear &amp; Greed · 30d</h4>'
                    f'<div class="muted">Unavailable</div></div>',
                    unsafe_allow_html=True,
                )
            else:
                cur = int(fg["value"].iloc[-1])
                cls = fg["value_classification"].iloc[-1] if "value_classification" in fg.columns else ""
                fig = go.Figure(
                    go.Scatter(
                        x=fg["timestamp"], y=fg["value"], mode="lines",
                        line=dict(color=C["amber"], width=1.8),
                        fill="tozeroy", fillcolor="rgba(240,185,11,0.10)",
                        hovertemplate="%{x|%b %d}<br>%{y}<extra></extra>",
                    )
                )
                fig.update_layout(
                    **_base_layout(
                        height=120,
                        margin=dict(l=4, r=4, t=4, b=4),
                        yaxis=dict(range=[0, 100], gridcolor=C["border"],
                                   tickfont=dict(size=9, color=C["text_muted"])),
                        xaxis=dict(showgrid=False, tickfont=dict(size=9, color=C["text_muted"])),
                    )
                )
                st.markdown(
                    f'<div class="card"><h4>Fear &amp; Greed · 30d</h4>'
                    f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
                    f'<span class="mono" style="font-size:24px;font-weight:600;">{cur}</span>'
                    f'<span class="muted">{cls}</span></div></div>',
                    unsafe_allow_html=True,
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # ---- volatility (ATR%) ----
        with cols[2]:
            rows = []
            for pair in PAIRS:
                bars = alpaca_crypto_bars(pair, days=7)
                atr = _atr_pct(bars)
                if atr is None:
                    rows.append(
                        f'<div style="display:flex;justify-content:space-between;'
                        f'padding:6px 0;border-bottom:1px solid {C["border"]};">'
                        f'<span style="color:{PAIR_COLOR[pair]}">{pair}</span>'
                        f'<span class="muted mono">—</span></div>'
                    )
                    continue
                if atr < 1.0:
                    badge_cls, label = "badge-low", "LOW"
                elif atr < 2.5:
                    badge_cls, label = "badge-normal", "NORMAL"
                else:
                    badge_cls, label = "badge-high", "HIGH"
                rows.append(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'padding:8px 0;border-bottom:1px solid {C["border"]};">'
                    f'<div><div style="color:{PAIR_COLOR[pair]};font-weight:500;">{pair}</div>'
                    f'<div class="muted mono" style="font-size:11px;">ATR {atr:.2f}%</div></div>'
                    f'<span class="tag {badge_cls}">{label}</span>'
                    f'</div>'
                )
            st.markdown(
                f'<div class="card"><h4>Volatility · 1h ATR(14)</h4>{"".join(rows)}</div>',
                unsafe_allow_html=True,
            )
    except Exception:
        _empty_placeholder("Sentiment unavailable")


def render_insights():
    """AI insights — Today / Week / Month tabs in reading-pane card.

    Schema used by this bot:
      agent_insights: timestamp, pair, strategy, insight
      memory:         timestamp, type ('weekly'|'monthly'), content
    """
    st.markdown('<div class="section-title">AI Insights</div>', unsafe_allow_html=True)
    try:
        ai  = db_agent_insights(limit=200)
        mem = db_memory(limit=200)

        def _render_text(txt):
            paragraphs = [p.strip() for p in str(txt).split("\n\n") if p.strip()]
            body = "".join(
                f'<p>{p.replace(chr(10), "<br>")}</p>' for p in paragraphs
            ) or f"<p>{txt}</p>"
            st.markdown(
                f'<div class="card"><div class="reading-pane">{body}</div></div>',
                unsafe_allow_html=True,
            )

        def _empty_insight(label):
            st.markdown(
                f'<div class="card"><div class="reading-pane">'
                f'<p class="muted">No insight for {label} yet — '
                f'runs automatically at midnight UTC.</p>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

        tab1, tab2, tab3 = st.tabs(["Today", "Week", "Month"])

        # TODAY — show the most recent AI insight per pair from agent_insights
        with tab1:
            if ai.empty or "insight" not in ai.columns:
                _empty_insight("today")
            else:
                today_ai = ai.copy()
                if "timestamp" in today_ai.columns:
                    today_ai = today_ai.sort_values("timestamp", ascending=False)
                # show one card per pair (most recent insight each)
                shown = 0
                for pair in PAIRS:
                    if "pair" in today_ai.columns:
                        sub = today_ai[today_ai["pair"] == pair]
                    else:
                        sub = today_ai
                    if sub.empty:
                        continue
                    row = sub.iloc[0]
                    ts_str = ""
                    if "timestamp" in row.index and pd.notna(row["timestamp"]):
                        ts_str = str(row["timestamp"])[:16] + " UTC"
                    st.markdown(
                        f'<div style="display:flex;justify-content:space-between;'
                        f'align-items:center;margin:10px 0 4px 0;">'
                        f'<span style="color:{PAIR_COLOR.get(pair, C["text"])};'
                        f'font-weight:600;font-size:13px;">{pair}</span>'
                        f'<span class="muted" style="font-size:11px;">{ts_str}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    _render_text(row["insight"])
                    shown += 1
                if shown == 0:
                    _empty_insight("today")

        # WEEK — from memory table where type='weekly'
        with tab2:
            if mem.empty:
                _empty_insight("this week")
            else:
                weekly = mem[mem.get("type", pd.Series(dtype=str)).astype(str).str.lower().str.contains("week", na=False)] \
                    if "type" in mem.columns else pd.DataFrame()
                if weekly.empty:
                    _empty_insight("this week")
                else:
                    weekly = weekly.sort_values("timestamp", ascending=False) if "timestamp" in weekly.columns else weekly
                    _render_text(weekly.iloc[0].get("content", "No content"))

        # MONTH — from memory table where type='monthly'
        with tab3:
            if mem.empty:
                _empty_insight("this month")
            else:
                monthly = mem[mem.get("type", pd.Series(dtype=str)).astype(str).str.lower().str.contains("month", na=False)] \
                    if "type" in mem.columns else pd.DataFrame()
                if monthly.empty:
                    _empty_insight("this month")
                else:
                    monthly = monthly.sort_values("timestamp", ascending=False) if "timestamp" in monthly.columns else monthly
                    _render_text(monthly.iloc[0].get("content", "No content"))

    except Exception:
        _empty_placeholder("Insights unavailable")


def render_footer():
    try:
        col_l, col_r = st.columns([5, 1])
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        with col_l:
            st.markdown(
                f'<div class="muted" style="margin-top:14px;">'
                f'Paper trading · Alpaca · Auto-refresh 30s · {ts}'
                f'</div>',
                unsafe_allow_html=True,
            )
        with col_r:
            if st.button("Refresh now", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
    except Exception:
        pass


# =============================================================================
# MAIN
# =============================================================================

def main():
    # Auto-refresh — wired so cached calls (positions/account at ttl=60) re-fetch,
    # while ttl=300 sources stay cached as the spec requires.
    if _AUTOREFRESH:
        try:
            st_autorefresh(interval=30_000, key="dashboard_autorefresh")
        except Exception:
            pass

    render_header()
    render_portfolio_strip()
    render_equity_curve()
    render_positions()
    render_strategy_matrix()
    render_price_charts()
    render_activity()
    render_sentiment()
    render_insights()
    render_footer()


if __name__ == "__main__":
    main()
