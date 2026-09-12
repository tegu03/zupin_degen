"""Titik masuk utama. Jalankan: python -m src.main"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import aiohttp
from sqlalchemy import select

from src.config import load_config
from src.db import Signal, Trade, get_session, init_db
from src.filter_engine import score_call
from src.message_parser import is_result_message, parse_call_message, parse_result_message
from src.notifier import Notifier
from src.paper_trader import open_trade, update_trade
from src.portfolio import Portfolio
from src.signal_matcher import apply_result_update
from src.telegram_listener import build_client, register_handler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("zupin_degen")


async def run():
    cfg = load_config()
    engine = init_db(cfg.database_url)
    db_session = get_session(engine)
    notifier = Notifier(cfg.output_bot_token, cfg.output_chat_id)
    portfolio = Portfolio(balance_usd=cfg.trading["starting_balance_usd"])

    client = build_client(cfg.tg_api_id, cfg.tg_api_hash, cfg.tg_session_name)

    async def on_message(text: str, message_id: int):
        if is_result_message(text):
            result = parse_result_message(text)
            if result:
                apply_result_update(db_session, result)
            return

        call = parse_call_message(text)
        if not call:
            return

        filter_result = score_call(call, cfg.filter)

        signal = Signal(
            contract_address=call.contract_address,
            ticker=call.ticker,
            source_message_id=message_id,
            mc_usd=call.mc_usd,
            liq_usd=call.liq_usd,
            age_minutes=(call.age_hours or 0) * 60,
            change_1h_pct=call.change_1h_pct,
            change_6h_pct=call.change_6h_pct,
            change_24h_pct=call.change_24h_pct,
            holders=call.holders,
            top10_pct=call.top10_pct,
            buys=call.buys,
            sells=call.sells,
            vol_1h_usd=call.vol_1h_usd,
            wallet_winrate_pct=call.wallet_winrate_pct,
            wallet_realized_usd=call.wallet_realized_usd,
            tag=call.tag,
            honeypot_flagged=call.honeypot_flagged,
            buy_tax_pct=call.buy_tax_pct,
            sell_tax_pct=call.sell_tax_pct,
            filter_score=filter_result.score,
            passed_filter=filter_result.passed,
            raw_text=call.raw_text,
        )
        db_session.add(signal)
        db_session.commit()

        if not filter_result.passed:
            await notifier.notify_rejected(call.ticker, filter_result.score, filter_result.reasons)
            return

        trade = open_trade(db_session, signal, portfolio, cfg.trading)
        if trade:
            await notifier.notify_new_trade(call.ticker, call.mc_usd, filter_result.score)

    register_handler(client, cfg.tg_source_channel, on_message)

    async def trade_monitor_loop():
        async with aiohttp.ClientSession() as http_session:
            while True:
                stmt = select(Trade).where(Trade.status == "open")
                open_trades = db_session.execute(stmt).scalars().all()
                for trade in open_trades:
                    events = await update_trade(
                        http_session, db_session, trade, portfolio, cfg.trading, cfg.price_feed["chain"]
                    )
                    for ev in events:
                        await notifier.notify_event(ev)
                await asyncio.sleep(cfg.price_feed["poll_interval_seconds"])

    async def daily_summary_loop():
        if not cfg.notifier["daily_summary"]:
            return
        while True:
            now = datetime.now(timezone.utc)
            target_hour = cfg.notifier["daily_summary_hour_utc"]
            next_run = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            await asyncio.sleep((next_run - now).total_seconds())

            closed = db_session.execute(select(Trade).where(Trade.status == "closed")).scalars().all()
            wins = [t for t in closed if (t.realized_pnl_usd or 0) > t.position_size_usd]
            avg_peak = sum(t.peak_multiplier for t in closed) / len(closed) if closed else 0
            await notifier.send_daily_summary(
                {
                    "balance_usd": portfolio.balance_usd,
                    "open_positions": portfolio.open_positions,
                    "closed_trades": len(closed),
                    "winrate_pct": (len(wins) / len(closed) * 100) if closed else 0,
                    "avg_peak_multiplier": avg_peak,
                }
            )

    async with client:
        logger.info("Zupin_Degen aktif, mendengarkan @%s", cfg.tg_source_channel)
        await asyncio.gather(
            client.run_until_disconnected(),
            trade_monitor_loop(),
            daily_summary_loop(),
        )


if __name__ == "__main__":
    asyncio.run(run())
