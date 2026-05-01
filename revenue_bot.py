"""
Revenue Bot — Bot Telegram ghi nhận doanh thu + quản lý tồn kho
================================================================
Cách dùng:
    Gõ trực tiếp: <tên SP> <số lượng> <số tiền (nghìn VND)>
    Ví dụ: van ep 12 ly 2 500  →  Ván ép 12 ly, SL: 2, 500.000 VND
    Nếu SL = 1:  mdf 200  →  MDF, SL: 1, 200.000 VND

Lệnh:
    /today   — Xem doanh thu hôm nay
    /tuan    — Xem doanh thu tuần này
    /thang   — Xem doanh thu tháng này
    /xoa     — Xóa giao dịch cuối cùng (hoàn kho)
    /nhap    — Nhập hàng vào kho
    /tonkho  — Xem tồn kho
    /help    — Hướng dẫn sử dụng
"""

import os
import sys
import re
import logging
import sqlite3
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv

# ─── Load .env ────────────────────────────────────────────────────────
load_dotenv()

BOT_TOKEN = os.getenv("REVENUE_BOT_TOKEN", "")
CHAT_ID = os.getenv("REVENUE_CHAT_ID", os.getenv("CHAT_ID", ""))
TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# ─── Google Sheets ────────────────────────────────────────────────────
GSHEET_CREDENTIALS = os.getenv("GSHEET_CREDENTIALS", "")
GSHEET_SPREADSHEET_ID = os.getenv("GSHEET_SPREADSHEET_ID", "1cKWKCAin6JVQmSzyM5wjK5o30t-eGFAgs_lc3Kf6pV0")
GSHEET_DATA_START_ROW = 10  # Dữ liệu bắt đầu từ row 10 (sau header A,B,C,1 ở row 9)
GSHEET_DATA_END_ROW = 39    # Row cuối vùng dữ liệu (row 40+ là footer)
GSHEET_INVENTORY_SHEET = "Tồn Kho"

# ─── Logging ──────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "revenue_bot.log")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ─── Google Sheets Helper ─────────────────────────────────────────────
_gsheet_client = None


def get_gsheet_client():
    """Lazy-init gspread client với Service Account credentials."""
    global _gsheet_client
    if _gsheet_client is not None:
        return _gsheet_client

    if not GSHEET_CREDENTIALS:
        logger.warning("GSHEET_CREDENTIALS chưa được cấu hình, bỏ qua Google Sheets.")
        return None

    try:
        import gspread
        creds_path = os.path.join(BASE_DIR, GSHEET_CREDENTIALS)
        if not os.path.exists(creds_path):
            creds_path = GSHEET_CREDENTIALS  # Thử đường dẫn tuyệt đối
        _gsheet_client = gspread.service_account(filename=creds_path)
        logger.info("Google Sheets client initialized.")
        return _gsheet_client
    except Exception as e:
        logger.error(f"Lỗi khởi tạo Google Sheets: {e}")
        return None


def get_quarter_sheet_name():
    """Trả về tên sheet theo quý hiện tại: 'Quý 2/2026', 'Quý 3/2026'..."""
    now = datetime.now(TZ)
    quarter = (now.month - 1) // 3 + 1
    return f"Quý {quarter}/{now.year}"


def get_or_create_quarter_sheet(spreadsheet):
    """
    Lấy sheet theo quý hiện tại.
    Nếu chưa có, tự tạo mới với header template giống sổ doanh thu.
    """
    sheet_name = get_quarter_sheet_name()

    # Tìm sheet theo tên
    try:
        return spreadsheet.worksheet(sheet_name)
    except Exception:
        pass  # Sheet chưa tồn tại, tạo mới

    # Tạo sheet mới với 50 rows
    new_sheet = spreadsheet.add_worksheet(title=sheet_name, rows=50, cols=4)

    # Ghi header template
    header_data = [
        ["HỘ, CÁ NHÂN KINH DOANH:......\nMã số thuế:........................................\nĐịa chỉ:.............................................", "", "",
         "Mẫu số S2a-HKD\n(Kèm theo Thông tư số 152/2025/TT-BTC ngày 31 tháng 12 năm 2025 của Bộ trưởng Bộ Tài chính)"],
        ["", "", "", ""],
        ["SỔ DOANH THU BÁN HÀNG HÓA, DỊCH VỤ", "", "", ""],
        ["Địa điểm kinh doanh:..........................", "", "", ""],
        ["Kỳ kê khai:.................................", "", "", ""],
        ["", "", "", ""],
        ["Chứng từ", "", "Diễn giải", "Số tiền"],
        ["Số hiệu", "Ngày, tháng", "", ""],
        ["A", "B", "C", "1"],
    ]
    new_sheet.update(values=header_data, range_name="A1:D9")

    # Ghi footer
    footer_data = [
        ["", "", "Tổng số thuế GTGT phải nộp", ""],
        ["", "", "Tổng số thuế TNCN phải nộp", ""],
        ["", "", "", ""],
        ["", "", "", "Ngày ... tháng ... năm ..."],
        ["", "", "", "NGƯỜI ĐẠI DIỆN HỘ KINH DOANH/"],
        ["", "", "", "CÁ NHÂN KINH DOANH"],
        ["", "", "", "(Ký, họ tên, đóng dấu)"],
    ]
    new_sheet.update(values=footer_data, range_name="A40:D46")

    logger.info(f"Google Sheets: Đã tạo sheet mới '{sheet_name}'")
    return new_sheet


