# Trading Agent — Analisa Harian XAUUSD / GBPJPY / EURUSD

Agent otomatis yang tiap pagi:
1. Ambil data candle dari TwelveData (6 timeframe: 15m, 1H, 4H, D1, W1, Monthly)
2. Kirim ke Claude API untuk dianalisa (key support/resistance, bias, gaya ICT/SMC)
3. Kirim hasilnya ke Telegram kamu

## ⚠️ PENTING — Soal Keamanan API Key

**Jangan pernah tempel API key langsung di chat, script, atau commit ke GitHub.**
Semua key disimpan di file `.env` yang **tidak pernah di-share/upload**.

Kalau kamu pernah tidak sengaja share API key (misal di chat), **segera revoke/regenerate key tersebut**:
- Anthropic: console.anthropic.com → API Keys
- TwelveData: dashboard → API Keys
- Telegram: @BotFather → /mybots → API Token → Revoke

## Cara Install di VPS

### 1. Upload folder ini ke VPS

```bash
mkdir -p /root/trading-agent
cd /root/trading-agent
# upload daily_analysis.py, requirements.txt, .env.example, get_chat_id.py ke sini
```

### 2. Install Python & dependencies

```bash
apt install -y python3 python3-pip python3-venv
cd /root/trading-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Buat bot Telegram (kalau belum)

1. Chat **@BotFather** di Telegram
2. Kirim `/newbot`, ikuti instruksi (kasih nama bot)
3. Simpan **token** yang diberikan

### 4. Cari Chat ID kamu

1. Chat bot kamu (kirim pesan apa saja, misal "halo")
2. Jalankan:
```bash
python3 get_chat_id.py <BOT_TOKEN_KAMU>
```
3. Catat Chat ID yang muncul

### 5. Setup file `.env`

```bash
cp .env.example .env
nano .env
```

Isi dengan API key kamu yang **baru** (bukan yang sudah pernah ter-expose):
```
TWELVEDATA_API_KEY=xxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxx
TELEGRAM_BOT_TOKEN=xxxxx:xxxxx
TELEGRAM_CHAT_ID=xxxxx
```

Simpan (Ctrl+O, Enter, Ctrl+X).

**Amankan file ini supaya tidak bisa dibaca user lain:**
```bash
chmod 600 .env
```

### 6. Test jalankan manual

```bash
source venv/bin/activate
export $(cat .env | xargs)
python3 daily_analysis.py
```

Kalau berhasil, kamu akan terima pesan analisa di Telegram dalam beberapa detik/menit (tergantung kecepatan API).

### 7. Jadwalkan otomatis tiap pagi (jam 5-7 WIB)

Buka crontab:
```bash
crontab -e
```

Tambahkan baris ini (jalan tiap hari jam 05:30 WIB — sesuaikan sesuai selera, misal mau jam 5 pas atau jam 6):

```
30 5 * * * cd /root/trading-agent && /root/trading-agent/venv/bin/python3 -c "import os; [os.environ.__setitem__(k,v) for k,v in (l.strip().split('=',1) for l in open('.env') if l.strip() and not l.startswith('#'))]; exec(open('daily_analysis.py').read())" >> /root/trading-agent/log.txt 2>&1
```

**Atau cara yang lebih rapi**, pakai wrapper script:

```bash
cat > /root/trading-agent/run.sh <<'EOF'
#!/bin/bash
cd /root/trading-agent
export $(cat .env | grep -v '^#' | xargs)
./venv/bin/python3 daily_analysis.py
EOF
chmod +x /root/trading-agent/run.sh
```

Lalu di crontab:
```
30 5 * * * /root/trading-agent/run.sh >> /root/trading-agent/log.txt 2>&1
```

Ini akan jalan setiap hari jam **05:30 WIB** (sesuaikan angka jam:menit sesuai kebutuhan, format cron: `menit jam * * *`).

Cek timezone VPS kamu dulu supaya jamnya pas:
```bash
timedatectl
```
Kalau VPS belum di WIB, set dulu:
```bash
timedatectl set-timezone Asia/Jakarta
```

## Cek Log

```bash
tail -f /root/trading-agent/log.txt
```

## Catatan Biaya

- **TwelveData**: gratis untuk 800 request/hari (script ini pakai ~18 request/hari — 3 pair × 6 timeframe)
- **Anthropic API**: berbayar per-token. Model `claude-sonnet-4-6` — cek harga terbaru di console.anthropic.com. Dengan data 6 timeframe × 3 pair, sekali jalan kira-kira memakai beberapa ribu token input + output, jadi biayanya kecil per hari, tapi tetap cek saldo/billing kamu secara berkala.
- **Telegram Bot API**: gratis, tidak ada biaya.

## Kustomisasi

- Ganti pair di `PAIRS` (dalam `daily_analysis.py`) kalau mau tambah/kurangi instrumen
- Ganti `TIMEFRAMES` kalau mau timeframe berbeda
- Edit `build_prompt()` kalau mau gaya analisa berbeda (misal lebih fokus ke satu konsep tertentu)
