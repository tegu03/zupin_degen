"""Kirim alert & ringkasan ke bot/channel output pakai python-telegram-bot."""
import logging

from telegram import Bot
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id

    async def send(self, text: str) -> None:
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode=ParseMode.HTML)
        except Exception:
            logger.exception("Gagal kirim pesan ke output chat")

    async def notify_new_trade(self, ticker: str, entry_mc: float, score: float) -> None:
        await self.send(
            f"🟢 <b>Entry baru: ${ticker}</b>\n"
            f"MC saat entry: ${entry_mc:,.0f}\n"
            f"Skor filter: {score}/100"
        )

    async def notify_rejected(self, ticker: str, score: float, reasons: list[str]) -> None:
        # Opsional: kirim ke chat/log terpisah kalau mau audit call yang ditolak
        logger.info("Ditolak $%s (skor %.1f): %s", ticker, score, "; ".join(reasons))

    async def notify_event(self, text: str) -> None:
        await self.send(f"ℹ️ {text}")

    async def send_daily_summary(self, stats: dict) -> None:
        await self.send(
            "📊 <b>Ringkasan harian Zupin_Degen</b>\n"
            f"Saldo virtual: ${stats['balance_usd']:,.2f}\n"
            f"Posisi terbuka: {stats['open_positions']}\n"
            f"Total trade ditutup: {stats['closed_trades']}\n"
            f"Winrate: {stats['winrate_pct']:.1f}%\n"
            f"Rata-rata multiplier puncak: {stats['avg_peak_multiplier']:.2f}x"
        )
