import asyncio
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
TELEGRAM_API_ID_RAW = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE")
TELEGRAM_API_ID = int(TELEGRAM_API_ID_RAW) if TELEGRAM_API_ID_RAW else None

TELEGRAM_SESSION_NAME = "telegram_lead_discovery_session"

# Each entry: q=query string, assets=asset tags, use_cases=use-case tags, platforms=platform tags.
# Empty list means "general / applies to any selection" for that dimension.
QUERIES = [
    # --- General market presence ---
    {"q": 'site:facebook.com "forex trading"',                    "assets": ["forex"],    "use_cases": [],                     "platforms": ["facebook"]},
    {"q": 'site:facebook.com "gold trading"',                     "assets": ["gold"],     "use_cases": [],                     "platforms": ["facebook"]},
    {"q": 'site:facebook.com "XAUUSD"',                           "assets": ["gold"],     "use_cases": [],                     "platforms": ["facebook"]},
    {"q": 'site:facebook.com "stocks investing"',                 "assets": ["stocks"],   "use_cases": [],                     "platforms": ["facebook"]},
    {"q": 'site:facebook.com "stock market"',                     "assets": ["stocks"],   "use_cases": [],                     "platforms": ["facebook"]},
    {"q": 'site:facebook.com "NAS100 trading"',                   "assets": ["indices"],  "use_cases": [],                     "platforms": ["facebook"]},
    {"q": 'site:facebook.com "US30 trading"',                     "assets": ["indices"],  "use_cases": [],                     "platforms": ["facebook"]},
    {"q": 'site:instagram.com "forex trader"',                    "assets": ["forex"],    "use_cases": [],                     "platforms": ["instagram"]},
    {"q": 'site:instagram.com "gold trader"',                     "assets": ["gold"],     "use_cases": [],                     "platforms": ["instagram"]},
    {"q": 'site:instagram.com "XAUUSD"',                          "assets": ["gold"],     "use_cases": [],                     "platforms": ["instagram"]},
    {"q": 'site:instagram.com "stock trader"',                    "assets": ["stocks"],   "use_cases": [],                     "platforms": ["instagram"]},
    {"q": 'site:instagram.com "indices trading"',                 "assets": ["indices"],  "use_cases": [],                     "platforms": ["instagram"]},
    {"q": 'site:tiktok.com "forex trader"',                       "assets": ["forex"],    "use_cases": [],                     "platforms": ["tiktok"]},
    {"q": 'site:tiktok.com "gold trading"',                       "assets": ["gold"],     "use_cases": [],                     "platforms": ["tiktok"]},
    {"q": 'site:tiktok.com "XAUUSD"',                             "assets": ["gold"],     "use_cases": [],                     "platforms": ["tiktok"]},
    {"q": 'site:tiktok.com "stock trading"',                      "assets": ["stocks"],   "use_cases": [],                     "platforms": ["tiktok"]},
    {"q": 'site:tiktok.com "NAS100"',                             "assets": ["indices"],  "use_cases": [],                     "platforms": ["tiktok"]},
    {"q": 'site:t.me "forex trading"',                            "assets": ["forex"],    "use_cases": [],                     "platforms": ["telegram"]},
    {"q": 'site:t.me "gold trading"',                             "assets": ["gold"],     "use_cases": [],                     "platforms": ["telegram"]},
    {"q": 'site:t.me "XAUUSD"',                                   "assets": ["gold"],     "use_cases": [],                     "platforms": ["telegram"]},
    {"q": 'site:t.me "stock market"',                             "assets": ["stocks"],   "use_cases": [],                     "platforms": ["telegram"]},
    {"q": 'site:t.me "NAS100"',                                   "assets": ["indices"],  "use_cases": [],                     "platforms": ["telegram"]},
    {"q": 'site:t.me "US30"',                                     "assets": ["indices"],  "use_cases": [],                     "platforms": ["telegram"]},
    # --- Signal providers ---
    {"q": 'site:facebook.com "forex signals"',                    "assets": ["forex"],    "use_cases": ["signal_provider"],    "platforms": ["facebook"]},
    {"q": 'site:facebook.com "gold signals"',                     "assets": ["gold"],     "use_cases": ["signal_provider"],    "platforms": ["facebook"]},
    {"q": 'site:facebook.com "XAUUSD signals"',                   "assets": ["gold"],     "use_cases": ["signal_provider"],    "platforms": ["facebook"]},
    {"q": 'site:facebook.com "buy sell signals"',                 "assets": [],           "use_cases": ["signal_provider"],    "platforms": ["facebook"]},
    {"q": 'site:facebook.com "free forex signals"',               "assets": ["forex"],    "use_cases": ["signal_provider"],    "platforms": ["facebook"]},
    {"q": 'site:instagram.com "forex signals"',                   "assets": ["forex"],    "use_cases": ["signal_provider"],    "platforms": ["instagram"]},
    {"q": 'site:instagram.com "gold signals"',                    "assets": ["gold"],     "use_cases": ["signal_provider"],    "platforms": ["instagram"]},
    {"q": 'site:instagram.com "XAUUSD signals"',                  "assets": ["gold"],     "use_cases": ["signal_provider"],    "platforms": ["instagram"]},
    {"q": 'site:instagram.com "trading signals"',                 "assets": [],           "use_cases": ["signal_provider"],    "platforms": ["instagram"]},
    {"q": 'site:tiktok.com "forex signals"',                      "assets": ["forex"],    "use_cases": ["signal_provider"],    "platforms": ["tiktok"]},
    {"q": 'site:tiktok.com "gold signals"',                       "assets": ["gold"],     "use_cases": ["signal_provider"],    "platforms": ["tiktok"]},
    {"q": 'site:tiktok.com "trading signals"',                    "assets": [],           "use_cases": ["signal_provider"],    "platforms": ["tiktok"]},
    {"q": 'site:t.me "forex signals"',                            "assets": ["forex"],    "use_cases": ["signal_provider"],    "platforms": ["telegram"]},
    {"q": 'site:t.me "gold signals"',                             "assets": ["gold"],     "use_cases": ["signal_provider"],    "platforms": ["telegram"]},
    {"q": 'site:t.me "XAUUSD signals"',                           "assets": ["gold"],     "use_cases": ["signal_provider"],    "platforms": ["telegram"]},
    {"q": 'site:t.me "premium signals"',                          "assets": [],           "use_cases": ["signal_provider"],    "platforms": ["telegram"]},
    {"q": 'site:t.me "free signals"',                             "assets": [],           "use_cases": ["signal_provider"],    "platforms": ["telegram"]},
    {"q": 'site:t.me "buy sell signal"',                          "assets": [],           "use_cases": ["signal_provider"],    "platforms": ["telegram"]},
    {"q": 'site:t.me "VIP signals"',                              "assets": [],           "use_cases": ["signal_provider"],    "platforms": ["telegram"]},
    {"q": 'site:t.me "indices signals"',                          "assets": ["indices"],  "use_cases": ["signal_provider"],    "platforms": ["telegram"]},
    # --- Forex educators ---
    {"q": 'site:facebook.com "learn forex"',                      "assets": ["forex"],    "use_cases": ["forex_educator"],     "platforms": ["facebook"]},
    {"q": 'site:facebook.com "forex course"',                     "assets": ["forex"],    "use_cases": ["forex_educator"],     "platforms": ["facebook"]},
    {"q": 'site:facebook.com "trading course"',                   "assets": [],           "use_cases": ["forex_educator"],     "platforms": ["facebook"]},
    {"q": 'site:facebook.com "forex mentorship"',                 "assets": ["forex"],    "use_cases": ["forex_educator"],     "platforms": ["facebook"]},
    {"q": 'site:facebook.com "forex masterclass"',                "assets": ["forex"],    "use_cases": ["forex_educator"],     "platforms": ["facebook"]},
    {"q": 'site:facebook.com "trading academy"',                  "assets": [],           "use_cases": ["forex_educator"],     "platforms": ["facebook"]},
    {"q": 'site:instagram.com "learn trading"',                   "assets": [],           "use_cases": ["forex_educator"],     "platforms": ["instagram"]},
    {"q": 'site:instagram.com "forex education"',                 "assets": ["forex"],    "use_cases": ["forex_educator"],     "platforms": ["instagram"]},
    {"q": 'site:instagram.com "trading mentor"',                  "assets": [],           "use_cases": ["forex_educator"],     "platforms": ["instagram"]},
    {"q": 'site:instagram.com "forex coach"',                     "assets": ["forex"],    "use_cases": ["forex_educator"],     "platforms": ["instagram"]},
    {"q": 'site:tiktok.com "how to trade forex"',                 "assets": ["forex"],    "use_cases": ["forex_educator"],     "platforms": ["tiktok"]},
    {"q": 'site:tiktok.com "forex for beginners"',                "assets": ["forex"],    "use_cases": ["forex_educator"],     "platforms": ["tiktok"]},
    {"q": 'site:tiktok.com "trading education"',                  "assets": [],           "use_cases": ["forex_educator"],     "platforms": ["tiktok"]},
    {"q": 'site:tiktok.com "learn to trade"',                     "assets": [],           "use_cases": ["forex_educator"],     "platforms": ["tiktok"]},
    {"q": 'site:t.me "forex course"',                             "assets": ["forex"],    "use_cases": ["forex_educator"],     "platforms": ["telegram"]},
    {"q": 'site:t.me "trading education"',                        "assets": [],           "use_cases": ["forex_educator"],     "platforms": ["telegram"]},
    {"q": 'site:t.me "forex mentorship"',                         "assets": ["forex"],    "use_cases": ["forex_educator"],     "platforms": ["telegram"]},
    {"q": 'site:t.me "learn to trade"',                           "assets": [],           "use_cases": ["forex_educator"],     "platforms": ["telegram"]},
    {"q": 'site:t.me "trading academy"',                          "assets": [],           "use_cases": ["forex_educator"],     "platforms": ["telegram"]},
    # --- Introducing brokers ---
    {"q": 'site:facebook.com "best forex broker"',                "assets": ["forex"],    "use_cases": ["introducing_broker"], "platforms": ["facebook"]},
    {"q": 'site:facebook.com "regulated broker"',                 "assets": [],           "use_cases": ["introducing_broker"], "platforms": ["facebook"]},
    {"q": 'site:facebook.com "forex broker review"',              "assets": ["forex"],    "use_cases": ["introducing_broker"], "platforms": ["facebook"]},
    {"q": 'site:facebook.com "ECN broker"',                       "assets": [],           "use_cases": ["introducing_broker"], "platforms": ["facebook"]},
    {"q": 'site:facebook.com "lowest spread broker"',             "assets": [],           "use_cases": ["introducing_broker"], "platforms": ["facebook"]},
    {"q": 'site:instagram.com "best forex broker"',               "assets": ["forex"],    "use_cases": ["introducing_broker"], "platforms": ["instagram"]},
    {"q": 'site:instagram.com "forex broker"',                    "assets": ["forex"],    "use_cases": ["introducing_broker"], "platforms": ["instagram"]},
    {"q": 'site:instagram.com "trading platform"',                "assets": [],           "use_cases": ["introducing_broker"], "platforms": ["instagram"]},
    {"q": 'site:tiktok.com "best forex broker"',                  "assets": ["forex"],    "use_cases": ["introducing_broker"], "platforms": ["tiktok"]},
    {"q": 'site:tiktok.com "broker review"',                      "assets": [],           "use_cases": ["introducing_broker"], "platforms": ["tiktok"]},
    {"q": 'site:tiktok.com "forex broker"',                       "assets": ["forex"],    "use_cases": ["introducing_broker"], "platforms": ["tiktok"]},
    {"q": 'site:t.me "forex broker"',                             "assets": ["forex"],    "use_cases": ["introducing_broker"], "platforms": ["telegram"]},
    {"q": 'site:t.me "regulated broker"',                         "assets": [],           "use_cases": ["introducing_broker"], "platforms": ["telegram"]},
    {"q": 'site:t.me "low spread broker"',                        "assets": [],           "use_cases": ["introducing_broker"], "platforms": ["telegram"]},
    {"q": 'site:t.me "best broker"',                              "assets": [],           "use_cases": ["introducing_broker"], "platforms": ["telegram"]},
    {"q": 'site:t.me "ECN broker"',                               "assets": [],           "use_cases": ["introducing_broker"], "platforms": ["telegram"]},
    # --- Mirror / copy trading ---
    {"q": 'site:facebook.com "copy trading"',                     "assets": [],           "use_cases": ["mirror_trading"],     "platforms": ["facebook"]},
    {"q": 'site:facebook.com "social trading"',                   "assets": [],           "use_cases": ["mirror_trading"],     "platforms": ["facebook"]},
    {"q": 'site:facebook.com "mirror trading"',                   "assets": [],           "use_cases": ["mirror_trading"],     "platforms": ["facebook"]},
    {"q": 'site:facebook.com "follow trader"',                    "assets": [],           "use_cases": ["mirror_trading"],     "platforms": ["facebook"]},
    {"q": 'site:instagram.com "copy trading"',                    "assets": [],           "use_cases": ["mirror_trading"],     "platforms": ["instagram"]},
    {"q": 'site:instagram.com "follow trader"',                   "assets": [],           "use_cases": ["mirror_trading"],     "platforms": ["instagram"]},
    {"q": 'site:instagram.com "social trading"',                  "assets": [],           "use_cases": ["mirror_trading"],     "platforms": ["instagram"]},
    {"q": 'site:tiktok.com "copy trading"',                       "assets": [],           "use_cases": ["mirror_trading"],     "platforms": ["tiktok"]},
    {"q": 'site:tiktok.com "copy trading forex"',                 "assets": ["forex"],    "use_cases": ["mirror_trading"],     "platforms": ["tiktok"]},
    {"q": 'site:t.me "copy trading"',                             "assets": [],           "use_cases": ["mirror_trading"],     "platforms": ["telegram"]},
    {"q": 'site:t.me "mirror trading"',                           "assets": [],           "use_cases": ["mirror_trading"],     "platforms": ["telegram"]},
    {"q": 'site:t.me "social trading"',                           "assets": [],           "use_cases": ["mirror_trading"],     "platforms": ["telegram"]},
    {"q": 'site:t.me "auto copy"',                                "assets": [],           "use_cases": ["mirror_trading"],     "platforms": ["telegram"]},
    {"q": 'site:t.me "copy trades"',                              "assets": [],           "use_cases": ["mirror_trading"],     "platforms": ["telegram"]},
    # --- Money managers ---
    {"q": 'site:facebook.com "managed forex account"',            "assets": ["forex"],    "use_cases": ["money_manager"],      "platforms": ["facebook"]},
    {"q": 'site:facebook.com "PAMM account"',                     "assets": [],           "use_cases": ["money_manager"],      "platforms": ["facebook"]},
    {"q": 'site:facebook.com "trade for me"',                     "assets": [],           "use_cases": ["money_manager"],      "platforms": ["facebook"]},
    {"q": 'site:facebook.com "manage my account"',                "assets": [],           "use_cases": ["money_manager"],      "platforms": ["facebook"]},
    {"q": 'site:instagram.com "managed trading"',                 "assets": [],           "use_cases": ["money_manager"],      "platforms": ["instagram"]},
    {"q": 'site:instagram.com "forex investment"',                "assets": ["forex"],    "use_cases": ["money_manager"],      "platforms": ["instagram"]},
    {"q": 'site:instagram.com "trade for me"',                    "assets": [],           "use_cases": ["money_manager"],      "platforms": ["instagram"]},
    {"q": 'site:tiktok.com "trade for me"',                       "assets": [],           "use_cases": ["money_manager"],      "platforms": ["tiktok"]},
    {"q": 'site:tiktok.com "managed forex"',                      "assets": ["forex"],    "use_cases": ["money_manager"],      "platforms": ["tiktok"]},
    {"q": 'site:t.me "account manager forex"',                    "assets": ["forex"],    "use_cases": ["money_manager"],      "platforms": ["telegram"]},
    {"q": 'site:t.me "PAMM"',                                     "assets": [],           "use_cases": ["money_manager"],      "platforms": ["telegram"]},
    {"q": 'site:t.me "MAM account"',                              "assets": [],           "use_cases": ["money_manager"],      "platforms": ["telegram"]},
    {"q": 'site:t.me "managed account"',                          "assets": [],           "use_cases": ["money_manager"],      "platforms": ["telegram"]},
    {"q": 'site:t.me "profit sharing"',                           "assets": [],           "use_cases": ["money_manager"],      "platforms": ["telegram"]},
]

