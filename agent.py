import json
import google.generativeai as genai
from groq import Groq
from config import GEMINI_API_KEY, GROQ_API_KEY


def ask_gemini(prompt: str) -> str:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
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


def analyze_backtest(pair: str, results: dict) -> str:
    prompt = f"""You are a quantitative crypto trading analyst.

Here are backtest results for {pair} over 180 days of hourly data:

{json.dumps(results, indent=2)}

Metrics explained:
- trades: number of completed trades
- win_rate: % of profitable trades
- avg_pnl: average profit/loss per trade (%)
- total_return: sum of all trade returns (%)
- sharpe: risk-adjusted return (higher is better, >1 is good)

Analyze these results and tell me:
1. Which strategy is best and why
2. Which strategies to avoid and why
3. One specific improvement to try on the best strategy
4. Overall market condition assessment based on these results

Be concise and specific. Focus on actionable insights."""

    return ask_brain(prompt)
