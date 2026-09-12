"""Cocokkan pesan hasil ('Nx from our call') ke signal call sebelumnya
lewat contract_address, lalu update max_multiplier_seen -- berguna untuk
riset/evaluasi filter (bukan buat paper trading, karena paper trading
sudah pakai harga live dari price_feed.py, bukan dari klaim channel)."""
import logging

from sqlalchemy import select

from src.db import Signal
from src.message_parser import ParsedResult

logger = logging.getLogger(__name__)


def apply_result_update(db_session, result: ParsedResult) -> Signal | None:
    stmt = (
        select(Signal)
        .where(Signal.contract_address == result.contract_address)
        .order_by(Signal.called_at.desc())
    )
    signal = db_session.execute(stmt).scalars().first()
    if not signal:
        logger.debug("Result untuk %s tidak punya call sebelumnya di DB", result.contract_address)
        return None

    if result.multiplier > (signal.max_multiplier_seen or 1.0):
        signal.max_multiplier_seen = result.multiplier
        db_session.commit()

    return signal