def push_to_gsheet(product: str, amount_k: int, date_str: str):
    """
    Đẩy 1 giao dịch lên Google Sheet (sheet theo quý).
    - date_str: format dd/mm/yyyy
    - Nếu ngày đã có trong sheet, chỉ thêm dòng mới (không ghi lại ngày)
    - Nếu chưa có, ghi ngày vào cột B ở dòng đầu tiên
    """
    client = get_gsheet_client()
    if client is None:
        return False

    try:
        spreadsheet = client.open_by_key(GSHEET_SPREADSHEET_ID)
        sheet = get_or_create_quarter_sheet(spreadsheet)

        # Lấy vùng dữ liệu (row 10 đến row 39)
        data_range = sheet.get(f"A{GSHEET_DATA_START_ROW}:D{GSHEET_DATA_END_ROW}")

        # Tìm dòng trống đầu tiên trong vùng data
        next_row = GSHEET_DATA_START_ROW
        for i, row in enumerate(data_range):
            if len(row) >= 3 and (row[2].strip() or (len(row) >= 4 and str(row[3]).strip())):
                next_row = GSHEET_DATA_START_ROW + i + 1
            else:
                break
        else:
            next_row = GSHEET_DATA_START_ROW + len(data_range)

        # Kiểm tra ngày hôm nay đã xuất hiện trong cột B chưa
        col_b_values = [row[1] if len(row) > 1 else "" for row in data_range]
        date_already_exists = date_str in col_b_values

        # Chuẩn bị dữ liệu
        amount_full = amount_k * 1000  # Chuyển từ nghìn sang đầy đủ
        if date_already_exists:
            sheet.update(values=[[product.upper()]], range_name=f"C{next_row}")
            sheet.update(values=[[amount_full]], range_name=f"D{next_row}")
        else:
            sheet.update(values=[[date_str]], range_name=f"B{next_row}")
            sheet.update(values=[[product.upper()]], range_name=f"C{next_row}")
            sheet.update(values=[[amount_full]], range_name=f"D{next_row}")

        logger.info(f"Google Sheets [{get_quarter_sheet_name()}]: row {next_row} - {product.upper()} - {amount_full}")
        return True
    except Exception as e:
        logger.error(f"Lỗi đẩy lên Google Sheets: {e}")
        return False


def delete_last_from_gsheet(product: str, amount_k: int):
    """
    Xóa dòng khớp sản phẩm + số tiền trong Google Sheet (tìm từ dưới lên).
    """
    client = get_gsheet_client()
    if client is None:
        return False

    try:
        spreadsheet = client.open_by_key(GSHEET_SPREADSHEET_ID)
        sheet = get_or_create_quarter_sheet(spreadsheet)
        data_range = sheet.get(f"A{GSHEET_DATA_START_ROW}:D{GSHEET_DATA_END_ROW}")

        amount_full = str(amount_k * 1000)
        target_product = product.upper().strip()

        # Tìm từ dưới lên dòng khớp sản phẩm + số tiền
        target_row = None
        for i in range(len(data_range) - 1, -1, -1):
            row = data_range[i]
            if len(row) >= 4:
                row_product = row[2].strip().upper()
                row_amount = str(row[3]).strip().replace(',', '').replace('.', '')
                # So khớp: sản phẩm giống và số tiền giống
                if row_product == target_product and row_amount == amount_full:
                    target_row = GSHEET_DATA_START_ROW + i
                    break

        if target_row is None:
            # Fallback: xóa dòng cuối cùng có data
            for i in range(len(data_range) - 1, -1, -1):
                row = data_range[i]
                if len(row) >= 3 and (row[2].strip() or (len(row) >= 4 and str(row[3]).strip())):
                    target_row = GSHEET_DATA_START_ROW + i
                    break

        if target_row is None:
            logger.info("Google Sheets: Không có dòng nào để xóa.")
            return False

        sheet.update(values=[['', '', '', '']], range_name=f"A{target_row}:D{target_row}")
        logger.info(f"Google Sheets [{get_quarter_sheet_name()}]: Đã xóa row {target_row} ({target_product} - {amount_full})")
        return True
    except Exception as e:
        logger.error(f"Lỗi xóa trên Google Sheets: {e}")
        return False


# ─── Inventory (Tồn Kho) ─────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Bỏ dấu tiếng Việt + lowercase để so khớp."""
    from unidecode import unidecode
    return unidecode(text).strip().lower()