TELEGRAM_SEARCH_TERMS = [
    "forex trading", "gold trading", "XAUUSD", "EURUSD", "stock market",
    "NAS100", "US30", "DAX", "indices trading",
    "TradingView", "MT4", "MT5",
    "forex signals", "gold signals", "XAUUSD signals", "premium signals",
    "free signals", "VIP signals", "buy sell signal", "entry stop loss take profit",
    "learn forex", "forex course", "trading education", "forex mentorship",
    "technical analysis", "price action", "risk management", "beginner trader",
    "trading academy", "forex coach", "learn to trade",
    "best forex broker", "regulated broker", "low spread broker", "ECN broker",
    "forex broker review", "trading platform",
    "copy trading", "mirror trading", "social trading", "auto copy", "copy trades",
    "follow trader",
    "PAMM", "MAM account", "managed account", "managed forex", "trade for me",
    "account manager", "profit sharing",
]

# ---------------------------------------------------------------------------
# Term dictionaries
# ---------------------------------------------------------------------------

REGION_TERMS = [
    "bulgaria", "bulgarian", "sofia", "varna", "plovdiv", "europe", "eu",
    "българия", "български", "софия", "варна", "пловдив", "европа", "ес",
]

ASSET_TERMS = {
    "forex": ["forex", "fx", "eurusd", "gbpusd", "usdjpy", "forex market", "форекс", "валутна търговия"],
    "gold": ["gold", "xauusd", "gold trading", "злато", "търговия със злато"],
    "stocks": ["stocks", "stock market", "shares", "equities", "nasdaq", "s&p 500", "sp500", "акции", "фондов пазар", "инвестиции"],
    "indices": ["nas100", "us30", "dow", "dax", "indices", "индекси"],
    "crypto_optional": ["crypto", "bitcoin", "btc", "ethereum", "eth", "крипто"],
}

