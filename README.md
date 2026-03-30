# PredIndex

**Financial Index Analysis and Prediction Platform**

Real-time monitoring and technical analysis of financial indices, currencies, and cryptocurrencies.

## Features

- 📊 **Market Monitoring** — Real-time tracking of 9 assets across 3 categories
- 📈 **Technical Analysis** — RSI, MACD, Bollinger Bands, SMA, EMA
- 🔮 **Trend Prediction** — Signal generation (Buy/Sell/Hold) with confidence scoring
- 🏗️ **DB-First Architecture** — Pipeline fetches → DB stores → API serves → Frontend displays
- 🌙 **Dark Dashboard** — Chart.js-powered dark theme dashboard

## Tracked Assets

| Category | Symbol | Name | Source |
|----------|--------|------|--------|
| Markets | `^BVSP` | Ibovespa | Yahoo Finance |
| Markets | `^GSPC` | S&P 500 | Yahoo Finance |
| Markets | `IFIX.SA` | IFIX | StatusInvest (Playwright) |
| Currencies | `USDBRL=X` | USD/BRL | Yahoo Finance |
| Currencies | `EURBRL=X` | EUR/BRL | Yahoo Finance |
| Crypto | `BTC-USD` | Bitcoin | Yahoo Finance |
| Crypto | `ETH-USD` | Ethereum | Yahoo Finance |
| Crypto | `SOL-USD` | Solana | Yahoo Finance |
| Crypto | `XRP-USD` | Ripple | Yahoo Finance |

## Tech Stack

- **Backend:** Python 3.11 / FastAPI / Uvicorn
- **Database:** SQLite (dev) / PostgreSQL (prod)
- **Charts:** Chart.js 4
- **Scraping:** Playwright (IFIX from StatusInvest)
- **Data Source:** Yahoo Finance (yfinance)
- **Analysis:** pandas, numpy
- **Scheduling:** APScheduler (15min intervals)

## Project Structure

```
predindex/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry + dashboard serving
│   │   ├── core/config.py       # Settings (port, DB, indices)
│   │   ├── api/routes.py        # REST endpoints + INDEX_REGISTRY
│   │   ├── models/
│   │   │   ├── db.py            # SQLAlchemy models (Quote, History, Indicators)
│   │   │   └── schemas.py       # Pydantic schemas
│   │   ├── services/
│   │   │   └── market_data.py   # DB-first data service
│   │   ├── analysis/
│   │   │   └── technical.py     # RSI, MACD, Bollinger, SMA, EMA
│   │   ├── pipeline/
│   │   │   ├── fetcher.py       # Yahoo Finance fetcher + DB storage
│   │   │   ├── scheduler.py     # APScheduler periodic jobs
│   │   │   └── scrapers/
│   │   │       └── ifix_statusinvest.py  # StatusInvest scraper
│   │   └── utils/
│   │       ├── cache.py         # Simple TTL cache
│   │       └── dates.py         # Date helpers
│   ├── tests/test_api.py        # 8 API tests
│   └── requirements.txt
├── frontend/
│   └── index.html               # Single-page dashboard
├── docker-compose.yml
└── README.md
```

## Quick Start

### Development (without Docker)

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium  # For IFIX scraper
uvicorn app.main:app --host 0.0.0.0 --port 5004 --reload
```

### Docker

```bash
docker-compose up --build
```

Dashboard: `http://localhost:5004`

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/` | Dashboard (index.html) |
| GET | `/api/v1/indices` | List all tracked assets |
| GET | `/api/v1/indices/categories` | Assets grouped by category |
| GET | `/api/v1/quotes` | All latest quotes from DB |
| GET | `/api/v1/indices/{symbol}` | Quote for specific asset |
| GET | `/api/v1/indices/{symbol}/history` | Historical OHLCV data |
| GET | `/api/v1/analysis/{symbol}` | Technical analysis + signals |
| POST | `/api/v1/indices/{symbol}/refresh` | Force refresh from source |
| POST | `/api/v1/pipeline/trigger` | Trigger pipeline fetch |
| GET | `/api/v1/pipeline/status` | Pipeline status |

## Architecture

```
┌──────────┐     ┌─────────┐     ┌───────┐     ┌──────────┐
│ Pipeline │────▶│  SQLite │────▶│  API  │────▶│ Frontend │
│ (Cron)   │     │   DB    │     │(Fast) │     │ (HTML)   │
└──────────┘     └─────────┘     └───────┘     └──────────┘
     │                                              │
     ▼                                              ▼
 Yahoo Finance                              Chart.js Dashboard
 StatusInvest
```

- **Pipeline** fetches data every 15 minutes → stores in SQLite
- **API** reads from DB (no external calls from frontend requests)
- **Frontend** makes 2 API calls on load (indices + quotes)
- **IFIX** scraped from StatusInvest via Playwright (Yahoo has no data)

## License

Private — Rodrigo Melo