def get_inventory_sheet():
    """Lấy sheet Tồn Kho."""
    client = get_gsheet_client()
    if client is None:
        return None
    try:
        spreadsheet = client.open_by_key(GSHEET_SPREADSHEET_ID)
        return spreadsheet.worksheet(GSHEET_INVENTORY_SHEET)
    except Exception as e:
        logger.error(f"Lỗi mở sheet Tồn Kho: {e}")
        return None


def find_inventory_product(product_input: str):
    """
    Tìm sản phẩm trong sheet Tồn Kho bằng cách so khớp không dấu.
    Trả về list các match: [(row_index, tên_gốc, số_lượng, đơn_vị), ...]
    """
    sheet = get_inventory_sheet()
    if sheet is None:
        return []

    all_data = sheet.get_all_values()
    input_norm = _normalize(product_input)
    matches = []

    for i, row in enumerate(all_data[1:], start=2):  # Bỏ header row 1
        if len(row) < 3:
            continue
        product_name = row[1].strip()
        if not product_name:
            continue
        product_norm = _normalize(product_name)

        # Khớp chính xác (bỏ dấu)
        if product_norm == input_norm:
            qty = int(row[2]) if row[2].strip().isdigit() else 0
            unit = row[3].strip() if len(row) > 3 else ""
            return [(i, product_name, qty, unit)]  # Exact match → return ngay

        # Khớp một phần (input nằm trong tên SP)
        if input_norm in product_norm or product_norm in input_norm:
            qty = int(row[2]) if row[2].strip().isdigit() else 0
            unit = row[3].strip() if len(row) > 3 else ""
            matches.append((i, product_name, qty, unit))

    return matches


def update_inventory_qty(row_index: int, new_qty: int):
    """Cập nhật số lượng tồn kho tại row_index."""
    sheet = get_inventory_sheet()
    if sheet is None:
        return False
    try:
        sheet.update(values=[[new_qty]], range_name=f"C{row_index}")
        return True
    except Exception as e:
        logger.error(f"Lỗi cập nhật tồn kho: {e}")
        return False


# ─── Database ─────────────────────────────────────────────────────────
DB_PATH = os.path.join(BASE_DIR, "revenue.db")


def init_db():
    """Tạo database và bảng sales nếu chưa tồn tại."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            product    TEXT    NOT NULL,
            amount     INTEGER NOT NULL,
            quantity   INTEGER NOT NULL DEFAULT 1,
            date       TEXT    NOT NULL,
            created_at TEXT    NOT NULL
        )
        """
    )
    # Thêm cột quantity nếu chưa có (migrate)
    try:
        cur.execute("ALTER TABLE sales ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    # Bảng lưu lịch sử nhập kho
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS imports_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            product    TEXT    NOT NULL,
            quantity   INTEGER NOT NULL,
            created_at TEXT    NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()
    logger.info(f"Database ready: {DB_PATH}")


def add_sale(product: str, amount: int, quantity: int = 1) -> int:
    """Thêm 1 giao dịch mới. Trả về id."""
    now = datetime.now(TZ)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sales (product, amount, quantity, date, created_at) VALUES (?, ?, ?, ?, ?)",
        (product.upper(), amount, quantity, now.strftime("%Y-%m-%d"), now.isoformat()),
    )
    conn.commit()
    sale_id = cur.lastrowid
    conn.close()
    return sale_id


