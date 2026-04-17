import os
from dotenv import load_dotenv

load_dotenv()

ALPACA_KEY = os.getenv("ALPACA_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

BASE_URL = "https://paper-api.alpaca.markets"
DATA_URL = "https://data.alpaca.markets/v1beta3/crypto/us"

PAIRS = ["BTC/USD", "ETH/USD", "SOL/USD"]
TIMEFRAME = "1Day"
LOOKBACK_DAYS = 180
