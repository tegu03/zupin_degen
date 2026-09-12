# Zupin_Degen

Bot filter + paper trading yang membaca sinyal dari channel Telegram
[Intel Hood by Vantis](https://t.me/intelhoodvantis), menyaring hanya coin
dengan potensi 3x–10x, lalu mensimulasikan trading (tanpa dana asli) dan
melaporkan hasilnya ke bot/channel Telegram milikmu sendiri.

Zupin_Degen **tidak** membuat sinyal sendiri. Dia murni lapisan filter +
simulator di atas data yang sudah dipublikasikan channel sumber.

## Alur singkat

```
Intel Hood Vantis (channel)
        |
        v
  telegram_listener.py   -> baca pesan call (🔎) & hasil (🏆)
        |
        v
  message_parser.py      -> ekstrak MC, liq, holder, wallet, audit, dst
        |
        v
  signal_matcher.py      -> hubungkan pesan call & update multiplier via contract address
        |
        v
  filter_engine.py       -> skor & saring, hanya lolos jika potensi 3x-10x
        |
        v
  paper_trader.py <----- price_feed.py (poll DexScreener per contract address)
        |
        v
  notifier.py             -> kirim alert entry/exit + laporan performa
        |
        v
  Bot/Channel Zupin_Degen kamu
```

Semua sinyal (lolos atau tidak) dan semua trade virtual disimpan di
`data/zupin_degen.db` (SQLite) lewat `db.py`, supaya kamu bisa evaluasi dan
tuning threshold filter dari waktu ke waktu.

## Setup

1. Salin `.env.example` ke `.env`, isi kredensial:
   - `TG_API_ID`, `TG_API_HASH`, `TG_SESSION_NAME` — untuk userbot Telethon (buat di https://my.telegram.org, dipakai untuk *membaca* channel sumber, bukan untuk posting)
   - `TG_SOURCE_CHANNEL` — username channel sumber, default `intelhoodvantis`
   - `OUTPUT_BOT_TOKEN`, `OUTPUT_CHAT_ID` — bot & channel/chat tujuan output kamu

2. Install dependency:
   ```bash
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Inisialisasi database:
   ```bash
   python scripts/init_db.py
   ```

4. Sesuaikan threshold filter di `config/settings.yaml` (lihat komentar di
   file itu untuk arti tiap parameter).

5. Jalankan:
   ```bash
   python -m src.main
   ```

## Deploy di VPS

Disediakan `Dockerfile` + `docker-compose.yml`. Cara tercepat:

```bash
docker compose up -d --build
```

Update ke versi baru cukup `git pull && docker compose up -d --build`.

Kalau tidak pakai Docker, pakai systemd (contoh unit file ada di
`scripts/zupin-degen.service`).

## Struktur repo

```
zupin-degen/
  src/
    telegram_listener.py   # userbot Telethon, dengarkan channel sumber
    message_parser.py      # regex parser format pesan Intel Hood Vantis
    signal_matcher.py      # cocokkan call <-> update multiplier
    filter_engine.py       # scoring & threshold 3x-10x
    price_feed.py          # polling harga/MC live via DexScreener API
    paper_trader.py        # simulasi entry, TP bertahap, SL, trailing stop
    portfolio.py           # saldo virtual & PnL
    notifier.py            # posting ke bot/channel output
    db.py                  # model SQLite (signals, trades)
    config.py              # loader .env + settings.yaml
    main.py                # orchestrator, jalankan semua komponen async
  config/settings.yaml     # semua parameter filter & trading, tanpa perlu ubah kode
  scripts/init_db.py
  scripts/zupin-degen.service
  tests/test_message_parser.py
  Dockerfile
  docker-compose.yml
  requirements.txt
  .env.example
```

## Catatan penting

- Ini **paper trading** (simulasi) — tidak ada eksekusi order asli, tidak
  menyentuh dompet/exchange. Cocok untuk validasi dulu seberapa efektif
  filter 3x-10x sebelum (kalau nanti) dihubungkan ke eksekusi asli.
- Parser dibuat berdasarkan format pesan yang kamu contohkan; kalau
  Intel Hood Vantis mengubah format kartunya, cuma `message_parser.py`
  yang perlu disesuaikan — modul lain tidak terpengaruh.
- Threshold filter di `settings.yaml` adalah titik awal berdasarkan pola di
  contoh $PAIREX (MC rendah, liq sehat, wallet reputasi, tag SMART MONEY).
  Sebaiknya dikalibrasi ulang setelah database `signals` terisi cukup data
  historis.
