from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.config import settings
from backend.db.schema import HistoryMeta, Portfolio, Position, Trade


def _portfolio_path() -> Path:
    return settings.data_path / "portfolio.json"


def _trades_path() -> Path:
    return settings.data_path / "trades.json"


def _positions_path() -> Path:
    return settings.data_path / "positions.json"


def _read_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, "r") as f:
        return json.load(f)


def _write_json(path: Path, data) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


# ── Portfolio ────────────────────────────────────────────────────

def load_portfolio() -> Portfolio:
    data = _read_json(_portfolio_path(), None)
    if data is None:
        portfolio = Portfolio(
            balance=settings.initial_balance,
            initial_balance=settings.initial_balance,
        )
        save_portfolio(portfolio)
        return portfolio
    return Portfolio(**data)


def save_portfolio(portfolio: Portfolio) -> None:
    _write_json(_portfolio_path(), portfolio.model_dump())


# ── Trades ───────────────────────────────────────────────────────

def load_trades() -> list[Trade]:
    data = _read_json(_trades_path(), [])
    return [Trade(**t) for t in data]


def save_trades(trades: list[Trade]) -> None:
    _write_json(_trades_path(), [t.model_dump() for t in trades])


def append_trade(trade: Trade) -> None:
    trades = load_trades()
    trades.append(trade)
    save_trades(trades)


# ── Positions ────────────────────────────────────────────────────

def load_positions() -> list[Position]:
    data = _read_json(_positions_path(), [])
    return [Position(**p) for p in data]


def save_positions(positions: list[Position]) -> None:
    _write_json(_positions_path(), [p.model_dump() for p in positions])


def find_position(token: str) -> Optional[Position]:
    for p in load_positions():
        if p.token == token:
            return p
    return None


# ── Reset & Versioned Archival ───────────────────────────────────

def _next_version_number() -> int:
    history = settings.history_path
    if not history.exists():
        return 1
    existing = [d.name for d in history.iterdir() if d.is_dir()]
    if not existing:
        return 1
    versions = []
    for name in existing:
        try:
            versions.append(int(name.split("_")[0].lstrip("v")))
        except (ValueError, IndexError):
            continue
    return max(versions, default=0) + 1


def reset_system() -> HistoryMeta:
    """Archive current state and reset to initial balance."""
    portfolio = load_portfolio()
    trades = load_trades()
    positions = load_positions()

    version = _next_version_number()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    folder_name = f"v{version}_{timestamp}"
    version_dir = settings.history_path / folder_name
    version_dir.mkdir(parents=True, exist_ok=True)

    total_pnl = portfolio.balance - portfolio.initial_balance

    if _portfolio_path().exists():
        shutil.copy2(_portfolio_path(), version_dir / "portfolio.json")
    if _trades_path().exists():
        shutil.copy2(_trades_path(), version_dir / "trades.json")
    if _positions_path().exists():
        shutil.copy2(_positions_path(), version_dir / "positions.json")

    meta = HistoryMeta(
        version=version,
        final_balance=portfolio.balance,
        total_pnl=total_pnl,
        total_trades=len(trades),
    )
    _write_json(version_dir / "meta.json", meta.model_dump())

    new_portfolio = Portfolio(
        balance=settings.initial_balance,
        initial_balance=settings.initial_balance,
    )
    save_portfolio(new_portfolio)
    save_trades([])
    save_positions([])

    return meta


def list_history_versions() -> list[dict]:
    history = settings.history_path
    if not history.exists():
        return []
    versions = []
    for d in sorted(history.iterdir()):
        if not d.is_dir():
            continue
        meta_path = d / "meta.json"
        if meta_path.exists():
            meta = _read_json(meta_path, {})
            meta["folder"] = d.name
            versions.append(meta)
    return versions


def load_history_version(folder: str) -> dict:
    version_dir = settings.history_path / folder
    if not version_dir.exists():
        raise FileNotFoundError(f"History version '{folder}' not found")
    return {
        "meta": _read_json(version_dir / "meta.json", {}),
        "portfolio": _read_json(version_dir / "portfolio.json", {}),
        "trades": _read_json(version_dir / "trades.json", []),
        "positions": _read_json(version_dir / "positions.json", []),
    }
