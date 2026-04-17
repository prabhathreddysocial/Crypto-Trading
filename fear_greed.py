import requests


def get_fear_greed() -> dict:
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        data = r.json()["data"][0]
        return {"value": int(data["value"]), "label": data["value_classification"]}
    except Exception:
        return {"value": 50, "label": "Unknown"}


def is_safe_to_buy(threshold=80) -> bool:
    fg = get_fear_greed()
    print(f"  Fear & Greed: {fg['value']} ({fg['label']})")
    return fg["value"] < threshold
