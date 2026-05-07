from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.routes import auth, instruments, trading, portfolio, system
from backend.websocket_manager import market_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Paper Trading System starting up")
    yield
    logger.info("Shutting down – stopping market data feed")
    market_data.stop()


app = FastAPI(
    title="Paper Trading System",
    description="Nifty & BankNifty Options Paper Trading with Angel One SmartAPI",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(instruments.router)
app.include_router(trading.router)
app.include_router(portfolio.router)
app.include_router(system.router)


@app.websocket("/ws/market-data")
async def market_data_ws(ws: WebSocket):
    await market_data.connect_client(ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        market_data.disconnect_client(ws)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
