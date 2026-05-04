# Finance Lead Discovery

Streamlit app that discovers social media leads in the finance/forex space across global platforms. Converted from `social_lead_discovery_finance_bg_eu.ipynb`.

---

## What it does

1. Runs 107 pre-built search queries through the **Serper API** (Google search results) targeting Facebook, Instagram, TikTok, and Telegram.
2. Scores each result by **commercial fit** — use case (educator, signal provider, broker, etc.), asset interest (forex, gold, stocks, indices), and intent signals.
3. Filters by platform, risk level, use case, and minimum score — filters also control which queries run, so only relevant searches fire.
4. Displays results in a sortable table with stats charts.
5. Exports a filtered CSV with quality and platform checkboxes.

Optionally fetches messages directly from Telegram channels via the Telethon MTProto client.

---

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit UI only |
| `core.py` | All logic — queries, scoring, filtering, Telegram helpers |
| `.env` | API keys — **never commit this** |
| `requirements.txt` | Python dependencies |
| `.gitignore` | Excludes `.env`, session files, and CSV exports |

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Fill in `.env`

```
SERPER_API_KEY=your_key_here        # required — get one at serper.dev
TELEGRAM_API_ID=                    # optional — from my.telegram.org
TELEGRAM_API_HASH=                  # optional — from my.telegram.org
TELEGRAM_PHONE=                     # optional — only needed on first Telegram login
```

> **Serper key**: sign up at [serper.dev](https://serper.dev) → API Keys → copy key.
>
> **Telegram keys**: go to [my.telegram.org](https://my.telegram.org) → API development tools → create an app → copy `api_id` and `api_hash`.

### 3. Run

```bash
streamlit run app.py
```

The app opens in your browser at `http://localhost:8501`.

---

## Using the app

1. **Sidebar** shows green/red dots for each API key status.
2. Adjust filters (min score, platforms, use cases, assets) as needed.
3. Click **▶ Run Discovery** — only queries matching your selected platforms, use cases, and assets will run.
4. Results appear in three tabs:
   - **Leads** — sortable filtered table with clickable links
   - **Stats** — use case and platform charts
   - **Telegram** — Telegram-only leads subset
5. Use the **Export** checkboxes to select quality tiers and platforms, then click **Download**.

---

## Telegram: first-time login

On the first run with Telegram enabled, Telethon will send a verification code to `TELEGRAM_PHONE`. Because this is interactive, **run the auth step once from a terminal** before using the app:

```bash
python3 - <<'EOF'
import asyncio, os
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()
client = TelegramClient(
    "telegram_lead_discovery_session",
    int(os.getenv("TELEGRAM_API_ID")),
    os.getenv("TELEGRAM_API_HASH"),
)
asyncio.run(client.start(phone=os.getenv("TELEGRAM_PHONE")))
print("Session saved. You can now remove TELEGRAM_PHONE from .env.")
asyncio.run(client.disconnect())
EOF
```

After this, a `telegram_lead_discovery_session.session` file is saved locally. The app reuses it on every subsequent run — `TELEGRAM_PHONE` is no longer needed and can be cleared from `.env`.