def delete_last_sale() -> dict | None:
    """Xóa giao dịch cuối cùng. Trả về thông tin giao dịch bị xóa, hoặc None."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, product, amount, quantity, date FROM sales ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    if row is None:
        conn.close()
        return None
    sale_id, product, amount, quantity, date = row
    cur.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
    conn.commit()
    conn.close()
    return {"id": sale_id, "product": product, "amount": amount, "quantity": quantity, "date": date}


def get_sales_by_date(date_str: str) -> list:
    """Lấy danh sách giao dịch theo ngày (YYYY-MM-DD)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, product, amount, created_at FROM sales WHERE date = ? ORDER BY id",
        (date_str,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_sales_between(start_date: str, end_date: str) -> list:
    """Lấy giao dịch trong khoảng ngày (inclusive)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, product, amount, date, created_at FROM sales WHERE date BETWEEN ? AND ? ORDER BY date, id",
        (start_date, end_date),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


# ─── Helpers ──────────────────────────────────────────────────────────

def format_vnd(amount_k: int) -> str:
    """Format số tiền từ đơn vị nghìn VND sang chuỗi đẹp."""
    full = amount_k * 1000
    return f"{full:,.0f}".replace(",", ".")


def build_report(rows: list, title: str) -> str:
    """Tạo báo cáo từ danh sách giao dịch."""
    if not rows:
        return f"{title}\n\n📭 Không có giao dịch nào."

    # Gom theo sản phẩm
    summary: dict[str, dict] = {}
    for row in rows:
        # row format có thể là (id, product, amount, created_at) hoặc (id, product, amount, date, created_at)
        product = row[1]
        amount = row[2]
        if product not in summary:
            summary[product] = {"count": 0, "total": 0}
        summary[product]["count"] += 1
        summary[product]["total"] += amount

    # Sắp xếp theo tổng tiền giảm dần
    sorted_products = sorted(summary.items(), key=lambda x: x[1]["total"], reverse=True)

    lines = [title, ""]
    total_count = 0
    total_amount = 0
    for product, data in sorted_products:
        lines.append(f"📦 {product}: {data['count']} đơn — {format_vnd(data['total'])} VND")
        total_count += data["count"]
        total_amount += data["total"]

    lines.append("─" * 28)
    lines.append(f"💰 TỔNG: {total_count} đơn — {format_vnd(total_amount)} VND")

    return "\n".join(lines)


def build_detail_report(rows: list, title: str) -> str:
    """Tạo báo cáo chi tiết từng giao dịch."""
    if not rows:
        return f"{title}\n\n📭 Không có giao dịch nào."

    lines = [title, ""]
    total = 0
    for i, row in enumerate(rows, 1):
        product = row[1]
        amount = row[2]
        # Lấy thời gian created_at (field cuối)
        created_at_str = row[-1]
        try:
            created_at = datetime.fromisoformat(created_at_str)
            time_str = created_at.strftime("%H:%M")
        except Exception:
            time_str = "—"
        lines.append(f"  {i}. {product} — {format_vnd(amount)} VND ({time_str})")
        total += amount

    lines.append("")
    lines.append("─" * 28)
    lines.append(f"💰 TỔNG: {len(rows)} đơn — {format_vnd(total)} VND")

    return "\n".join(lines)


# ─── Handlers ─────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lệnh /start"""
    logger.info(f"[DEBUG] /start from chat_id={update.effective_chat.id}, user={update.effective_user.id if update.effective_user else 'N/A'}")
    await update.message.reply_text(
        "🧰 <b>REVENUE BOT</b> — Doanh thu & Quản lý kho\n\n"
        "📝 <b>Ghi doanh thu:</b>\n"
        "  <code>tên SP số tiền</code> (SL=1)\n"
        "  <code>tên SP số_lượng số_tiền</code>\n\n"
        "📦 <b>Quản lý kho:</b>\n"
        "  /nhap — Nhập hàng vào kho\n"
        "  /tonkho — Xem tồn kho\n"
        "  /xoanhap — Xóa/trừ kho\n\n"
        "📊 <b>Báo cáo:</b>\n"
        "  /today — Hôm nay\n"
        "  /tuan — Tuần này\n"
        "  /thang — Tháng này\n\n"
        "  /help — Hướng dẫn chi tiết",
        parse_mode="HTML",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lệnh /help"""
    await update.message.reply_text(
        "📖 <b>HƯỚNG DẪN SỬ DỤNG</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ <b>Ghi doanh thu:</b>\n"
        "  <code>tên SP số tiền</code> → SL = 1\n"
        "  <code>tên SP số_lượng số_tiền</code>\n\n"
        "  Ví dụ:\n"
        "  • <code>mdf 200</code> → 1 MDF, 200k\n"
        "  • <code>van ep 12 ly 2 500</code> → 2 tấm, 500k\n"
        "  • <code>keo 1tr5</code> → 1 keo, 1.500k\n"
        "  ⚠️ Số tiền tính theo <b>nghìn VND</b>\n"
        "  📌 Gõ không dấu cũng nhận (tự khớp tồn kho)\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "2️⃣ <b>Xem doanh thu:</b>\n"
        "  /today — Hôm nay (chi tiết)\n"
        "  /tuan — Tuần này\n"
        "  /thang — Tháng này\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "3️⃣ <b>Quản lý kho:</b>\n"
        "  /nhap <code>tên SP số lượng</code>\n"
        "  • <code>/nhap van ep 12 ly 50</code> → +50 tấm\n"
        "  • SP chưa có → tự thêm mới vào kho\n\n"
        "  /tonkho — Xem toàn bộ tồn kho\n"
        "  /tonkho <code>tên SP</code> — Tìm SP\n\n"
        "  /xoanhap — Undo lần nhập cuối\n"
        "  /xoanhap <code>tên SP số lượng</code> — Trừ kho\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "4️⃣ <b>Xóa giao dịch:</b>\n"
        "  /xoa — Xóa đơn cuối + hoàn kho\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "5️⃣ <b>Báo cáo tự động:</b>\n"
        "  Tổng kết ngày hôm trước gửi lúc <b>5:30 sáng</b>",
        parse_mode="HTML",
    )


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lệnh /today — xem doanh thu hôm nay chi tiết."""
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    today_display = datetime.now(TZ).strftime("%d/%m/%Y")
    rows = get_sales_by_date(today)
    report = build_detail_report(rows, f"📊 <b>DOANH THU HÔM NAY</b> ({today_display})")
    await update.message.reply_text(report, parse_mode="HTML")


async def week_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lệnh /tuan — xem doanh thu tuần này."""
    now = datetime.now(TZ)
    # Thứ 2 đầu tuần
    start_of_week = now - timedelta(days=now.weekday())
    start_str = start_of_week.strftime("%Y-%m-%d")
    end_str = now.strftime("%Y-%m-%d")
    display_range = f"{start_of_week.strftime('%d/%m')} → {now.strftime('%d/%m/%Y')}"

    rows = get_sales_between(start_str, end_str)
    report = build_report(rows, f"📊 <b>DOANH THU TUẦN NÀY</b> ({display_range})")
    await update.message.reply_text(report, parse_mode="HTML")


async def month_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lệnh /thang — xem doanh thu tháng này."""
    now = datetime.now(TZ)
    start_str = now.strftime("%Y-%m-01")
    end_str = now.strftime("%Y-%m-%d")
    display = f"Tháng {now.month}/{now.year}"

    rows = get_sales_between(start_str, end_str)
    report = build_report(rows, f"📊 <b>DOANH THU {display.upper()}</b>")
    await update.message.reply_text(report, parse_mode="HTML")


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lệnh /xoa — xóa giao dịch cuối cùng + hoàn kho."""
    deleted = delete_last_sale()
    if deleted is None:
        await update.message.reply_text("📭 Không có giao dịch nào để xóa.")
        return

    # Xóa trên Google Sheets
    try:
        import asyncio
        await asyncio.to_thread(delete_last_from_gsheet, deleted['product'], deleted['amount'])
    except Exception as e:
        logger.error(f"Lỗi xóa Google Sheets (non-blocking): {e}")

    # Hoàn kho
    inventory_msg = ""
    try:
        import asyncio
        def _restore_inventory():
            matches = find_inventory_product(deleted['product'])
            if matches:
                row_idx, name, old_qty, unit = matches[0]
                new_qty = old_qty + deleted.get('quantity', 1)
                update_inventory_qty(row_idx, new_qty)
                return f"\n  📦 Hoàn kho: {name} +{deleted.get('quantity', 1)} → {new_qty} {unit}"
            return ""
        inventory_msg = await asyncio.to_thread(_restore_inventory)
    except Exception as e:
        logger.error(f"Lỗi hoàn kho: {e}")

    date_display = datetime.strptime(deleted["date"], "%Y-%m-%d").strftime("%d/%m/%Y")
    await update.message.reply_text(
        f"🗑 <b>Đã xóa giao dịch:</b>\n"
        f"  📦 Sản phẩm: {deleted['product']}\n"
        f"  💰 Số tiền: {format_vnd(deleted['amount'])} VND\n"
        f"  📅 Ngày: {date_display}{inventory_msg}",
        parse_mode="HTML",
    )


def _parse_amount(amount_str: str) -> int | None:
    """Parse số tiền hỗ trợ format: 200, 1trieu, 1tr5, 1.5trieu..."""
    amount_str = amount_str.lower().strip()
    trieu_match = re.match(r'^(\d+(?:[.,]\d+)?)\s*(trieu|tr)(\d+)?$', amount_str)
    if trieu_match:
        whole = float(trieu_match.group(1).replace(",", "."))
        fraction = trieu_match.group(3)
        if fraction:
            decimal = int(fraction) / (10 ** len(fraction))
            whole += decimal
        return int(whole * 1000)
    try:
        val = int(float(amount_str.replace(",", ".")))
        return val if val > 0 else None
    except ValueError:
        return None


async def handle_revenue_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Xử lý tin nhắn dạng:
      <tên SP> <số lượng> <số tiền>   (ví dụ: van ep 12 ly 2 500)
      <tên SP> <số tiền>              (ví dụ: mdf 200 → SL=1)
    """
    text = update.message.text.strip()
    if not text:
        return

    parts = text.split()
    if len(parts) < 2:
        return

    # Thử parse: 2 số cuối = SL + Tiền, hoặc 1 số cuối = Tiền (SL=1)
    amount_str = parts[-1].lower()
    amount_k = _parse_amount(amount_str)
    if amount_k is None:
        return  # Số cuối không phải số → bỏ qua

    quantity = 1
    product_name = " ".join(parts[:-1])

    # Kiểm tra phần tử áp chót có phải số lượng không
    if len(parts) >= 3:
        maybe_qty = parts[-2]
        if maybe_qty.isdigit() and int(maybe_qty) > 0:
            # Kiểm tra: nếu bỏ 2 phần tử cuối, còn lại có phải tên SP không?
            potential_name = " ".join(parts[:-2])
            if potential_name:  # Còn tên SP
                quantity = int(maybe_qty)
                product_name = potential_name

    # Khớp tên SP với tồn kho (không dấu)
    inventory_msg = ""
    matched_name = product_name  # Tên gốc (có dấu) nếu khớp được
    try:
        import asyncio
        def _match_and_deduct():
            nonlocal matched_name
            matches = find_inventory_product(product_name)
            if len(matches) == 1:
                row_idx, name, old_qty, unit = matches[0]
                matched_name = name
                new_qty = old_qty - quantity
                update_inventory_qty(row_idx, max(new_qty, 0))
                if new_qty < 0:
                    return f"\n  ⚠️ <b>Tồn kho không đủ!</b> Còn: {old_qty} {unit}, Bán: {quantity}"
                return f"\n  📦 Tồn kho: {name} còn {new_qty} {unit}"
            elif len(matches) > 1:
                lines = [f"\n  ⚠️ Nhiều SP khớp '{product_name}':"]
                for _, name, qty, unit in matches[:5]:
                    lines.append(f"    • {name} ({qty} {unit})")
                return "\n".join(lines)
            return ""  # Không tìm thấy trong kho → bỏ qua
        inventory_msg = await asyncio.to_thread(_match_and_deduct)
    except Exception as e:
        logger.error(f"Lỗi kiểm tra tồn kho: {e}")

    # Ghi vào database (dùng tên có dấu nếu khớp được)
    sale_id = add_sale(matched_name, amount_k, quantity)

    # Đẩy lên Google Sheets
    date_for_sheet = datetime.now(TZ).strftime("%d/%m/%Y")
    display_product = f"{matched_name.upper()} x{quantity}" if quantity > 1 else matched_name.upper()
    try:
        import asyncio
        await asyncio.to_thread(push_to_gsheet, display_product, amount_k, date_for_sheet)
    except Exception as e:
        logger.error(f"Lỗi push Google Sheets (non-blocking): {e}")

    # Lấy tổng doanh thu hôm nay
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    today_rows = get_sales_by_date(today)
    today_total = sum(row[2] for row in today_rows)
    today_count = len(today_rows)

    date_display = datetime.now(TZ).strftime("%d/%m/%Y")
    qty_text = f" × {quantity}" if quantity > 1 else ""

    await update.message.reply_text(
        f"✅ <b>Đã ghi nhận!</b>\n\n"
        f"  📦 Sản phẩm: <b>{matched_name.upper()}{qty_text}</b>\n"
        f"  💰 Số tiền: <b>{format_vnd(amount_k)} VND</b>\n"
        f"  📅 Ngày: <b>{date_display}</b>{inventory_msg}\n\n"
        f"📈 Hôm nay: {today_count} đơn — <b>{format_vnd(today_total)} VND</b>",
        parse_mode="HTML",
    )
    logger.info(f"Sale #{sale_id}: {matched_name.upper()}{qty_text} - {format_vnd(amount_k)} VND")


async def nhap_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Lệnh /nhap — nhập hàng vào kho.
    Ví dụ: /nhap van ep 12 ly 50
    """
    if not context.args:
        await update.message.reply_text(
            "📥 <b>Nhập hàng:</b>\n"
            "  /nhap <tên SP> <số lượng>\n"
            "  Ví dụ: /nhap van ep 12 ly 50",
            parse_mode="HTML",
        )
        return

    parts = context.args
    if len(parts) < 2:
        await update.message.reply_text("⚠️ Cần ít nhất: /nhap <tên SP> <số lượng>")
        return

    qty_str = parts[-1]
    if not qty_str.isdigit() or int(qty_str) <= 0:
        await update.message.reply_text("⚠️ Số lượng phải là số nguyên dương.")
        return

    qty = int(qty_str)
    product_input = " ".join(parts[:-1])

    try:
        import asyncio
        def _do_nhap():
            matches = find_inventory_product(product_input)
            if len(matches) == 1:
                row_idx, name, old_qty, unit = matches[0]
                new_qty = old_qty + qty
                update_inventory_qty(row_idx, new_qty)
                # Lưu lịch sử nhập kho
                conn = sqlite3.connect(DB_PATH)
                conn.execute(
                    "INSERT INTO imports_log (product, quantity, created_at) VALUES (?, ?, ?)",
                    (name, qty, datetime.now(TZ).isoformat()),
                )
                conn.commit()
                conn.close()
                return (
                    f"📥 <b>Đã nhập hàng!</b>\n\n"
                    f"  📦 {name}: +{qty} {unit}\n"
                    f"  📦 Tồn kho: <b>{new_qty} {unit}</b>"
                )
            elif len(matches) > 1:
                lines = [f"⚠️ Nhiều SP khớp '{product_input}':"]
                for _, name, q, unit in matches[:5]:
                    lines.append(f"  • {name} ({q} {unit})")
                lines.append("\nGõ chính xác hơn để chọn.")
                return "\n".join(lines)
            else:
                # SP chưa có → thêm mới vào sheet Tồn Kho
                sheet = get_inventory_sheet()
                if sheet is None:
                    return f"❌ Không thể mở sheet Tồn Kho."
                all_data = sheet.get_all_values()
                next_stt = len(all_data)  # STT tiếp theo
                new_row = next_stt + 1
                product_title = product_input.title()  # viết hoa đầu mỗi từ
                sheet.update(values=[[next_stt, product_title, qty, ""]], range_name=f"A{new_row}:D{new_row}")
                # Lưu lịch sử
                conn = sqlite3.connect(DB_PATH)
                conn.execute(
                    "INSERT INTO imports_log (product, quantity, created_at) VALUES (?, ?, ?)",
                    (product_title, qty, datetime.now(TZ).isoformat()),
                )
                conn.commit()
                conn.close()
                return (
                    f"📥 <b>Đã thêm SP mới vào kho!</b>\n\n"
                    f"  📦 {product_title}: {qty}\n"
                    f"  ⚠️ Chưa có đơn vị — vào Sheet bổ sung nếu cần"
                )
        result = await asyncio.to_thread(_do_nhap)
        await update.message.reply_text(result, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Lỗi nhập hàng: {e}")
        await update.message.reply_text("❌ Lỗi khi nhập hàng.")


async def xoanhap_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Lệnh /xoanhap:
      /xoanhap              → undo lần nhập kho cuối cùng
      /xoanhap van ep 10    → trừ 10 ván ép khỏi tồn kho
    """
    if context.args:
        # Mode 2: trừ số lượng cụ thể
        parts = context.args
        qty_str = parts[-1]
        if not qty_str.isdigit() or int(qty_str) <= 0:
            await update.message.reply_text("⚠️ Format: /xoanhap <tên SP> <số lượng>\nVí dụ: /xoanhap van ep 12 ly 10")
            return

        qty = int(qty_str)
        product_input = " ".join(parts[:-1])
        if not product_input:
            await update.message.reply_text("⚠️ Cần tên sản phẩm: /xoanhap <tên SP> <số lượng>")
            return

        try:
            import asyncio
            def _deduct():
                matches = find_inventory_product(product_input)
                if len(matches) == 1:
                    row_idx, name, old_qty, unit = matches[0]
                    new_qty = max(old_qty - qty, 0)
                    update_inventory_qty(row_idx, new_qty)
                    return (
                        f"🗑 <b>Đã trừ tồn kho:</b>\n"
                        f"  📦 {name}: {old_qty} → <b>{new_qty} {unit}</b> (-{qty})"
                    )
                elif len(matches) > 1:
                    lines = [f"⚠️ Nhiều SP khớp '{product_input}':"]
                    for _, name, q, unit in matches[:5]:
                        lines.append(f"  • {name} ({q} {unit})")
                    lines.append("\nGõ chính xác hơn.")
                    return "\n".join(lines)
                else:
                    return f"❌ Không tìm thấy SP '{product_input}' trong kho."
            result = await asyncio.to_thread(_deduct)
            await update.message.reply_text(result, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Lỗi trừ tồn kho: {e}")
            await update.message.reply_text("❌ Lỗi khi trừ tồn kho.")
        return

    # Mode 1: undo lần nhập cuối
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, product, quantity FROM imports_log ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    if row is None:
        conn.close()
        await update.message.reply_text("📭 Không có lần nhập kho nào để xóa.")
        return

    imp_id, product, qty = row
    cur.execute("DELETE FROM imports_log WHERE id = ?", (imp_id,))
    conn.commit()
    conn.close()

    inventory_msg = ""
    try:
        import asyncio
        def _undo_nhap():
            matches = find_inventory_product(product)
            if matches:
                row_idx, name, old_qty, unit = matches[0]
                new_qty = max(old_qty - qty, 0)
                update_inventory_qty(row_idx, new_qty)
                return f"\n  📦 {name}: -{qty} → còn {new_qty} {unit}"
            return ""
        inventory_msg = await asyncio.to_thread(_undo_nhap)
    except Exception as e:
        logger.error(f"Lỗi undo nhập kho: {e}")

    await update.message.reply_text(
        f"🗑 <b>Đã xóa lần nhập kho cuối:</b>\n"
        f"  📦 {product}: -{qty}{inventory_msg}",
        parse_mode="HTML",
    )


async def tonkho_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Lệnh /tonkho — xem tồn kho.
    /tonkho        → xem tất cả
    /tonkho van ep → tìm sản phẩm
    """
    try:
        import asyncio
        def _get_inventory():
            sheet = get_inventory_sheet()
            if sheet is None:
                return "❌ Không thể đọc sheet Tồn Kho."

            all_data = sheet.get_all_values()
            if len(all_data) <= 1:
                return "📭 Kho trống."

            search = " ".join(context.args).strip() if context.args else ""
            search_norm = _normalize(search) if search else ""

            lines = []
            for row in all_data[1:]:
                if len(row) < 3 or not row[1].strip():
                    continue
                name = row[1].strip()
                qty = row[2].strip()
                unit = row[3].strip() if len(row) > 3 else ""

                if search_norm and search_norm not in _normalize(name):
                    continue

                qty_int = int(qty) if qty.isdigit() else 0
                if qty_int <= 0:
                    emoji = "🔴"
                elif qty_int <= 10:
                    emoji = "🟡"
                else:
                    emoji = "🟢"
                lines.append(f"{emoji} {name}: <b>{qty}</b> {unit}")

            if not lines:
                return f"❌ Không tìm thấy SP '{search}' trong kho." if search else "📭 Kho trống."

            header = f"📦 <b>TỒN KHO</b>" + (f" — tìm '{search}'" if search else f" ({len(lines)} SP)")
            return header + "\n\n" + "\n".join(lines)

        result = await asyncio.to_thread(_get_inventory)
        await update.message.reply_text(result, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Lỗi xem tồn kho: {e}")
        await update.message.reply_text("❌ Lỗi khi đọc tồn kho.")


# ─── Scheduled Jobs ──────────────────────────────────────────────────

async def send_daily_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Job chạy vào 6:00 AM mỗi ngày.
    Gửi tổng kết doanh thu ngày hôm trước.
    """
    yesterday = datetime.now(TZ) - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")
    yesterday_display = yesterday.strftime("%d/%m/%Y")

    rows = get_sales_by_date(yesterday_str)

    if not rows:
        # Vẫn gửi thông báo nếu không có đơn
        msg = (
            f"📊 <b>BÁO CÁO DOANH THU NGÀY {yesterday_display}</b>\n\n"
            f"📭 Không có giao dịch nào trong ngày."
        )
    else:
        # Gom theo sản phẩm
        summary: dict[str, dict] = {}
        for row in rows:
            product = row[1]
            amount = row[2]
            if product not in summary:
                summary[product] = {"count": 0, "total": 0}
            summary[product]["count"] += 1
            summary[product]["total"] += amount

        sorted_products = sorted(summary.items(), key=lambda x: x[1]["total"], reverse=True)

        lines = [f"📊 <b>BÁO CÁO DOANH THU NGÀY {yesterday_display}</b>", ""]
        total_count = 0
        total_amount = 0
        for product, data in sorted_products:
            lines.append(f"📦 {product}: {data['count']} đơn — {format_vnd(data['total'])} VND")
            total_count += data["count"]
            total_amount += data["total"]

        lines.append("─" * 28)
        lines.append(f"💰 <b>TỔNG: {total_count} đơn — {format_vnd(total_amount)} VND</b>")
        msg = "\n".join(lines)

    try:
        await context.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")
        # Lưu ngày đã gửi báo cáo
        _save_last_report_date(yesterday_str)
        logger.info(f"Đã gửi báo cáo doanh thu ngày {yesterday_display}")
    except Exception as e:
        logger.error(f"Lỗi gửi báo cáo tự động: {e}")


LAST_REPORT_FILE = os.path.join(BASE_DIR, ".last_report_date")


def _save_last_report_date(date_str: str):
    """Lưu ngày báo cáo cuối cùng."""
    with open(LAST_REPORT_FILE, "w") as f:
        f.write(date_str)


def _get_last_report_date() -> str:
    """Lấy ngày báo cáo cuối cùng."""
    try:
        with open(LAST_REPORT_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


async def check_missed_report(app: Application) -> None:
    """
    Kiểm tra khi bot khởi động: nếu chưa gửi báo cáo ngày hôm qua → gửi luôn.
    """
    if not CHAT_ID:
        return

    yesterday = datetime.now(TZ) - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")
    last_report = _get_last_report_date()

    if last_report >= yesterday_str:
        logger.info(f"Báo cáo ngày {yesterday_str} đã gửi rồi. Bỏ qua.")
        return

    logger.info(f"Phát hiện chưa gửi báo cáo ngày {yesterday_str}. Đang gửi...")
    # Tạo fake context để gọi send_daily_report
    class FakeContext:
        bot = app.bot
    await send_daily_report(FakeContext())


# ─── Main ─────────────────────────────────────────────────────────────

def main() -> None:
    if not BOT_TOKEN:
        print("❌ Chưa cấu hình REVENUE_BOT_TOKEN trong file .env!")
        print("   Vào @BotFather tạo bot mới và lấy token.")
        sys.exit(1)

    if not CHAT_ID:
        print("⚠️  Chưa cấu hình REVENUE_CHAT_ID (hoặc CHAT_ID) trong file .env!")
        print("   Bot vẫn chạy nhưng sẽ không giới hạn user và không gửi báo cáo tự động.")

    # Khởi tạo database
    init_db()

    print("[Revenue Bot] Dang khoi dong...")

    app = Application.builder().token(BOT_TOKEN).build()

    # ── Kiểm tra báo cáo bị lỡ khi khởi động ──
    app.post_init = check_missed_report

    # ── Error handler ──
    async def error_handler(update, context):
        logger.error(f"Exception: {context.error}")
    app.add_error_handler(error_handler)

    # ── Command handlers ──
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("tuan", week_command))
    app.add_handler(CommandHandler("thang", month_command))
    app.add_handler(CommandHandler("xoa", delete_command))
    app.add_handler(CommandHandler("nhap", nhap_command))
    app.add_handler(CommandHandler("xoanhap", xoanhap_command))
    app.add_handler(CommandHandler("tonkho", tonkho_command))

    # ── Message handler: bắt text thường (không phải command) ──
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_revenue_message)
    )

    # ── Scheduled job: báo cáo 5:30 AM mỗi ngày ──
    job_queue = app.job_queue
    job_queue.run_daily(
        send_daily_report,
        time=dtime(hour=5, minute=30, second=0, tzinfo=TZ),
        name="daily_revenue_report",
    )
    logger.info("Scheduled: Báo cáo doanh thu hàng ngày lúc 05:30 AM (Asia/Ho_Chi_Minh)")

    print("[Revenue Bot] Da san sang! Nhan Ctrl-C de dung.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
