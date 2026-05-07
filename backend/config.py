import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    angel_api_key: str = ""
    angel_client_code: str = ""
    angel_pin: str = ""
    angel_totp_secret: str = ""
    initial_balance: float = 700000.0
    data_dir: str = "./data"

    nifty_lot_size: int = 25
    banknifty_lot_size: int = 15

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)

    @property
    def history_path(self) -> Path:
        return self.data_path / "history"

    def ensure_dirs(self) -> None:
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.history_path.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