SIGNAL_PROVIDER_TERMS = [
    "signals", "forex signals", "gold signals", "xauusd signals",
    "buy signal", "sell signal", "entry", "stop loss", "take profit", "tp", "sl",
    "premium signals", "free signals", "telegram signals",
    "сигнали", "форекс сигнали", "сигнали за злато",
]

FOREX_EDUCATOR_TERMS = [
    "learn forex", "forex course", "trading course", "trading education",
    "beginner trader", "how to trade", "technical analysis", "price action",
    "risk management", "candlestick", "backtesting", "tradingview", "mt4", "mt5",
    "обучение", "обучение форекс", "курс форекс", "технически анализ",
]

IB_BROKER_TERMS = [
    "broker", "forex broker", "best broker", "regulated broker", "low spread",
    "ecn broker", "deposit", "withdrawal", "leverage", "account type",
    "rebate", "ib", "introducing broker", "affiliate broker",
    "брокер", "форекс брокер", "регулиран брокер", "лост", "депозит", "теглене",
]

MONEY_MANAGER_TERMS = [
    "managed account", "account manager", "manage my account", "trade for me",
    "portfolio manager", "profit share", "pamm", "mam account",
    "управление на средства", "управление на акаунт",
]

MIRROR_TRADING_TERMS = [
    "copy trading", "mirror trading", "social trading", "copy trader",
    "auto copy", "follow trader", "copy trades",
    "копиране на сделки", "копи трейдинг",
]

