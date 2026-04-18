import json
from google import genai as google_genai
from groq import Groq
from config import GEMINI_API_KEY, GROQ_API_KEY


def ask_gemini(prompt: str) -> str:
    client = google_genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    return response.text


def ask_groq(prompt: str) -> str:
    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
    return response.choices[0].message.content


def ask_brain(prompt: str) -> str:
    try:
        return ask_gemini(prompt)
    except Exception:
        return ask_groq(prompt)


def analyze_backtest(pair: str, results: dict, history: list = None, trades: list = None, memory: str = None) -> str:
    memory_text = f"\n\nLONG-TERM MEMORY (confirmed rules & patterns):\n{memory}" if memory else ""
    history_text = ""
    if history:
        history_text = "\n\nPREVIOUS INSIGHTS (last 5 days):\n"
        for h in history[-5:]:
            history_text += f"- [{h['timestamp'][:10]}]: {h['insight'][:300]}\n"

    trades_text = ""
    if trades:
        trades_text = "\n\nCOMPLETED TRADES:\n"
        for t in trades:
            trades_text += f"- {t['entry_time'][:10]} BUY @ ${t['entry_price']:,.2f} → SELL @ ${t['exit_price']:,.2f} = {t['pnl_pct']:+.2f}% ({t['result']})\n"

    prompt = f"""You are a quantitative crypto trading AI with long-term memory. Be specific, data-driven, cite exact numbers. Never make vague statements. If data is insufficient, say so explicitly.

PAIR: {pair}
TODAY'S BACKTEST RESULTS (30 days of hourly data):
{json.dumps(results, indent=2)}
{memory_text}

METRICS GUIDE:
- trades: number of completed trades (below 5 = unreliable)
- win_rate: % profitable trades (>55% is good)
- avg_pnl: average profit/loss per trade (%)
- total_return: cumulative return (%)
- sharpe: risk-adjusted return (>1 good, >2 excellent, <0 avoid)
- sortino: downside-only risk (higher = better)
- max_drawdown: worst peak-to-trough loss (lower = safer)
{history_text}{trades_text}

Answer these EXACTLY with numbers:
1. BEST STRATEGY TODAY: Name it, state its exact sharpe/win_rate/total_return, explain WHY these numbers make it best vs others.
2. WORST STRATEGY TODAY: Name it, state what's bad about its exact numbers.
3. PATTERN vs YESTERDAY: If previous insights exist, what changed? Is the best strategy consistent or did it flip? What does that tell us about market conditions?
4. MARKET CONDITION: Based on which strategy types are winning (trend-following vs mean-reversion), what is the market doing right now? Be specific.
5. WHAT TO WATCH: One specific price level or indicator value to watch for {pair} next 24hrs.

Keep each point to 2-3 sentences max. No fluff."""

    return ask_brain(prompt)
