# 🧰 Revenue Bot — Telegram Sales & Inventory Management

> Bot Telegram tự động ghi nhận doanh thu bán hàng, quản lý tồn kho và đồng bộ dữ liệu lên Google Sheets theo quý.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![Telegram](https://img.shields.io/badge/Telegram-Bot_API-26A5E4?logo=telegram)
![Google Sheets](https://img.shields.io/badge/Google-Sheets-34A853?logo=googlesheets)

---

## ✨ Tính năng chính

### 💰 Ghi nhận doanh thu
- Gõ nhanh: `tên SP số tiền` hoặc `tên SP số_lượng số_tiền`
- Hỗ trợ nhập không dấu tiếng Việt (tự khớp với tên trong kho)
- Hỗ trợ format: `200`, `1tr5`, `1trieu`, `1.5trieu`
- Tự động đồng bộ lên Google Sheets theo quý (Quý 2/2026, Quý 3/2026...)

### 📦 Quản lý tồn kho
- `/nhap` — Nhập hàng vào kho (tự thêm SP mới nếu chưa có)
- `/tonkho` — Xem tồn kho (có đèn 🟢🟡🔴 theo mức)
- `/xoanhap` — Undo nhập kho hoặc trừ số lượng cụ thể
- Bán hàng tự động trừ kho, xóa đơn tự động hoàn kho

### 📊 Báo cáo
- `/today` — Doanh thu hôm nay (chi tiết từng đơn)
- `/tuan` — Doanh thu tuần này
- `/thang` — Doanh thu tháng này
- **Báo cáo tự động 5:30 sáng** — Tổng kết ngày hôm trước
- Nếu máy tắt lúc 5:30 → bot gửi báo cáo khi khởi động lại

### 🔤 Khớp tên thông minh
- Gõ `van ep 12 ly` → tự khớp `Ván ép 12 ly` ✅
- Gõ `dao roc giay` → tự khớp `Dao rọc giấy` ✅
- Nhiều kết quả → bot hỏi chọn

---

## 🚀 Cài đặt

### 1. Clone repo

```bash
git clone https://github.com/YOUR_USERNAME/RevenueBot.git
cd RevenueBot
```

### 2. Cài dependencies

```bash
pip install -r requirements.txt
```

### 3. Tạo Telegram Bot

1. Mở [@BotFather](https://t.me/BotFather) trên Telegram
2. Gõ `/newbot` → đặt tên → lấy **Bot Token**
3. Thêm bot vào nhóm hoặc chat riêng
4. Lấy **Chat ID** (chạy bot rồi gõ `/start`, xem log)

### 4. Tạo Google Sheets API

1. Vào [Google Cloud Console](https://console.cloud.google.com/)
2. Tạo project → Enable **Google Sheets API**
3. Tạo **Service Account** → Download file JSON credentials
4. Đổi tên thành `gsheet_credentials.json`, đặt vào thư mục project
5. Share Google Spreadsheet cho email của Service Account (quyền **Editor**)

### 5. Cấu hình .env

```bash
cp .env.example .env
```

Sửa file `.env`:

```env
REVENUE_BOT_TOKEN=your_bot_token_here
REVENUE_CHAT_ID=your_chat_id_here
GSHEET_CREDENTIALS=gsheet_credentials.json
GSHEET_SPREADSHEET_ID=your_spreadsheet_id_here
```

### 6. Chạy bot

```bash
python revenue_bot.py
```

---

## 📋 Danh sách lệnh

| Lệnh | Ví dụ | Mô tả |
|---|---|---|
| Gõ text | `van ep 12 ly 2 500` | Bán 2 tấm ván ép, 500k |
| Gõ text | `mdf 200` | Bán 1 MDF, 200k |
| `/today` | | Doanh thu hôm nay |
| `/tuan` | | Doanh thu tuần này |
| `/thang` | | Doanh thu tháng này |
| `/xoa` | | Xóa đơn cuối + hoàn kho |
| `/nhap` | `/nhap van ep 12 ly 50` | Nhập 50 tấm vào kho |
| `/xoanhap` | `/xoanhap` | Undo lần nhập cuối |
| `/xoanhap` | `/xoanhap van ep 10` | Trừ 10 tấm khỏi kho |
| `/tonkho` | `/tonkho` | Xem toàn bộ tồn kho |
| `/tonkho` | `/tonkho van ep` | Tìm SP trong kho |
| `/help` | | Hướng dẫn sử dụng |

---

## 🏗️ Kiến trúc hệ thống

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────────┐
│  Telegram    │────▶│  Revenue Bot │────▶│   Google Sheets      │
│  (User gõ)  │◀────│  (Python)    │────▶│  ┌────────────────┐  │
└─────────────┘     │              │     │  │ Quý 2/2026     │  │
                    │  ┌────────┐  │     │  │ (Doanh thu)    │  │
                    │  │ SQLite │  │     │  ├────────────────┤  │
                    │  │   DB   │  │     │  │ Tồn Kho        │  │
                    │  └────────┘  │     │  │ (Inventory)    │  │
                    └──────────────┘     │  └────────────────┘  │
                                        └──────────────────────┘
```

### Cấu trúc Google Sheets

| Sheet | Mô tả | Dữ liệu |
|---|---|---|
| `Quý X/YYYY` | Doanh thu theo quý | Tự tạo khi qua quý mới |
| `Tồn Kho` | Danh sách SP + SL | STT, Tên, Số lượng, Đơn vị |

---

## 📁 Cấu trúc project

```
RevenueBot/
├── revenue_bot.py          # Bot chính
├── setup_inventory.py      # Script import dữ liệu tồn kho ban đầu
├── requirements.txt        # Dependencies
├── .env.example            # Template cấu hình
├── .gitignore
└── README.md
```

---

## ⚙️ Công nghệ

- **Python 3.11+**
- **python-telegram-bot** — Telegram Bot API
- **gspread** — Google Sheets API
- **unidecode** — Bỏ dấu tiếng Việt cho matching
- **SQLite** — Database local
- **APScheduler** — Scheduled jobs (báo cáo tự động)

---

## 📝 Ghi chú

- Bot chỉ chạy **1 instance** tại 1 thời điểm (tránh lỗi 409 Conflict)
- Dữ liệu doanh thu lưu cả local (SQLite) và cloud (Google Sheets)
- Có thể sửa tồn kho trực tiếp trên Google Sheets — bot đọc realtime
- File `setup_inventory.py` dùng để import danh sách SP ban đầu (chạy 1 lần)

---

## 📄 License

MIT License — Tự do sử dụng và chỉnh sửa.