VULNERABLE_RISK_TERMS = [
    "lost money", "lost everything", "in debt", "need money fast",
    "guaranteed profit", "guaranteed income", "recover losses",
    "passive income guaranteed", "no risk",
    "загубих пари", "дълг", "бързи пари", "гарантирана печалба", "без риск",
]

HIGH_RISK_FINANCE_TERMS = [
    "leverage", "high leverage", "cfds", "cfd", "binary options",
    "managed account", "trade for me", "copy trading", "mirror trading",
    "profit share", "pamm", "mam",
    "лост", "договори за разлика", "управление на средства", "копиране на сделки",
]

NEGATIVE_FINANCE_TERMS = [
    "job", "hiring", "vacancy", "casino", "betting", "sports betting",
    "scam warning", "exposed scam",
    "работа", "обява за работа", "казино", "залагания",
]

STRONG_INTENT_TERMS = [
    "learn forex", "forex course", "trading education", "beginner trader",
    "best broker", "regulated broker", "forex signals", "gold signals",
    "copy trading", "managed account", "trade for me",
    "обучение форекс", "регулиран брокер", "форекс сигнали",
]

USE_CASE_WEIGHTS = {
    "forex_educator": 25,
    "signal_provider": 18,
    "introducing_broker": 15,
    "mirror_trading": 8,
    "money_manager": 5,
}

