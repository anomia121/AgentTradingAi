#!/usr/bin/env python3
"""
daily_analysis.py

Agent harian: ambil data candle (XAUUSD, GBPJPY, EURUSD) dari TwelveData
di beberapa timeframe, minta Claude analisa key level Support/Resistance,
lalu kirim hasilnya ke Telegram.

Jalankan manual: python3 daily_analysis.py
Dijadwalkan otomatis lewat cron (lihat README.md).
"""

import os
import sys
import time
import json
from datetime import datetime

import requests
from anthropic import Anthropic

# ========================= CONFIG =========================
# Semua secret diambil dari environment variable / file .env
# JANGAN hardcode API key di sini.

TWELVEDATA_API_KEY = os.environ.get("TWELVEDATA_API_KEY")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL")  # opsional: isi kalau pakai router/gateway pihak ketiga (misal 9Router)
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")  # bisa diganti sesuai model yang tersedia di provider kamu
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

PAIRS = ["XAU/USD", "GBP/JPY", "EUR/USD"]
TIMEFRAMES = ["15min", "1h", "4h", "1day", "1week", "1month"]
CANDLES_PER_TF = 60  # jumlah candle historis yang diambil per timeframe

TWELVEDATA_BASE_URL = "https://api.twelvedata.com/time_series"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{{token}}/sendMessage"

REQUEST_DELAY_SECONDS = 8  # jeda antar request (TwelveData free tier: limit 8 request/menit)


def check_env():
    missing = []
    for name in ["TWELVEDATA_API_KEY", "ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]:
        if not os.environ.get(name):
            missing.append(name)
    if missing:
        print(f"[ERROR] Environment variable belum di-set: {', '.join(missing)}")
        print("Cek file .env atau export manual sebelum menjalankan script ini.")
        sys.exit(1)


def fetch_candles(symbol: str, interval: str) -> dict | None:
    """Ambil data candle dari TwelveData untuk satu pair + satu timeframe."""
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": CANDLES_PER_TF,
        "apikey": TWELVEDATA_API_KEY,
        "format": "JSON",
    }
    try:
        resp = requests.get(TWELVEDATA_BASE_URL, params=params, timeout=20)
        data = resp.json()
        if data.get("status") == "error":
            print(f"[WARN] TwelveData error untuk {symbol} {interval}: {data.get('message')}")
            return None
        return data
    except Exception as e:
        print(f"[ERROR] Gagal fetch {symbol} {interval}: {e}")
        return None


def summarize_candles(data: dict, max_rows: int = 60) -> str:
    """Ubah data candle jadi teks ringkas (OHLC) untuk dikirim ke Claude."""
    values = data.get("values", [])[:max_rows]
    if not values:
        return "(tidak ada data)"
    lines = []
    for v in reversed(values):  # urut dari lama ke baru
        lines.append(f"{v['datetime']} O:{v['open']} H:{v['high']} L:{v['low']} C:{v['close']}")
    return "\n".join(lines)


def collect_all_data() -> dict:
    """Kumpulkan data candle untuk semua pair x semua timeframe."""
    all_data = {}
    for pair in PAIRS:
        all_data[pair] = {}
        for tf in TIMEFRAMES:
            print(f"[INFO] Mengambil data {pair} - {tf}...")
            raw = fetch_candles(pair, tf)
            if raw:
                all_data[pair][tf] = summarize_candles(raw)
            else:
                all_data[pair][tf] = None
            time.sleep(REQUEST_DELAY_SECONDS)
    return all_data


def build_prompt(all_data: dict) -> str:
    """Susun prompt untuk Claude berdasarkan data candle yang sudah dikumpulkan."""
    today = datetime.now().strftime("%A, %d %B %Y")

    sections = []
    for pair, tf_data in all_data.items():
        sections.append(f"\n=== {pair} ===")
        for tf, candles in tf_data.items():
            if candles is None:
                sections.append(f"\n--- Timeframe {tf} ---\n(data tidak tersedia)")
            else:
                sections.append(f"\n--- Timeframe {tf} ---\n{candles}")

    data_block = "\n".join(sections)

    prompt = f"""Kamu adalah analis teknikal forex/gold berpengalaman dengan pendekatan ICT/Smart Money Concepts (SMC).

Hari ini: {today}

Berikut data candle (OHLC) untuk 3 instrumen, masing-masing di 6 timeframe (15min, 1H, 4H, Daily, Weekly, Monthly):

{data_block}

Tugas kamu:
1. Untuk SETIAP instrumen (XAU/USD, GBP/JPY, EUR/USD), identifikasi KEY LEVEL support dan resistance yang paling signifikan di SETIAP timeframe.
2. Fokus pada level yang relevan dengan konsep SMC: liquidity zones, order blocks / area konsolidasi penting, equal highs/lows, dan zona premium/discount.
3. Berikan ringkasan singkat bias arah (bullish/bearish/ranging) untuk masing-masing timeframe.
4. Tutup dengan satu paragraf kesimpulan: level mana yang paling penting untuk dipantau hari ini secara keseluruhan (confluence antar timeframe).

Format output:
- Gunakan format yang ringkas dan mudah dibaca di Telegram (gunakan emoji secukupnya, bold pada angka penting).
- Jangan gunakan tabel markdown (tidak render baik di Telegram).
- Batasi total panjang output supaya tidak terlalu panjang untuk pesan chat (maks sekitar 3500 karakter).
"""
    return prompt


def ask_claude(prompt: str) -> str:
    """Kirim prompt ke Claude API (atau kompatibel) dan ambil hasil analisanya."""
    client_kwargs = {"api_key": ANTHROPIC_API_KEY}
    if ANTHROPIC_BASE_URL:
        client_kwargs["base_url"] = ANTHROPIC_BASE_URL

    client = Anthropic(**client_kwargs)
    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in message.content if block.type == "text")


def send_telegram_message(text: str):
    """Kirim pesan ke Telegram, otomatis dipecah kalau kepanjangan."""
    url = TELEGRAM_API_URL.format(token=TELEGRAM_BOT_TOKEN)
    max_len = 4000  # batas aman di bawah limit Telegram (4096)

    chunks = [text[i:i + max_len] for i in range(0, len(text), max_len)]

    for chunk in chunks:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown",
        }
        try:
            resp = requests.post(url, json=payload, timeout=20)
            if resp.status_code != 200:
                print(f"[WARN] Gagal kirim ke Telegram: {resp.text}")
        except Exception as e:
            print(f"[ERROR] Gagal kirim ke Telegram: {e}")
        time.sleep(1)


def main():
    check_env()

    print("[INFO] Memulai analisa harian...")
    all_data = collect_all_data()

    print("[INFO] Menyusun prompt untuk Claude...")
    prompt = build_prompt(all_data)

    print("[INFO] Meminta analisa dari Claude...")
    analysis = ask_claude(prompt)

    header = f"📊 *Analisa Harian XAUUSD, GBPJPY, EURUSD*\n{datetime.now().strftime('%d %B %Y, %H:%M WIB')}\n\n"
    full_message = header + analysis

    print("[INFO] Mengirim hasil ke Telegram...")
    send_telegram_message(full_message)

    print("[INFO] Selesai!")


if __name__ == "__main__":
    main()
