from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from pydantic_settings import BaseSettings

from backend.config import settings

logger = logging.getLogger(__name__)


class StrategySettings(BaseSettings):
    """All configurable parameters for the autonomous option selling strategy."""

    enabled: bool = False
    execution_mode: Literal["paper", "live"] = "paper"
    instruments: list[str] = ["NIFTY", "BANKNIFTY"]

    # Signal thresholds
    min_confidence_score: int = 70
    scan_interval_seconds: int = 60

    # Risk management
    max_positions: int = 4
    max_lots_per_trade: int = 2
    max_total_lots: int = 4
    max_risk_per_trade_pct: float = 5.0
    max_total_risk_pct: float = 15.0
    max_daily_loss_pct: float = 2.0
    min_risk_reward_ratio: float = 0.3
    min_time_between_trades_s: int = 900

    # Margin (approx SPAN + Exposure as % of contract notional)
    margin_pct_nifty: float = 15.0
    margin_pct_banknifty: float = 18.0

    # Position management
    target_pct: float = 50.0
    stop_loss_multiplier: float = 2.0
    trailing_sl_trigger_pct: float = 30.0
    trailing_sl_pct: float = 15.0

    # Execution
    limit_order_timeout_s: int = 30

    # Time filters
    no_trade_before: str = "09:30"
    no_trade_after: str = "14:30"

    # Expiry
    min_dte: int = 1
    preferred_dte_min: int = 2
    preferred_dte_max: int = 7

    # Strike selection
    otm_offset_points_nifty: float = 200.0
    otm_offset_points_banknifty: float = 500.0
    min_premium: float = 5.0
    max_premium: float = 1500.0

    # VIX thresholds
    vix_pause_threshold: float = 20.0
    vix_spike_pct: float = 20.0

    # Greeks / decay gate thresholds
    max_delta_for_sell: float = 0.40
    max_gamma_for_sell: float = 0.01
    min_theta_for_sell: float = 0.5
    max_iv_for_sell: float = 50.0
    risk_free_rate: float = 7.0

    # Smart SL parameters
    max_loss_per_trade_amount: float = 5000.0
    sl_delta_danger_threshold: float = 0.55
    sl_iv_spike_exit_pct: float = 30.0

    model_config = {"env_prefix": "STRATEGY_", "env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


def _config_file_path() -> Path:
    return settings.data_path / "strategy_config.json"


def load_strategy_settings() -> StrategySettings:
    """Load strategy settings from JSON file, falling back to defaults."""
    path = _config_file_path()
    if path.exists():
        try:
            with open(path, "r") as f:
                data = json.load(f)
            return StrategySettings(**data)
        except Exception as e:
            logger.warning("Failed to load strategy config, using defaults: %s", e)
    return StrategySettings()


def save_strategy_settings(s: StrategySettings) -> None:
    """Persist strategy settings to JSON file."""
    path = _config_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(s.model_dump(), f, indent=2)
    logger.info("Strategy config saved to %s", path)


strategy_settings = load_strategy_settings()