# ---------------------------------------------------------------------------
# Query filtering
# ---------------------------------------------------------------------------

def query_matches_filters(
    entry: Dict,
    target_platforms: List[str],
    target_use_cases: List[str],
    target_assets: List[str],
) -> bool:
    if target_platforms and entry["platforms"] and not set(entry["platforms"]).intersection(target_platforms):
        return False
    if target_assets and entry["assets"] and not set(entry["assets"]).intersection(target_assets):
        return False
    if target_use_cases and entry["use_cases"] and not set(entry["use_cases"]).intersection(target_use_cases):
        return False
    return True

# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def detect_platform(url: str) -> str:
    url = (url or "").lower()
    if "facebook.com" in url or "fb.watch" in url:
        return "facebook"
    if "instagram.com" in url:
        return "instagram"
    if "tiktok.com" in url:
        return "tiktok"
    if "t.me/" in url or "telegram.me/" in url:
        return "telegram"
    return "other"


def make_result_row(
    source_query: str,
    title: str,
    snippet: str,
    link: str,
    display_link: str = "",
    provider: str = "",
    extra: Optional[Dict] = None,
) -> Dict:
    row = {
        "provider": provider,
        "source_query": source_query,
        "title": title or "",
        "snippet": snippet or "",
        "link": link or "",
        "display_link": display_link or "",
        "platform": detect_platform(link or ""),
        "manual_visible_text": "",
        "review_status": "not_reviewed",
        "notes": "",
    }
    if extra:
        row.update(extra)
    return row


def serper_search(query: str, num: int = 10) -> List[Dict]:
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    payload = {"q": query, "num": num}
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    data = response.json()
    if response.status_code >= 400:
        raise RuntimeError(f"Serper API error: {data}")
    rows = []
    for item in data.get("organic", []):
        rows.append(make_result_row(
            source_query=query,
            title=item.get("title", ""),
            snippet=item.get("snippet", ""),
            link=item.get("link", ""),
            display_link=item.get("source", ""),
            provider="serper",
        ))
    return rows


