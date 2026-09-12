"""SQLite models: signals (semua call yg terbaca) & trades (paper trades)."""
from datetime import datetime, timezone

from sqlalchemy import (Boolean, Column, DateTime, Float, ForeignKey, Integer,
                         String, create_engine)
from sqlalchemy.orm import DeclarativeBase, Session, relationship


class Base(DeclarativeBase):
    pass


class Signal(Base):
    """Satu baris = satu pesan call (🔎) yang berhasil di-parse."""

    __tablename__ = "signals"

    id = Column(Integer, primary_key=True)
    contract_address = Column(String, index=True, nullable=False)
    ticker = Column(String)
    source_message_id = Column(Integer)
    called_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    mc_usd = Column(Float)
    liq_usd = Column(Float)
    age_minutes = Column(Float)
    change_1h_pct = Column(Float)
    change_6h_pct = Column(Float)
    change_24h_pct = Column(Float)
    holders = Column(Integer)
    top10_pct = Column(Float)
    buys = Column(Integer)
    sells = Column(Integer)
    vol_1h_usd = Column(Float)
    wallet_winrate_pct = Column(Float)
    wallet_realized_usd = Column(Float)
    tag = Column(String)
    honeypot_flagged = Column(Boolean)
    buy_tax_pct = Column(Float)
    sell_tax_pct = Column(Float)

    filter_score = Column(Float)
    passed_filter = Column(Boolean, default=False)

    max_multiplier_seen = Column(Float, default=1.0)
    raw_text = Column(String)

    trades = relationship("Trade", back_populates="signal")


class Trade(Base):
    """Satu baris = satu paper trade yang dibuka Zupin_Degen."""

    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    signal_id = Column(Integer, ForeignKey("signals.id"))
    contract_address = Column(String, index=True, nullable=False)
    ticker = Column(String)

    entry_price_mc_usd = Column(Float)
    entry_time = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    position_size_usd = Column(Float)

    status = Column(String, default="open")  # open | closed | expired
    remaining_pct = Column(Float, default=100.0)

    exit_price_mc_usd = Column(Float)
    exit_time = Column(DateTime)
    exit_reason = Column(String)  # tp1 | tp2 | tp3 | stop_loss | liquidity_drop | trailing_stop | timeout

    realized_pnl_usd = Column(Float, default=0.0)
    peak_multiplier = Column(Float, default=1.0)

    signal = relationship("Signal", back_populates="trades")


def get_engine(database_url: str):
    return create_engine(database_url, future=True)


def init_db(database_url: str):
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine) -> Session:
    return Session(engine)
