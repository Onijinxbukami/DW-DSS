# Hướng Dẫn Sử Dụng – DSS Thu Hồi Nợ Ngân Hàng A

> **CO5113 – Data Warehousing & Decision Support Systems**
> Snapshot date: **2024-12-31**

---

## Mục Lục

1. [Cài Đặt & Khởi Động](#1-cài-đặt--khởi-động)
2. [Đăng Nhập](#2-đăng-nhập)
3. [Tab 1 – Collector: Danh Sách Task](#3-tab-1--collector-danh-sách-task)
4. [Tab 2 – Manager: What-If Analysis](#4-tab-2--manager-what-if-analysis)
5. [Tab 3 – Manager: Dashboard](#5-tab-3--manager-dashboard)
6. [Luồng Hoạt Động Tổng Thể](#6-luồng-hoạt-động-tổng-thể)
7. [Tài Khoản Demo](#7-tài-khoản-demo)
8. [Cấu Trúc Thư Mục](#8-cấu-trúc-thư-mục)
9. [Xử Lý Lỗi Thường Gặp](#9-xử-lý-lỗi-thường-gặp)

---

## 1. Cài Đặt & Khởi Động

### Yêu cầu

- Python 3.11+
- PostgreSQL (hoặc Supabase cloud)
- Đã chạy ETL để populate Star Schema và Data Mart

### Bước 1 – Clone & cài thư viện

```bash
cd source
pip install -r requirements.txt
```

### Bước 2 – Cấu hình biến môi trường

Sao chép file mẫu và điền thông tin kết nối database:

```bash
cp .env.example .env
```

Mở `.env` và chỉnh sửa:

```env
# URL kết nối PostgreSQL (ví dụ: Supabase)
DATABASE_URL=postgresql://postgres@db.YOUR-PROJECT-REF.supabase.co:5432/postgres

# Mật khẩu DB (tách riêng để tránh lỗi ký tự đặc biệt)
DB_PASSWORD=your-raw-password-here

# Flask secret key
SECRET_KEY=banka-dss-2024-secret
```

### Bước 3 – Chạy ETL (nếu chưa có dữ liệu)

```bash
python etl/run_etl.py
```

ETL sẽ:
1. Đọc 12 file CSV từ `data/raw/`
2. Chuẩn hóa ngày tháng và branch code
3. Load vào Star Schema (5 dim + 1 fact)
4. Tính DPD, Risk Score, phân bổ collector
5. Ghi `dm_daily_collection_tasks` (snapshot 2024-12-31)

### Bước 4 – Khởi động web app

```bash
python run.py
```

Mở trình duyệt tại: **http://localhost:5000**

---

## 2. Đăng Nhập

Truy cập `http://localhost:5000` — hệ thống tự chuyển đến trang đăng nhập.

| Trường | Mô tả |
|--------|-------|
| **Tên đăng nhập** | `manager` hoặc `COL-001` đến `COL-020` |
| **Mật khẩu** | Xem bảng tài khoản demo bên dưới |

Sau khi đăng nhập:
- **Manager** → chuyển đến Dashboard (có đủ 3 tab)
- **Collector** → chuyển đến Danh Sách Task (chỉ thấy tab của mình)

---

## 3. Tab 1 – Collector: Danh Sách Task

> **Ai dùng:** Nhân viên thu hồi nợ (COL-001 đến COL-020)

### Giao diện tổng quan

```
┌─────────────────────────────────────────────────┐
│  Xin chào, Bui Thu Linh   [===     ] 3/12 task  │
│                                  12 task hôm nay │
├─────────────────────────────────────────────────┤
│ ⬛ #1  Nguyễn Văn An     [FIELD]  🔴 47d  1.2B │
│ 🔴 #2  Trần Thị Bích     [CALL]   🟠 28d  800M │
│ 🟠 #3  Lê Minh Tuấn      [CALL]   🟠 22d  450M │
│ ...                                              │
└─────────────────────────────────────────────────┘
```

### Ý nghĩa màu sắc (thanh màu bên trái mỗi card)

| Màu | DPD | Kênh liên hệ |
|-----|-----|-------------|
| 🟢 Xanh | 0 ngày (đúng hạn) | – |
| 🟡 Vàng | 1–9 ngày | EMAIL |
| 🟠 Cam | 10–19 ngày | SMS |
| 🔴 Đỏ | 20–29 ngày | CALL |
| ⬛ Đen | ≥ 30 ngày | FIELD (thực địa) |

### Số thứ tự ưu tiên (#)

- **#1** = khoản cần liên hệ đầu tiên trong ngày
- Màu đỏ đậm = Top 3, màu cam = Top 10
- Thứ tự dựa trên **Risk Score** tính từ Model 2

### Cập nhật trạng thái task

Mỗi card có dropdown trạng thái:

| Trạng thái | Ý nghĩa |
|-----------|---------|
| ⏳ Chờ | Chưa xử lý (mặc định) |
| 🔄 Đang xử lý | Đang liên hệ khách hàng |
| ✅ Xong | Đã liên hệ thành công |
| ⏭ Bỏ qua | Không liên hệ được hôm nay |

> Thay đổi được lưu ngay lập tức (optimistic UI). Thông báo xác nhận hiện ở góc dưới-phải.

### Xem chi tiết khách hàng

Nhấn nút 👁 ở cuối mỗi card để mở popup gồm:

- **Thông tin liên hệ:** SĐT (nhấn để gọi ngay), email, địa chỉ (nhấn để mở Google Maps)
- **Thông tin hợp đồng:** mã HĐ, sản phẩm, chi nhánh, tổng dư nợ
- **Chỉ số rủi ro:** DPD hiện tại, số kỳ trễ 6 tháng, Max DPD 6 tháng, Risk Score
- **Lịch sử 6 tháng gần nhất:** timeline màu thể hiện PAID / OVERDUE / PARTIAL theo từng kỳ

### Lưu ý cho Collector thực địa (FIELD)

- SĐT là **link gọi điện trực tiếp** — nhấn 1 lần trên điện thoại
- Địa chỉ là **link Google Maps** — mở chỉ đường luôn
- Giao diện tự động **thu gọn** trên màn hình nhỏ

---

## 4. Tab 2 – Manager: What-If Analysis

> **Ai dùng:** Quản lý (tài khoản `manager`)
> Truy cập: Navbar → **What-If**

### Mục đích

Cho phép Manager điều chỉnh trọng số Model 2 (Risk Score) và xem trước tác động lên thứ tự ưu tiên của collector **trước khi áp dụng thật**.

### Panel trái – Điều chỉnh trọng số

| Tham số | Ký hiệu | Ý nghĩa | Mặc định |
|---------|---------|---------|---------|
| Số kỳ trễ 6T | α | Tần suất trễ hạn 6 tháng qua | 20 |
| Max DPD 6T | β | DPD cao nhất trong 6 tháng | 25 |
| DPD hiện tại | γ | DPD của kỳ hiện tại | 0.5 |
| Bậc dư nợ | δ | Mức dư nợ (<100M / 100–500M / 500M–1B / >1B) | 10 |
| Nguồn sản phẩm | ε | Vay thế chấp (cao hơn) vs Thẻ tín dụng | 5 |

Mỗi tham số có **thanh kéo** và **ô nhập số** đồng bộ với nhau.

### Nút "Xem Preview"

1. Nhấn **Xem Preview** sau khi điều chỉnh trọng số
2. Hệ thống tính lại Risk Score với trọng số mới
3. Hiển thị ngay:
   - **3 thẻ tóm tắt:** số task đổi hạng, số task đổi kênh, Δ hạng trung bình
   - **Bảng Top 20:** cột "Hạng cũ → Mới" với mũi tên ↑↓ màu xanh/đỏ
   - **Biểu đồ histogram:** phân bố Risk Score hiện tại (xanh) vs mới (đỏ)

> Preview **không ghi vào database**. Collector chưa bị ảnh hưởng.

> Nếu thay đổi thanh kéo sau khi preview, nút Apply tự **vô hiệu hóa** — cần Preview lại trước.

### Nút "Áp Dụng Cho Hôm Nay"

1. Chỉ bật sau khi đã xem Preview
2. Nhấn → modal xác nhận hiện ra với cảnh báo
3. Nhấn **Xác Nhận Áp Dụng** → hệ thống:
   - Lưu config mới vào bảng `scoring_config`
   - Tính lại Risk Score và priority_rank cho tất cả task hôm nay
   - Collector reload trang sẽ thấy thứ tự mới ngay

---

## 5. Tab 3 – Manager: Dashboard

> **Ai dùng:** Quản lý (tài khoản `manager`)
> Truy cập: Navbar → **Dashboard**

### KPI Cards (4 thẻ trên cùng)

| Thẻ | Ý nghĩa |
|-----|---------|
| 🔴 Hợp đồng quá hạn | Tổng số HĐ có DPD > 0 |
| 🟡 Dư nợ quá hạn | Tổng tiền dư nợ (đơn vị tỷ VNĐ) |
| 🟢 Task hoàn thành | % task đã DONE trong ngày |
| 🔵 Collector hoạt động | Số collector có task hôm nay |

### Biểu đồ hàng 1

- **Phân bố DPD Bucket (cột):** số task thuộc nhóm A/B/C/D — màu khớp với hệ thống màu card
- **Phân bố kênh liên hệ (donut):** tỷ lệ EMAIL / SMS / CALL / FIELD

### Biểu đồ hàng 2

- **Phân bố Risk Score (cột):** phân bổ điểm rủi ro theo dải 0–20, 20–40, 40–60, 60–80, 80–100, 100+
- **Trạng thái task hôm nay (donut):** tỷ lệ DONE / IN_PROGRESS / PENDING / SKIPPED

### Bảng Hiệu Suất Collector

Sắp xếp theo số task hoàn thành (nhiều nhất lên trên):

| Cột | Ý nghĩa |
|-----|---------|
| Được giao | Tổng task hôm nay |
| Đang xử lý | Task đang IN_PROGRESS |
| Hoàn thành | Task DONE (xanh đậm) |
| Bỏ qua | Task SKIPPED |
| Tiến độ | Thanh % (xanh ≥80%, vàng ≥40%, đỏ <40%) |

---

## 6. Luồng Hoạt Động Tổng Thể

```
Buổi sáng (Manager):
  1. Mở Dashboard → kiểm tra KPI tổng quan
  2. Nếu thứ tự ưu tiên chưa phù hợp → mở What-If
  3. Điều chỉnh trọng số → Xem Preview → so sánh thứ tự
  4. Nhấn Áp Dụng → collector reload sẽ thấy thứ tự mới

Trong ngày (Collector):
  5. Đăng nhập → danh sách task đã sắp xếp theo ưu tiên
  6. Gọi/gặp KH theo thứ tự từ #1
  7. Nhấn 👁 để xem SĐT, địa chỉ, lịch sử thanh toán
  8. Cập nhật trạng thái: Đang xử lý → Xong hoặc Bỏ qua

Cuối ngày (Manager):
  9. Quay lại Dashboard → xem % hoàn thành, hiệu suất từng collector
```

---

## 7. Tài Khoản Demo

| Tên đăng nhập | Mật khẩu | Vai trò | Tên |
|--------------|---------|---------|-----|
| `manager` | `admin123` | Manager | Quản Lý |
| `COL-001` | `col001` | Collector | Bui Thu Linh |
| `COL-002` | `col002` | Collector | Nguyen Thi Trang |
| `COL-003` | `col003` | Collector | Dang Quang Chau |
| `COL-004` | `col004` | Collector | Vo Thi Huy |
| `COL-005` | `col005` | Collector | Pham Quang Thao |
| `COL-006` | `col006` | Collector | Tran Thu Trang |
| `COL-007` | `col007` | Collector | Huynh Thanh Dung |
| `COL-008` | `col008` | Collector | Tran Duc Dung |
| `COL-009` | `col009` | Collector | Dang Thanh Chau |
| `COL-010` | `col010` | Collector | Bui Van Hieu |
| `COL-011` | `col011` | Collector | Dang Van Khanh |
| `COL-012` | `col012` | Collector | Phan Minh Hieu |
| `COL-013` | `col013` | Collector | Phan Ngoc Khoa |
| `COL-014` | `col014` | Collector | Nguyen Thi Binh |
| `COL-015` | `col015` | Collector | Bui Hai Trang |
| `COL-016` | `col016` | Collector | Vo Duc Tuan |
| `COL-017` | `col017` | Collector | Phan Duc Binh |
| `COL-018` | `col018` | Collector | Hoang Anh Vy |
| `COL-019` | `col019` | Collector | Nguyen Quang Tuan |
| `COL-020` | `col020` | Collector | Tran Thu Linh |

---

## 8. Cấu Trúc Thư Mục

```
source/
├── data/
│   └── raw/                  # 12 file CSV đầu vào
│       ├── cb_customer.csv
│       ├── cb_mortgage_loan.csv
│       ├── cb_loan_schedule.csv
│       ├── cb_payment_transaction.csv
│       ├── cc_user.csv
│       ├── cc_card_account.csv
│       ├── cc_card_statement.csv
│       ├── cc_card_payment.csv
│       ├── collector_staff.csv
│       ├── branch_master.csv
│       ├── branch_raw_codes.csv
│       └── scoring_config_initial.csv
│
├── etl/
│   ├── run_etl.py            # Entry point ETL
│   ├── load_dimensions.py    # Load 5 dim tables
│   ├── load_fact.py          # Load fact_debt_installment
│   └── utils.py              # parse_dirty_date(), branch mapping
│
├── models/
│   ├── model1_channel.py     # DPD → kênh liên hệ
│   ├── model2_risk_score.py  # Risk Score formula
│   └── assign_collectors.py  # Round-robin phân bổ collector
│
├── mart/
│   └── build_mart.py         # Tạo dm_daily_collection_tasks
│
├── app/
│   ├── __init__.py           # Flask app factory
│   ├── auth.py               # Login / logout / role guard
│   ├── db.py                 # PostgreSQL connection helper
│   ├── routes/
│   │   ├── collector.py      # /tasks, /update_status, /task_detail
│   │   └── manager.py        # /dashboard, /whatif, /whatif/preview, /whatif/apply
│   ├── templates/
│   │   ├── base.html         # Layout + navbar
│   │   ├── login.html
│   │   ├── collector/tasks.html
│   │   └── manager/
│   │       ├── dashboard.html
│   │       └── whatif.html
│   └── static/
│       ├── css/style.css
│       └── js/
│           ├── collector.js
│           ├── whatif.js
│           └── dashboard.js
│
├── config.py                 # DATABASE_URL, SNAPSHOT_DATE, SECRET_KEY
├── .env                      # Biến môi trường (git-ignored)
├── .env.example              # Mẫu cấu hình
├── requirements.txt
└── run.py                    # Khởi động Flask
```

---

## 9. Xử Lý Lỗi Thường Gặp

### Lỗi kết nối database khi khởi động

```
KeyError: 'DATABASE_URL'
```

**Nguyên nhân:** Chưa tạo file `.env` hoặc chưa đặt `DATABASE_URL`.
**Cách sửa:** Sao chép `.env.example` thành `.env` và điền đầy đủ thông tin.

---

### Trang task hiển thị "Không có task nào"

**Nguyên nhân:** ETL chưa chạy hoặc chưa ghi `dm_daily_collection_tasks`.
**Cách sửa:**
```bash
python etl/run_etl.py
```

---

### Collector không thấy thứ tự mới sau khi Manager Apply

**Nguyên nhân:** Trình duyệt collector đang giữ trang cũ.
**Cách sửa:** Collector nhấn **F5** hoặc reload trang — dữ liệu sẽ cập nhật ngay.

---

### Lỗi "No tasks found" khi nhấn Xem Preview

**Nguyên nhân:** `dm_daily_collection_tasks` trống hoặc snapshot date không khớp.
**Cách sửa:** Kiểm tra `SNAPSHOT_DATE` trong `config.py` khớp với ngày đã ETL (`2024-12-31`).

---

### Thay đổi trọng số nhưng nút "Áp Dụng" vẫn bị mờ

**Nguyên nhân:** Cần chạy lại Preview sau mỗi lần thay đổi trọng số.
**Cách sửa:** Nhấn **Xem Preview** trước, sau đó nút Áp Dụng sẽ bật.

---

*Tài liệu này được tạo cho môn CO5113 – HCMUT, Semester 2 2025-2026.*