def normalize_text(text: str) -> str:
    text = str(text or "").lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"www\.\S+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_any(text: str, terms: List[str]) -> List[str]:
    t = normalize_text(text)
    return [term for term in terms if normalize_text(term) and normalize_text(term) in t]


def match_term_groups(text: str, term_groups: Dict[str, List[str]]) -> Dict[str, List[str]]:
    return {g: hits for g, hits in {g: contains_any(text, t) for g, t in term_groups.items()}.items() if hits}


def classify_finance_use_cases(text: str) -> Dict[str, List[str]]:
    candidates = {
        "signal_provider": contains_any(text, SIGNAL_PROVIDER_TERMS),
        "forex_educator": contains_any(text, FOREX_EDUCATOR_TERMS),
        "introducing_broker": contains_any(text, IB_BROKER_TERMS),
        "money_manager": contains_any(text, MONEY_MANAGER_TERMS),
        "mirror_trading": contains_any(text, MIRROR_TRADING_TERMS),
    }
    return {k: v for k, v in candidates.items() if v}


def classify_asset_interest(text: str) -> Dict[str, List[str]]:
    return match_term_groups(text, ASSET_TERMS)


def classify_finance_risk(text: str, use_cases: Optional[Dict] = None) -> Tuple[str, List[str]]:
    use_cases = use_cases or {}
    vulnerable_hits = contains_any(text, VULNERABLE_RISK_TERMS)
    high_risk_hits = contains_any(text, HIGH_RISK_FINANCE_TERMS)
    risk_reasons = []

    if vulnerable_hits:
        risk_reasons.extend([f"vulnerable-risk term: {h}" for h in vulnerable_hits])
    if high_risk_hits:
        risk_reasons.extend([f"high-risk finance term: {h}" for h in high_risk_hits])
    if "money_manager" in use_cases:
        risk_reasons.append("money manager / managed account use case detected")
    if "mirror_trading" in use_cases:
        risk_reasons.append("copy/mirror trading use case detected")

    if vulnerable_hits or "money_manager" in use_cases or "mirror_trading" in use_cases:
        return "high", risk_reasons

    if "signal_provider" in use_cases:
        risk_reasons.append("signal-related language detected")
    if "introducing_broker" in use_cases:
        risk_reasons.append("broker / introducing broker language detected")

    return ("medium", risk_reasons) if risk_reasons else ("low", [])


def choose_primary_use_case(use_cases: Dict[str, List[str]]) -> str:
    if not use_cases:
        return ""
    return max(use_cases.keys(), key=lambda n: USE_CASE_WEIGHTS.get(n, 0))


def to_csv_list(value) -> str:
    if isinstance(value, dict):
        return ", ".join(value.keys())
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value)
    return str(value or "")


def recommend_action(primary_use_case: str, compliance_risk: str, risk_reasons: List[str]) -> str:
    reasons_text = normalize_text(" ".join(risk_reasons))
    if "vulnerable-risk term" in reasons_text:
        return "not_suitable_for_outreach"
    if compliance_risk == "high":
        if primary_use_case == "money_manager":
            return "licensed_provider_only_or_exclude"
        if primary_use_case == "mirror_trading":
            return "high_risk_review_required"
        return "high_compliance_risk_review_required"
    if primary_use_case == "forex_educator" and compliance_risk == "low":
        return "education_outreach"
    if primary_use_case == "signal_provider":
        return "review_before_signal_outreach"
    if primary_use_case == "introducing_broker":
        return "broker_compliance_review_required"
    if compliance_risk == "medium":
        return "compliance_review_required"
    return "general_market_interest_review"


