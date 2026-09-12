"""Jalankan sekali di awal: python scripts/init_db.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config
from src.db import init_db

if __name__ == "__main__":
    cfg = load_config()
    Path("data").mkdir(exist_ok=True)
    init_db(cfg.database_url)
    print(f"Database siap di {cfg.database_url}")
