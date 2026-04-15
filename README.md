# Apartment Rental Scraper

Scrapes filtered apartment search URLs and sends Telegram notifications when new listings appear. Dashboard hosted on GitHub Pages.

## Setup

### 1. Clone & push to GitHub
```bash
git init
git add .
git commit -m "init"
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

### 2. Add GitHub Secrets
Go to **Settings → Secrets → Actions** and add:

| Secret | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Your chat/group ID |

### 3. Enable GitHub Pages
Go to **Settings → Pages** → Source: **GitHub Actions**.

### 4. Enable Actions write permissions
Go to **Settings → Actions → General** → Workflow permissions → **Read and write permissions**.

### 5. Configure scrape sources
Edit `config.yaml` to add/remove scrape URLs.

## Adding a new scraper

1. Create `backend/scrapers/yoursite.py` with a class that extends `BaseScraper`
2. Register it in `SCRAPER_REGISTRY` in `backend/main.py`
3. Add a source entry in `config.yaml`

## Local run

```bash
pip install -r requirements.txt
python -m playwright install chromium
TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=yyy python -m backend.main
```