def score_finance_result(row: pd.Series) -> Dict:
    combined_text = " ".join([
        str(row.get("title", "")),
        str(row.get("snippet", "")),
        str(row.get("manual_visible_text", "")),
    ])

    score = 0
    reasons = []
    matched_terms = []

    region_hits = contains_any(combined_text, REGION_TERMS)
    asset_matches = classify_asset_interest(combined_text)
    use_cases = classify_finance_use_cases(combined_text)
    primary_use_case = choose_primary_use_case(use_cases)
    negative_hits = contains_any(combined_text, NEGATIVE_FINANCE_TERMS)
    strong_intent_hits = contains_any(combined_text, STRONG_INTENT_TERMS)

    if asset_matches:
        matched_assets = [a for a in asset_matches.keys() if a != "crypto_optional"]
        score += min(10, 4 * len(matched_assets))
        reasons.append(f"asset match: {', '.join(matched_assets or asset_matches.keys())}")
        for hits in asset_matches.values():
            matched_terms.extend(hits[:5])

    if use_cases:
        score += min(35, sum(USE_CASE_WEIGHTS.get(n, 0) for n in use_cases))
        reasons.append(f"use case match: {', '.join(use_cases.keys())}")
        for hits in use_cases.values():
            matched_terms.extend(hits[:5])

    if region_hits:
        score += min(10, 3 * len(region_hits))
        reasons.append(f"region match: {', '.join(region_hits[:5])}")
        matched_terms.extend(region_hits[:5])

    if strong_intent_hits:
        score += min(20, 4 * len(strong_intent_hits))
        reasons.append(f"strong intent phrase: {', '.join(strong_intent_hits[:5])}")
        matched_terms.extend(strong_intent_hits[:5])

    platform = str(row.get("platform", "")).lower()
    provider = str(row.get("provider", "")).lower()
    source_query = str(row.get("source_query", "")).lower()

    if platform in ["facebook", "instagram", "tiktok", "telegram"]:
        score += 3
        reasons.append(f"social platform: {platform}")

    if platform == "telegram" or provider.startswith("telegram") or source_query.startswith("telegram_"):
        score += 3
        reasons.append("telegram source")

    if provider in ["serper", "google"] or source_query:
        score += 5
        reasons.append("search/discovery source available")

    if negative_hits:
        penalty = min(20, 5 * len(negative_hits))
        score -= penalty
        reasons.append(f"negative/noise terms: {', '.join(negative_hits[:5])}")
        matched_terms.extend(negative_hits[:5])

    compliance_risk, risk_reasons = classify_finance_risk(combined_text, use_cases)
    recommended_action = recommend_action(primary_use_case, compliance_risk, risk_reasons)

    if not reasons:
        reasons.append("weak or irrelevant match")

    return {
        "lead_score": score,
        "commercial_fit_score": score,
        "finance_use_cases": to_csv_list(use_cases),
        "primary_use_case": primary_use_case,
        "asset_interest": to_csv_list(asset_matches),
        "region_hits": to_csv_list(region_hits),
        "matched_terms": to_csv_list(sorted(set(matched_terms))),
        "compliance_risk": compliance_risk,
        "risk_reasons": "; ".join(risk_reasons),
        "score_reasons": "; ".join(reasons),
        "recommended_action": recommended_action,
    }


