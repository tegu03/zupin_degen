"""
Userbot Telethon yang mendengarkan channel sumber (Intel Hood by Vantis).

Kenapa userbot, bukan Bot API biasa: bot Telegram tidak bisa "membaca"
histori/pesan channel yang bukan miliknya kecuali dijadikan admin di
channel itu. Userbot (login pakai akun Telegram pribadi/khusus) bisa
membaca channel publik yang sudah di-join, persis seperti kamu scroll
manual.

Jalan pertama kali akan meminta login interaktif (nomor HP + kode OTP),
setelah itu session tersimpan di data/<TG_SESSION_NAME>.session dan tidak
perlu login ulang.
"""
import logging

from telethon import TelegramClient, events

logger = logging.getLogger(__name__)


def build_client(api_id: int, api_hash: str, session_name: str) -> TelegramClient:
    return TelegramClient(f"data/{session_name}", api_id, api_hash)


def register_handler(client: TelegramClient, source_channel: str, on_message):
    """on_message: async callable(text: str, message_id: int)"""

    @client.on(events.NewMessage(chats=source_channel))
    async def _handler(event):
        try:
            await on_message(event.raw_text, event.id)
        except Exception:
            logger.exception("Gagal proses pesan id=%s dari %s", event.id, source_channel)

    return _handler
