"""Load .env + config/settings.yaml into a single Config object."""
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _load_yaml() -> dict:
    path = ROOT_DIR / "config" / "settings.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class Config:
    tg_api_id: int
    tg_api_hash: str
    tg_session_name: str
    tg_source_channel: str
    output_bot_token: str
    output_chat_id: str
    database_url: str
    settings: dict = field(default_factory=dict)

    @property
    def filter(self) -> dict:
        return self.settings["filter"]

    @property
    def trading(self) -> dict:
        return self.settings["trading"]

    @property
    def price_feed(self) -> dict:
        return self.settings["price_feed"]

    @property
    def notifier(self) -> dict:
        return self.settings["notifier"]


def load_config() -> Config:
    missing = [
        k
        for k in ("TG_API_ID", "TG_API_HASH", "OUTPUT_BOT_TOKEN", "OUTPUT_CHAT_ID")
        if not os.getenv(k)
    ]
    if missing:
        raise RuntimeError(
            f"Env var berikut belum diisi di .env: {', '.join(missing)}"
        )

    return Config(
        tg_api_id=int(os.environ["TG_API_ID"]),
        tg_api_hash=os.environ["TG_API_HASH"],
        tg_session_name=os.getenv("TG_SESSION_NAME", "zupin_degen_session"),
        tg_source_channel=os.getenv("TG_SOURCE_CHANNEL", "intelhoodvantis"),
        output_bot_token=os.environ["OUTPUT_BOT_TOKEN"],
        output_chat_id=os.environ["OUTPUT_CHAT_ID"],
        database_url=os.getenv("DATABASE_URL", "sqlite:///data/zupin_degen.db"),
        settings=_load_yaml(),
    )