def apply_scoring(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    scored = df.copy()
    score_rows = scored.apply(score_finance_result, axis=1).apply(pd.Series)
    scored = pd.concat([scored.reset_index(drop=True), score_rows.reset_index(drop=True)], axis=1)
    scored["lead_quality"] = pd.cut(
        scored["commercial_fit_score"],
        bins=[-999, 20, 45, 70, 999],
        labels=["low", "medium", "high", "very_high"],
    )
    return scored.sort_values(
        by=["commercial_fit_score", "compliance_risk", "platform"],
        ascending=[False, True, True],
    ).reset_index(drop=True)


def row_has_any_target(value: str, targets: List[str]) -> bool:
    if not targets:
        return True
    value_set = {v.strip() for v in str(value or "").split(",") if v.strip()}
    return bool(value_set.intersection(set(targets)))


def filter_ranked_results(
    df: pd.DataFrame,
    target_platforms: List[str],
    include_high_risk: bool,
    min_score: int,
    target_use_cases: List[str],
    target_assets: List[str],
) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    filtered = df.copy()
    if target_platforms:
        filtered = filtered[filtered["platform"].isin(target_platforms)]
    if not include_high_risk:
        filtered = filtered[filtered["compliance_risk"] != "high"]
    filtered = filtered[filtered["commercial_fit_score"] >= min_score]
    if target_use_cases:
        filtered = filtered[filtered["finance_use_cases"].apply(lambda x: row_has_any_target(x, target_use_cases))]
    if target_assets:
        filtered = filtered[filtered["asset_interest"].apply(lambda x: row_has_any_target(x, target_assets))]
    return filtered.reset_index(drop=True)


def extract_possible_handle(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower().replace("www.", "")
        parts = [p for p in parsed.path.split("/") if p]
        if "instagram.com" in host and parts:
            return parts[0]
        if "tiktok.com" in host and parts:
            return parts[0]
        if "t.me" in host or "telegram.me" in host:
            if parts and parts[0] == "s" and len(parts) > 1:
                return parts[1]
            if parts:
                return parts[0]
        if "facebook.com" in host and parts:
            return parts[0]
        return ""
    except Exception:
        return ""


def ensure_columns(df: pd.DataFrame, columns: List[str], default: str = "") -> pd.DataFrame:
    safe_df = df.copy()
    for col in columns:
        if col not in safe_df.columns:
            safe_df[col] = default
    return safe_df


def fetch_public_visible_text(url: str, timeout: int = 20) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 LeadResearchNotebook/1.0",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code >= 400:
            return f"[FETCH_FAILED status={response.status_code}]"
        html = response.text or ""
        login_wall_markers = ["log in to facebook", "login", "sign up", "create an account"]
        if any(m in html.lower() for m in login_wall_markers):
            return "[LOGIN_OR_SIGNUP_WALL_DETECTED]"
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript", "svg", "canvas"]):
            tag.decompose()
        text = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()
        return text[:5000]
    except Exception as exc:
        return f"[FETCH_ERROR {type(exc).__name__}: {exc}]"


# ---------------------------------------------------------------------------
# Telegram helpers
# ---------------------------------------------------------------------------

def clean_telegram_channel_ref(channel_ref: str) -> str:
    channel_ref = str(channel_ref or "").strip()
    for prefix in ["https://t.me/s/", "http://t.me/s/", "https://t.me/", "http://t.me/", "telegram.me/"]:
        channel_ref = channel_ref.replace(prefix, "")
    return channel_ref.split("?")[0].strip("/").lstrip("@")


def telegram_message_link(channel_username: str, message_id: int) -> str:
    return f"https://t.me/{channel_username}/{message_id}" if channel_username else ""


async def _fetch_telegram_async(
    channels: List[str],
    search_terms: List[str],
    recent_limit: int,
    search_limit: int,
    warn_fn: Callable[[str], None] = print,
) -> pd.DataFrame:
    from telethon import TelegramClient
    from telethon.errors import FloodWaitError, ChannelPrivateError, UsernameInvalidError, UsernameNotOccupiedError

    client = TelegramClient(TELEGRAM_SESSION_NAME, TELEGRAM_API_ID, TELEGRAM_API_HASH)
    rows = []

    await client.start(phone=TELEGRAM_PHONE)

    for original_ref in channels:
        channel_ref = clean_telegram_channel_ref(original_ref)
        try:
            entity = await client.get_entity(channel_ref)
            channel_title = getattr(entity, "title", channel_ref)
            channel_username = getattr(entity, "username", channel_ref)

            async for msg in client.iter_messages(entity, limit=recent_limit):
                text = msg.message or ""
                if not text.strip():
                    continue
                rows.append(make_result_row(
                    provider="telegram_api_recent",
                    source_query=f"telegram_recent:{channel_ref}",
                    title=channel_title,
                    snippet=text[:1000],
                    link=telegram_message_link(channel_username, msg.id),
                    display_link=f"t.me/{channel_username}" if channel_username else "telegram",
                    extra={
                        "platform": "telegram",
                        "created_time": msg.date.isoformat() if msg.date else "",
                        "telegram_channel": channel_ref,
                        "telegram_message_id": msg.id,
                    },
                ))

            for term in search_terms:
                async for msg in client.iter_messages(entity, search=term, limit=search_limit):
                    text = msg.message or ""
                    if not text.strip():
                        continue
                    rows.append(make_result_row(
                        provider="telegram_api_search",
                        source_query=f"telegram_search:{channel_ref}:{term}",
                        title=channel_title,
                        snippet=text[:1000],
                        link=telegram_message_link(channel_username, msg.id),
                        display_link=f"t.me/{channel_username}" if channel_username else "telegram",
                        extra={
                            "platform": "telegram",
                            "created_time": msg.date.isoformat() if msg.date else "",
                            "telegram_channel": channel_ref,
                            "telegram_message_id": msg.id,
                        },
                    ))
            time.sleep(0.8)

        except FloodWaitError as exc:
            warn_fn(f"Telegram flood wait for {channel_ref}: {exc.seconds}s. Skipping.")
        except (ChannelPrivateError, UsernameInvalidError, UsernameNotOccupiedError) as exc:
            warn_fn(f"Cannot access {original_ref}: {type(exc).__name__}")
        except Exception as exc:
            warn_fn(f"Telegram error for {original_ref}: {exc}")

    await client.disconnect()

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates(subset=["link", "snippet"]).reset_index(drop=True)
    return df


def run_telegram_fetch(
    channels: List[str],
    search_terms: List[str],
    recent_limit: int,
    search_limit: int,
    warn_fn: Callable[[str], None] = print,
) -> pd.DataFrame:
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                _fetch_telegram_async(channels, search_terms, recent_limit, search_limit, warn_fn)
            )
        finally:
            loop.close()

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run)
        return future.result()
