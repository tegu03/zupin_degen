"""
Mesin paper trading. Tidak ada eksekusi order asli -- semua entry/exit
adalah pencatatan di database, dihitung dari harga live yang diambil
price_feed.py.

Alur satu trade:
  1. open_trade()  -- dipanggil filter_engine/main saat sebuah call lolos filter
  2. update_trade() -- dipanggil berkala (loop di main.py) untuk tiap trade
     yang masih 'open', mengecek TP ladder / SL / trailing stop / timeout
"""
import logging
from datetime import datetime, timedelta, timezone

import aiohttp

from src.db import Signal, Trade
from src.portfolio import Portfolio
from src.price_feed import fetch_pair_data

logger = logging.getLogger(__name__)


def open_trade(db_session, signal: Signal, portfolio: Portfolio, trading_cfg: dict) -> Trade | None:
    size = trading_cfg["position_size_usd"]
    if not portfolio.can_open_position(size, trading_cfg["max_concurrent_positions"]):
        logger.info("Portfolio penuh / saldo kurang, skip trade untuk %s", signal.ticker)
        return None

    trade = Trade(
        signal_id=signal.id,
        contract_address=signal.contract_address,
        ticker=signal.ticker,
        entry_price_mc_usd=signal.mc_usd,
        position_size_usd=size,
        status="open",
        remaining_pct=100.0,
        peak_multiplier=1.0,
    )
    db_session.add(trade)
    portfolio.open_position(size)
    db_session.commit()
    logger.info("Buka paper trade %s di MC $%.0f", trade.ticker, trade.entry_price_mc_usd)
    return trade


async def update_trade(
    http_session: aiohttp.ClientSession,
    db_session,
    trade: Trade,
    portfolio: Portfolio,
    trading_cfg: dict,
    chain: str,
) -> list[str]:
    """Return list of pesan event (untuk notifier) yang terjadi pada trade ini."""
    events: list[str] = []

    market = await fetch_pair_data(http_session, trade.contract_address, chain)
    if not market or not market.get("mc_usd"):
        return events

    current_mc = market["mc_usd"]
    multiplier = current_mc / trade.entry_price_mc_usd if trade.entry_price_mc_usd else 0
    trade.peak_multiplier = max(trade.peak_multiplier, multiplier)

    # --- Timeout ---
    age = datetime.now(timezone.utc) - trade.entry_time.replace(tzinfo=timezone.utc)
    if age > timedelta(hours=trading_cfg["max_hold_hours"]) and trade.status == "open":
        _close_remaining(trade, portfolio, current_mc, "timeout")
        events.append(f"{trade.ticker}: ditutup (timeout {trading_cfg['max_hold_hours']}h) di {multiplier:.2f}x")
        db_session.commit()
        return events

    # --- Stop loss ---
    change_pct = (multiplier - 1) * 100
    if change_pct <= trading_cfg["stop_loss_pct"] and trade.status == "open":
        _close_remaining(trade, portfolio, current_mc, "stop_loss")
        events.append(f"{trade.ticker}: STOP LOSS di {multiplier:.2f}x ({change_pct:.0f}%)")
        db_session.commit()
        return events

    # --- Liquidity drop exit ---
    liq_usd = market.get("liq_usd")
    if liq_usd is not None and trade.status == "open":
        # Bandingkan terhadap liquidity saat entry tersimpan di signal, kalau ada
        pass  # placeholder: perlu liq_usd_at_entry disimpan di Trade kalau ingin dipakai persis

    # --- Trailing stop (setelah capai target multiplier) ---
    if (
        trade.peak_multiplier >= trading_cfg["trailing_stop_after_multiplier"]
        and trade.status == "open"
    ):
        drawdown_pct = (trade.peak_multiplier - multiplier) / trade.peak_multiplier * 100
        if drawdown_pct >= trading_cfg["trailing_stop_pct"]:
            _close_remaining(trade, portfolio, current_mc, "trailing_stop")
            events.append(
                f"{trade.ticker}: TRAILING STOP di {multiplier:.2f}x (puncak {trade.peak_multiplier:.2f}x)"
            )
            db_session.commit()
            return events

    # --- Take profit ladder ---
    for i, tp in enumerate(trading_cfg["take_profit_ladder"], start=1):
        tp_key = f"tp{i}"
        already_taken = trade.exit_reason and tp_key in (trade.exit_reason or "")
        if multiplier >= tp["multiplier"] and not already_taken and trade.remaining_pct > 0:
            sell_pct = min(tp["sell_pct"], trade.remaining_pct)
            pnl = trade.position_size_usd * (sell_pct / 100) * multiplier
            trade.realized_pnl_usd = (trade.realized_pnl_usd or 0) + pnl
            trade.remaining_pct -= sell_pct
            portfolio.balance_usd += pnl
            events.append(
                f"{trade.ticker}: TP{i} tercapai {tp['multiplier']}x, jual {sell_pct}% posisi (+${pnl:.2f})"
            )
            trade.exit_reason = f"{trade.exit_reason or ''}+{tp_key}".strip("+")
            if trade.remaining_pct <= 0:
                trade.status = "closed"
                trade.exit_time = datetime.now(timezone.utc)
                trade.exit_price_mc_usd = current_mc
                portfolio.open_positions = max(0, portfolio.open_positions - 1)
            db_session.commit()

    return events


def _close_remaining(trade: Trade, portfolio: Portfolio, current_mc: float, reason: str) -> None:
    multiplier = current_mc / trade.entry_price_mc_usd if trade.entry_price_mc_usd else 0
    remaining_value = trade.position_size_usd * (trade.remaining_pct / 100) * multiplier
    trade.realized_pnl_usd = (trade.realized_pnl_usd or 0) + remaining_value
    trade.remaining_pct = 0
    trade.status = "closed"
    trade.exit_time = datetime.now(timezone.utc)
    trade.exit_price_mc_usd = current_mc
    trade.exit_reason = f"{trade.exit_reason or ''}+{reason}".strip("+")
    portfolio.balance_usd += remaining_value
    portfolio.open_positions = max(0, portfolio.open_positions - 1)
