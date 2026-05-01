import sys
sys.stdout.reconfigure(encoding='utf-8')
import gspread

gc = gspread.service_account(filename='gsheet_credentials.json')
sp = gc.open_by_key('1cKWKCAin6JVQmSzyM5wjK5o30t-eGFAgs_lc3Kf6pV0')

# Tạo sheet Tồn Kho
try:
    ws = sp.worksheet("Tồn Kho")
    print("Sheet 'Tồn Kho' đã tồn tại")
except:
    ws = sp.add_worksheet(title="Tồn Kho", rows=100, cols=4)
    print("Đã tạo sheet 'Tồn Kho'")

# Header
ws.update(values=[["STT", "Tên hàng hóa", "Số lượng", "Đơn vị"]], range_name="A1:D1")

# Import data từ ảnh user cung cấp
products = [
    [1, "Ván ép 18 ly", 170, "Tấm"],
    [2, "Ván ép 12 ly", 70, "Tấm"],
    [3, "Ván ép 8 ly", 60, "Tấm"],
    [4, "V lỗ 3 ly (hoặc V)", 100, "Tấm"],
    [5, "Nhựa Đài Loan", 76, "Tấm"],
    [6, "Đinh vít đủ cỡ", 148, "Bịch"],
    [7, "Bánh xe đại cỡ", 180, "Bánh"],
    [8, "Đinh chỉ", 30, "Kg"],
    [9, "Ray kéo tủ", 300, "Kg"],
    [10, "Bản lề", 140, "Kg"],
    [11, "Giấy nhám", 900, "Tép"],
    [12, "Cây gỗ", 105, "Bó"],
    [13, "Cửa nhựa các loại", 10, "Cái"],
    [14, "Cửa nhựa xếp", 30, "Cái"],
    [15, "Lưới nhựa", 180, "Kg"],
    [16, "Xốp trắng", 168, "Tấm"],
    [17, "Đề can giấy dán", 18, "Cuộn"],
    [18, "Đề can dán kính", 10, "Cuộn"],
    [19, "SiliLy (Silicon)", 15, "Cây"],
    [20, "Chỉ dán 4F", 65, "Cuộn"],
    [21, "Chỉ dán 2F", 78, "Cuộn"],
    [22, "Băng keo trong", 38, "Cuộn"],
    [23, "Băng keo giấy", 100, "Cuộn"],
    [24, "Thạch cao 60x1", 110, "Tấm"],
    [25, "Thạch cao 12x2", 60, "Tấm"],
    [26, "Ván nhựa e có 1", 60, "Tấm"],
    [27, "Ván nhựa e có 1", 45, "Tấm"],
    [28, "Pom Mác 3 ly", 80, "Tấm"],
    [29, "Pom Mác 5 ly", 115, "Tấm"],
    [30, "Pom Mác 12 ly", 38, "Tấm"],
    [31, "Ổ khóa các loại", 112, "Cái"],
    [32, "Dây buộc", 20, "Cục"],
    [33, "Dây kẽm", 50, "Kg"],
    [34, "Mũi khoan đủ loại", 1200, "Cái"],
    [35, "Keo sữa", 78, "Bịch"],
    [36, "Chậu nhựa ghép", 200, "Cặp"],
    [37, "Tấm nhựa đủ loại", 90, "Tấm"],
    [38, "Bạt dày hay", 8, "Xắp"],
]

ws.update(values=products, range_name=f"A2:D{len(products)+1}")
print(f"Đã import {len(products)} sản phẩm vào sheet Tồn Kho")
