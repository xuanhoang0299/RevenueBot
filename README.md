# 🧰 Revenue Bot — Telegram Sales & Inventory Management

> A Telegram bot that automatically records sales revenue, manages inventory, and syncs data to Google Sheets — organized by quarter.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![Telegram](https://img.shields.io/badge/Telegram-Bot_API-26A5E4?logo=telegram)
![Google Sheets](https://img.shields.io/badge/Google-Sheets-34A853?logo=googlesheets)

---

## ✨ Key Features

### 💰 Sales Revenue Tracking
- Quick input: `product_name amount` or `product_name quantity amount`
- Supports **Vietnamese diacritics-free input** (auto-matches inventory names)
- Flexible amount formats: `200`, `1tr5`, `1trieu`, `1.5trieu`
- Auto-syncs to Google Sheets, organized by quarter (Q2/2026, Q3/2026...)

### 📦 Inventory Management
- `/nhap` — Restock items (auto-creates new products if not found)
- `/tonkho` — View inventory with color-coded stock levels (🟢🟡🔴)
- `/xoanhap` — Undo last restock or deduct a specific quantity
- Selling auto-deducts inventory; deleting a sale auto-restores it

### 📊 Reports
- `/today` — Today's revenue (detailed, per transaction)
- `/tuan` — This week's summary
- `/thang` — This month's summary
- **Auto daily report at 5:30 AM** — Previous day's sales summary
- If the machine is off at 5:30 AM → report is sent on next startup

### 🔤 Smart Name Matching
- Type `van ep 12 ly` → auto-matches `Ván ép 12 ly` ✅
- Type `dao roc giay` → auto-matches `Dao rọc giấy` ✅
- Multiple matches → bot asks user to choose

---

## 🚀 Installation

### 1. Clone the repo

```bash
git clone https://github.com/xuanhoang0299/RevenueBot.git
cd RevenueBot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create a Telegram Bot

1. Open [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` → set a name → copy the **Bot Token**
3. Add the bot to a group or private chat
4. Get your **Chat ID** (run the bot, send `/start`, check the logs)

### 4. Set up Google Sheets API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable **Google Sheets API**
3. Create a **Service Account** → Download the JSON credentials file
4. Rename it to `gsheet_credentials.json` and place it in the project root
5. Share your Google Spreadsheet with the Service Account email (as **Editor**)

### 5. Configure .env

```bash
cp .env.example .env
```

Edit the `.env` file:

```env
REVENUE_BOT_TOKEN=your_bot_token_here
REVENUE_CHAT_ID=your_chat_id_here
GSHEET_CREDENTIALS=gsheet_credentials.json
GSHEET_SPREADSHEET_ID=your_spreadsheet_id_here
```

### 6. Run the bot

```bash
python revenue_bot.py
```

---

## 📋 Commands

| Command | Example | Description |
|---|---|---|
| Text input | `van ep 12 ly 2 500` | Sell 2 units, 500k VND |
| Text input | `mdf 200` | Sell 1 unit, 200k VND |
| `/today` | | Today's revenue |
| `/tuan` | | This week's revenue |
| `/thang` | | This month's revenue |
| `/xoa` | | Delete last sale + restore inventory |
| `/nhap` | `/nhap van ep 12 ly 50` | Restock 50 units |
| `/xoanhap` | `/xoanhap` | Undo last restock |
| `/xoanhap` | `/xoanhap van ep 10` | Deduct 10 units from inventory |
| `/tonkho` | `/tonkho` | View all inventory |
| `/tonkho` | `/tonkho van ep` | Search inventory |
| `/help` | | Usage guide |

---

## 🏗️ System Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────────┐
│  Telegram    │────▶│  Revenue Bot │────▶│   Google Sheets      │
│  (User)      │◀────│  (Python)    │────▶│  ┌────────────────┐  │
└─────────────┘     │              │     │  │ Q2/2026        │  │
                    │  ┌────────┐  │     │  │ (Revenue)      │  │
                    │  │ SQLite │  │     │  ├────────────────┤  │
                    │  │   DB   │  │     │  │ Inventory      │  │
                    │  └────────┘  │     │  │ (Stock)        │  │
                    └──────────────┘     │  └────────────────┘  │
                                        └──────────────────────┘
```

### Google Sheets Structure

| Sheet | Description | Data |
|---|---|---|
| `Quý X/YYYY` | Quarterly revenue | Auto-created on quarter change |
| `Tồn Kho` | Product inventory | ID, Name, Quantity, Unit |

---

## 📁 Project Structure

```
RevenueBot/
├── revenue_bot.py          # Main bot logic
├── setup_inventory.py      # One-time script to import initial inventory
├── requirements.txt        # Python dependencies
├── .env.example            # Configuration template
├── .gitignore
└── README.md
```

---

## ⚙️ Tech Stack

- **Python 3.11+**
- **python-telegram-bot** — Telegram Bot API wrapper
- **gspread** — Google Sheets API client
- **unidecode** — Vietnamese diacritics removal for smart matching
- **SQLite** — Local database
- **APScheduler** — Scheduled jobs (auto daily reports)

---

## 📝 Notes

- Only **one bot instance** should run at a time (to avoid 409 Conflict errors)
- Sales data is stored both locally (SQLite) and in the cloud (Google Sheets)
- You can edit inventory directly on Google Sheets — the bot reads in real-time
- `setup_inventory.py` is used to import the initial product list (run once)

---

## 📄 License

MIT License — Free to use and modify.
