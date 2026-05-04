import asyncio
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import matplotlib.pyplot as plt
import pandas as pd
import requests
import streamlit as st
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
# Core functions (unchanged from notebook)
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
            st.warning(f"Telegram flood wait for {channel_ref}: {exc.seconds}s. Skipping.")
        except (ChannelPrivateError, UsernameInvalidError, UsernameNotOccupiedError) as exc:
            st.warning(f"Cannot access {original_ref}: {type(exc).__name__}")
        except Exception as exc:
            st.warning(f"Telegram error for {original_ref}: {exc}")

    await client.disconnect()

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates(subset=["link", "snippet"]).reset_index(drop=True)
    return df


def run_telegram_fetch(channels, search_terms, recent_limit, search_limit) -> pd.DataFrame:
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                _fetch_telegram_async(channels, search_terms, recent_limit, search_limit)
            )
        finally:
            loop.close()

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run)
        return future.result()


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Finance Lead Discovery — BG/EU", layout="wide")
st.title("Finance Lead Discovery — BG/EU")

# --- Sidebar ---
with st.sidebar:
    st.header("Configuration")

    # API key status
    st.subheader("API Keys")
    serper_ok = bool(SERPER_API_KEY)
    st.markdown(f"{'🟢' if serper_ok else '🔴'} **Serper** {'loaded' if serper_ok else 'missing — add to .env'}")
    tg_ok = bool(TELEGRAM_API_ID and TELEGRAM_API_HASH)
    st.markdown(f"{'🟢' if tg_ok else '🔴'} **Telegram** {'loaded' if tg_ok else 'optional — add to .env'}")

    st.divider()

    # Filters
    with st.expander("Filters", expanded=True):
        min_score = st.slider("Min commercial score", 0, 70, 20)
        include_high_risk = st.checkbox("Include high-risk leads", value=False)
        target_platforms = st.multiselect(
            "Platforms",
            ["facebook", "instagram", "tiktok", "telegram", "other"],
            default=["facebook", "instagram", "tiktok", "telegram"],
        )
        target_use_cases = st.multiselect(
            "Use cases",
            ["forex_educator", "signal_provider", "introducing_broker", "money_manager", "mirror_trading"],
            default=["forex_educator", "signal_provider", "introducing_broker", "money_manager", "mirror_trading"],
        )
        target_assets = st.multiselect(
            "Assets",
            ["forex", "gold", "stocks", "indices", "crypto_optional"],
            default=["forex", "gold", "stocks"],
        )
        max_results_per_query = st.number_input("Results per query", min_value=1, max_value=10, value=10)
        delay = st.number_input("Delay between queries (s)", min_value=0.5, max_value=5.0, value=1.2, step=0.1)

    # Telegram
    with st.expander("Telegram (optional)", expanded=False):
        enable_telegram = st.checkbox("Enable Telegram fetch", value=False, disabled=not tg_ok)
        if not tg_ok:
            st.caption("Set TELEGRAM_API_ID, TELEGRAM_API_HASH in .env to enable.")
        channels_input = st.text_area(
            "Channel usernames (one per line)",
            placeholder="@example_channel\nhttps://t.me/example",
            height=100,
        )
        recent_limit = st.number_input("Recent messages per channel", min_value=10, max_value=500, value=100)
        search_limit = st.number_input("Search results per term", min_value=5, max_value=100, value=30)

# --- Run button ---
run_clicked = st.button("▶ Run Discovery", type="primary", disabled=not serper_ok)

if not serper_ok:
    st.info("Add your `SERPER_API_KEY` to the `.env` file and restart the app to run discovery.")

# --- Discovery pipeline ---
if run_clicked:
    all_rows = []

    with st.status("Running Serper search...", expanded=True) as status:
        active_queries = [
            e for e in QUERIES
            if query_matches_filters(e, target_platforms, target_use_cases, target_assets)
        ]
        st.write(f"Running {len(active_queries)} / {len(QUERIES)} queries matching your filters.")
        progress = st.progress(0)
        total = len(active_queries)

        for i, entry in enumerate(active_queries):
            query = entry["q"]
            st.write(f"Querying: `{query}`")
            try:
                rows = serper_search(query, num=int(max_results_per_query))
                all_rows.extend(rows)
                time.sleep(delay)
            except Exception as exc:
                st.warning(f"Query failed: {query} — {exc}")
            progress.progress((i + 1) / total if total else 1)

        raw_results = pd.DataFrame(all_rows)
        if not raw_results.empty:
            raw_results = raw_results.drop_duplicates(subset=["link"]).reset_index(drop=True)

        st.write(f"Search complete — {len(raw_results)} unique results.")

        # Telegram
        if enable_telegram and tg_ok:
            channels = [c.strip() for c in channels_input.splitlines() if c.strip()]
            if channels:
                st.write(f"Fetching Telegram ({len(channels)} channels)...")
                try:
                    tg_df = run_telegram_fetch(channels, TELEGRAM_SEARCH_TERMS, int(recent_limit), int(search_limit))
                    st.write(f"Telegram: {len(tg_df)} rows fetched.")
                    if not tg_df.empty:
                        raw_results = pd.concat([raw_results, tg_df], ignore_index=True)
                        raw_results = raw_results.drop_duplicates(subset=["link", "snippet"]).reset_index(drop=True)
                except Exception as exc:
                    st.error(f"Telegram fetch failed: {exc}")
            else:
                st.write("No Telegram channels entered.")

        st.write("Scoring results...")
        ranked = apply_scoring(raw_results) if not raw_results.empty else pd.DataFrame()
        filtered = filter_ranked_results(
            ranked, target_platforms, include_high_risk, min_score, target_use_cases, target_assets
        ) if not ranked.empty else pd.DataFrame()

        status.update(label="Done!", state="complete")

    st.session_state["ranked"] = ranked
    st.session_state["filtered"] = filtered
    st.session_state["raw"] = raw_results

