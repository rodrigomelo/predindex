# PredIndex

**Financial Index Analysis and Prediction Platform**

PredIndex is a platform for analyzing and predicting financial index movements with a focus on anticipating market trends.

## Features

- 📊 **Market Monitoring** — Real-time tracking of financial indices
- 📈 **Trend Analysis** — Dedicated index analysis tools
- 🔮 **Trend Prediction** — Data-driven market movement anticipation

## Tech Stack

- **Backend:** Python 3.11+ / FastAPI
- **Real-time:** Node.js
- **Database:** SQLite (dev) / PostgreSQL (prod)
- **Containerization:** Docker + Docker Compose

## Indices (Initial)

- Ibovespa (BVSP)
- S&P 500 (GSPC)
- USD/BRL (Dollar)

## Project Structure

```
predindex/
├── backend/                 # Python + FastAPI
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI entry point
│   │   ├── core/            # Config, security, dependencies
│   │   ├── api/             # API routes
│   │   ├── analysis/        # Index analysis logic
│   │   ├── models/          # Data models / schemas
│   │   ├── services/        # Business logic
│   │   └── utils/           # Utility functions
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── realtime/                # Node.js real-time server
│   ├── src/
│   │   ├── index.js         # Entry point
│   │   ├── routes/
│   │   ├── services/
│   │   └── utils/
│   ├── package.json
│   └── Dockerfile
├── data/                    # Data storage
├── docker-compose.yml
└── README.md
```

## Quick Start

### With Docker

```bash
docker-compose up --build
```

### Without Docker (Development)

#### Backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 5000 --reload
```

#### Real-time (Node.js)

```bash
cd realtime
npm install
npm run dev
```

## API Endpoints

| Method | Path              | Description                |
|--------|-------------------|----------------------------|
| GET    | `/health`         | Health check               |
| GET    | `/api/v1/indices`  | List available indices     |
| GET    | `/api/v1/indices/{symbol}` | Get index current data |
| GET    | `/api/v1/indices/{symbol}/history` | Historical data |
| GET    | `/api/v1/analysis/{symbol}` | Analysis for an index |

## License

Private — Rodrigo Melo
