#!/usr/bin/env python3
"""
get_chat_id.py

Helper kecil untuk menemukan Telegram Chat ID kamu.

Cara pakai:
1. Chat bot kamu di Telegram dulu (kirim pesan apa saja, misal "halo").
2. Jalankan script ini: python3 get_chat_id.py <BOT_TOKEN>
3. Chat ID kamu akan muncul di output.
"""

import sys
import requests


def main():
    if len(sys.argv) != 2:
        print("Cara pakai: python3 get_chat_id.py <BOT_TOKEN>")
        sys.exit(1)

    token = sys.argv[1]
    url = f"https://api.telegram.org/bot{token}/getUpdates"

    resp = requests.get(url, timeout=20)
    data = resp.json()

    if not data.get("ok"):
        print(f"Gagal mengambil update: {data}")
        sys.exit(1)

    results = data.get("result", [])
    if not results:
        print("Belum ada pesan masuk. Kirim pesan ke bot kamu dulu di Telegram, lalu jalankan ulang script ini.")
        sys.exit(0)

    seen = set()
    for item in results:
        message = item.get("message", {})
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        name = chat.get("first_name", chat.get("title", "?"))
        if chat_id and chat_id not in seen:
            seen.add(chat_id)
            print(f"Chat ID: {chat_id}  (dari: {name})")


if __name__ == "__main__":
    main()