# --- Results ---
if "filtered" in st.session_state and not st.session_state["filtered"].empty:
    ranked = st.session_state["ranked"]
    filtered = st.session_state["filtered"]

    st.caption(f"{len(filtered)} filtered leads · {len(ranked)} total scored")

    tab_leads, tab_stats, tab_telegram = st.tabs(["Leads", "Stats", "Telegram"])

    display_cols = [
        "lead_quality", "commercial_fit_score", "compliance_risk",
        "primary_use_case", "recommended_action", "platform",
        "title", "snippet", "link", "score_reasons",
    ]

    with tab_leads:
        show_cols = [c for c in display_cols if c in filtered.columns]
        st.dataframe(
            filtered[show_cols],
            use_container_width=True,
            hide_index=True,
            column_config={"link": st.column_config.LinkColumn("link")},
        )

    with tab_stats:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Use case distribution")
            if "primary_use_case" in ranked.columns:
                vc = ranked["primary_use_case"].value_counts().reset_index()
                vc.columns = ["use_case", "count"]
                st.bar_chart(vc.set_index("use_case"))
        with col2:
            st.subheader("Platform distribution")
            if "platform" in ranked.columns:
                pc = ranked["platform"].value_counts().reset_index()
                pc.columns = ["platform", "count"]
                st.bar_chart(pc.set_index("platform"))

        if "platform" in ranked.columns and "lead_quality" in ranked.columns:
            st.subheader("Lead quality by platform")
            crosstab = pd.crosstab(ranked["platform"], ranked["lead_quality"])
            fig, ax = plt.subplots(figsize=(9, 4))
            crosstab.plot(kind="bar", stacked=True, ax=ax)
            ax.set_xlabel("Platform")
            ax.set_ylabel("Count")
            ax.legend(title="Lead Quality")
            plt.tight_layout()
            st.pyplot(fig)

    with tab_telegram:
        tg_leads = ranked[ranked["platform"] == "telegram"].copy() if "platform" in ranked.columns else pd.DataFrame()
        if tg_leads.empty:
            st.info("No Telegram leads found in this run.")
        else:
            tg_cols = [c for c in ["lead_quality", "commercial_fit_score", "primary_use_case", "title", "link"] if c in tg_leads.columns]
            st.dataframe(
                tg_leads[tg_cols],
                use_container_width=True,
                hide_index=True,
                column_config={"link": st.column_config.LinkColumn("link")},
            )

    # --- Downloads ---
    st.divider()
    st.subheader("Export")

    FINAL_COLS = [
        "lead_score", "lead_quality", "commercial_fit_score", "compliance_risk",
        "recommended_action", "primary_use_case", "finance_use_cases", "asset_interest",
        "region_hits", "review_status", "platform", "title", "snippet",
        "manual_visible_text", "matched_terms", "score_reasons", "risk_reasons",
        "link", "source_query", "notes",
    ]

    exp_col1, exp_col2 = st.columns(2)
    with exp_col1:
        st.caption("**Lead quality**")
        exp_quality_options = ["low", "medium", "high", "very_high"]
        exp_quality_selected = [
            q for q in exp_quality_options
            if st.checkbox(q, value=(q in ["high", "very_high"]), key=f"exp_q_{q}")
        ]
    with exp_col2:
        st.caption("**Platforms**")
        exp_platform_options = ["facebook", "instagram", "tiktok", "telegram", "other"]
        exp_platforms_selected = [
            p for p in exp_platform_options
            if st.checkbox(p, value=True, key=f"exp_p_{p}")
        ]

    export_df = filtered.copy()
    if exp_quality_selected:
        export_df = export_df[export_df["lead_quality"].astype(str).isin(exp_quality_selected)]
    if exp_platforms_selected:
        export_df = export_df[export_df["platform"].isin(exp_platforms_selected)]

    export_df["possible_handle_or_page"] = export_df["link"].apply(extract_possible_handle)
    export_df["action_status"] = "research_more"
    export_df = ensure_columns(export_df, FINAL_COLS)
    final_cols_present = ["possible_handle_or_page", "action_status"] + [c for c in FINAL_COLS if c in export_df.columns]
    export_df = export_df[final_cols_present].sort_values("commercial_fit_score", ascending=False)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    st.download_button(
        label=f"Download filtered leads ({len(export_df)} rows)",
        data=export_df.to_csv(index=False, encoding="utf-8-sig"),
        file_name=f"finance_bg_eu_leads_{timestamp}.csv",
        mime="text/csv",
        disabled=export_df.empty,
    )

elif "filtered" in st.session_state and st.session_state["filtered"].empty:
    st.warning("No leads matched the current filters. Try lowering the min score or broadening platform/use-case filters.")
