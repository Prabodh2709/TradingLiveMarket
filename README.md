# PaperTrader - Nifty & BankNifty Options Paper Trading System

A full-stack paper trading system for Nifty and BankNifty options using Angel One SmartAPI for live market data.

## Features

- **Live Market Data** via Angel One SmartAPI WebSocket
- **Option Chain** with real-time LTP for NIFTY and BANKNIFTY
- **Paper Trading** with 7L initial balance
- **Position Tracking** with live unrealized P&L
- **Trade History** with full audit trail
- **Reset & Archive** system with versioned history

## Prerequisites

- Python 3.10+
- Node.js 18+
- Angel One SmartAPI credentials

## Setup

### 1. Environment Variables

Copy `.env.example` to `.env` and fill in your Angel One credentials:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `ANGEL_API_KEY` | Your SmartAPI app key |
| `ANGEL_CLIENT_CODE` | Your Angel One client ID |
| `ANGEL_PIN` | Your trading PIN |
| `ANGEL_TOTP_SECRET` | Your TOTP secret (for auto-generation) |
| `INITIAL_BALANCE` | Starting balance (default: 700000) |
| `DATA_DIR` | Data storage path (default: ./data) |

### 2. Backend (Python venv)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

### 3. Frontend

```bash
cd frontend
npm install
```

## Running

### Start Backend (from project root)

```bash
source venv/bin/activate
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Start Frontend (in another terminal)

```bash
cd frontend
npm run dev
```

Open http://localhost:5173 in your browser.

## How It Works

1. **Login** with your Angel One credentials (or auto-generate TOTP from .env)
2. **Refresh Instruments** to download the latest option chain
3. **Select Index** (NIFTY or BANKNIFTY) and expiry
4. **Subscribe** to live market data for that expiry
5. **Buy** options from the option chain
6. **Monitor** positions with live P&L on the dashboard
7. **Square Off** when ready
8. **Reset** the system to start fresh (previous session gets archived)

## Data Storage

All data is stored as JSON files in the `data/` directory:

```
data/
  portfolio.json          # Current balance and P&L
  positions.json          # Open positions
  trades.json             # Trade log
  instruments_cache.json  # Cached instrument master
  history/                # Archived sessions
    v1_2026-05-07.../
    v2_2026-05-08.../
```

## Disclaimer

This is a paper trading system only. No real orders are placed.
