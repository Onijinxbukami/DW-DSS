# DSS Thu Hồi Nợ – Ngân Hàng A
**CO5113 – Data Warehousing & Decision Support Systems | HCMUT**

Hệ thống **Compound DSS** (Data-driven + Model-driven) hỗ trợ quy trình thu hồi nợ tại ngân hàng giả lập Việt Nam. Được xây dựng bằng Python, PostgreSQL (Supabase) và Flask.

---

## Quick Start

### 1. Cài đặt dependencies
```bash
pip install -r requirements.txt
```

### 2. Cấu hình database
Tạo file `.env` từ `.env.example` và điền thông tin Supabase:
```
DATABASE_URL=postgresql://postgres@db.YOUR-REF.supabase.co:5432/postgres
DB_PASSWORD=your-password
SECRET_KEY=your-secret-key
```

### 3. Chạy ETL (tạo Star Schema)
```bash
python etl/run_etl.py
```
Tạo ~800K+ fact rows trong PostgreSQL.

### 4. Build Data Mart
```bash
python mart/build_mart.py 2024-12-31
```
Tạo ~12,000 task trong `dm_daily_collection_tasks`.

### 5. Khởi động Web App
```bash
python run.py
```
Mở **http://localhost:5000** trên trình duyệt.

---

## Tài Khoản Đăng Nhập

### Manager
| Username | Password | Vai trò |
|----------|----------|---------|
| `manager` | `admin123` | Quản lý |

> Manager có thể xem Dashboard, chạy What-If Analysis và áp dụng config mới.

### Collectors
| Username | Password | Tên |
|----------|----------|-----|
| `COL-001` | `col001` | Bui Thu Linh |
| `COL-002` | `col002` | Nguyen Thi Trang |
| `COL-003` | `col003` | Dang Quang Chau |
| `COL-004` | `col004` | Vo Thi Huy |
| `COL-005` | `col005` | Pham Quang Thao |
| `COL-006` | `col006` | Tran Thu Trang |
| `COL-007` | `col007` | Huynh Thanh Dung |
| `COL-008` | `col008` | Tran Duc Dung |
| `COL-009` | `col009` | Dang Thanh Chau |
| `COL-010` | `col010` | Bui Van Hieu |
| `COL-011` | `col011` | Dang Van Khanh |
| `COL-012` | `col012` | Phan Minh Hieu |
| `COL-013` | `col013` | Phan Ngoc Khoa |
| `COL-014` | `col014` | Nguyen Thi Binh |
| `COL-015` | `col015` | Bui Hai Trang |
| `COL-016` | `col016` | Vo Duc Tuan |
| `COL-017` | `col017` | Phan Duc Binh |
| `COL-018` | `col018` | Hoang Anh Vy |
| `COL-019` | `col019` | Nguyen Quang Tuan |
| `COL-020` | `col020` | Tran Thu Linh |

> Quy tắc: username = `COL-XXX`, password = `colXXX`

---

## Cấu Trúc Dự Án

```
source/
├── config.py                # Cấu hình tập trung (đường dẫn, hằng số)
├── run.py                   # Entry point ứng dụng
├── requirements.txt
├── vercel.json              # Cấu hình deploy Vercel
├── data/
│   └── raw/                 # 12 file CSV nguồn
├── etl/
│   ├── utils.py             # parse_dirty_date, RAW_TO_CLEAN, clean_branch
│   ├── load_dimensions.py   # Load 5 dim tables + scoring_config
│   ├── load_fact.py         # Load fact_debt_installment
│   └── run_etl.py           # ETL orchestrator
├── models/
│   ├── helpers.py           # Hàm toán học (normalize, amount_band, source_flag)
│   ├── model1_channel.py    # Model 1: DPD → dpd_bucket + assigned_channel
│   ├── model2_risk_score.py # Model 2: Công thức risk score
│   └── assign_collectors.py # Phân công collector round-robin
├── mart/
│   └── build_mart.py        # Build dm_daily_collection_tasks
└── app/
    ├── __init__.py          # Flask app factory
    ├── db.py                # PostgreSQL connection wrapper
    ├── auth.py              # Đăng nhập / session / phân quyền
    ├── routes/
    │   ├── collector.py     # Routes cho Collector
    │   └── manager.py       # Routes cho Manager (dashboard, what-if)
    ├── templates/
    │   ├── base.html
    │   ├── login.html
    │   ├── collector/tasks.html
    │   └── manager/dashboard.html, whatif.html
    └── static/
        ├── css/style.css
        └── js/
            ├── collector.js
            ├── dashboard.js
            └── whatif.js
```

---

## Pipeline Tổng Thể

```
12 file CSV (raw)
    └─► ETL (etl/run_etl.py)
            └─► Star Schema (PostgreSQL)
                    ├── dim_customer, dim_product, dim_branch
                    ├── dim_collector, dim_date
                    └── fact_debt_installment (~812K rows)
                            └─► Model Base
                                    ├── Model 1: DPD → Channel
                                    └── Model 2: Risk Score
                                            └─► Data Mart (mart/build_mart.py)
                                                    └─► dm_daily_collection_tasks
                                                            └─► Web App (run.py)
```

---

## Các Trang Web

| Vai trò | URL | Mô tả |
|---------|-----|-------|
| Tất cả | `/login` | Trang đăng nhập |
| Collector | `/collector/tasks` | Danh sách task hôm nay, sắp xếp theo ưu tiên |
| Manager | `/manager/dashboard` | KPI + biểu đồ + hiệu suất collector |
| Manager | `/manager/whatif` | Điều chỉnh trọng số, preview, áp dụng config |

---

## Hướng Dẫn Sử Dụng

### Đăng nhập
1. Mở **http://localhost:5000** → chuyển đến `/login`
2. Nhập username và password từ bảng tài khoản trên
3. Collector → chuyển đến danh sách task; Manager → chuyển đến Dashboard

---

### Collector – Danh Sách Task (`/collector/tasks`)

Hiển thị **tất cả task được phân công cho collector** theo ngày snapshot (2024-12-31), sắp xếp theo độ ưu tiên (rank 1 = rủi ro cao nhất).

| Cột | Mô tả |
|-----|-------|
| # | Thứ hạng ưu tiên (1 = khẩn cấp nhất) |
| Khách hàng | Họ tên đầy đủ |
| Hợp đồng | Số hợp đồng vay hoặc tài khoản thẻ |
| Sản phẩm | Loại vay hoặc loại thẻ |
| DPD | Số ngày quá hạn |
| Dư nợ | Tổng dư nợ còn lại (VND) |
| Kênh | Kênh liên hệ do Model 1 xác định |
| Risk Score | Điểm rủi ro từ Model 2 (cao hơn = nguy hiểm hơn) |
| Trạng thái | Trạng thái xử lý hiện tại |

**Thao tác:**
- **Cập nhật trạng thái** — Dùng dropdown để chuyển `PENDING → IN_PROGRESS → DONE / SKIPPED`. Lưu ngay, không cần reload trang.
- **Xem chi tiết** — Click icon mắt để xem popup: thông tin liên hệ KH, lịch sử 6 tháng thanh toán.
- **Đăng xuất** — Click username góc trên phải → Logout.

**Màu sắc dòng:**
- Đỏ → Bucket D (DPD ≥ 30, cần gặp trực tiếp)
- Vàng → Bucket C (DPD 20–29, gọi điện)
- Xanh dương → Bucket B (DPD 10–19, SMS)
- Không màu → Bucket A (DPD 1–9, email)

---

### Manager – Dashboard (`/manager/dashboard`)

Tổng quan danh mục thu hồi nợ toàn hệ thống theo ngày snapshot.

**KPI Cards:**
| Card | Ý nghĩa |
|------|---------|
| Tổng khoản quá hạn | Số hợp đồng có `dpd_current > 0` |
| Tổng dư nợ quá hạn | Tổng `total_outstanding` (đơn vị tỷ VND) |
| Tỷ lệ hoàn thành | % task có `task_status = DONE` |
| Collector đang hoạt động | Số collector được phân công ít nhất 1 task |

**Biểu đồ:**
- **Phân bố DPD Bucket** (bar chart) — Số task theo nhóm A / B / C / D
- **Phân bố kênh liên hệ** (doughnut chart) — EMAIL / SMS / CALL / FIELD
- **Phân bố Risk Score** (histogram) — Phân bố điểm rủi ro toàn bộ task
- **Phân bố trạng thái task** — PENDING / IN_PROGRESS / DONE / SKIPPED

**Bảng hiệu suất Collector:**
Số task được giao / hoàn thành / bỏ qua / đang xử lý của từng collector.

---

### Manager – What-If Analysis (`/manager/whatif`)

Thử nghiệm thay đổi trọng số Model 2 trước khi áp dụng chính thức.

**Panel trái – Slider trọng số:**
| Slider | Tham số | Mặc định | Ý nghĩa |
|--------|---------|---------|---------|
| α (Alpha) | `alpha` | 20 | Tầm quan trọng của tần suất quá hạn 6 tháng |
| β (Beta) | `beta` | 25 | Tầm quan trọng của DPD cao nhất 6 tháng |
| γ (Gamma) | `gamma` | 0.5 | Tầm quan trọng của DPD hiện tại |
| δ (Delta) | `delta` | 10 | Tầm quan trọng của mức dư nợ |
| ε (Epsilon) | `epsilon` | 5 | Phân biệt vay thế chấp vs thẻ tín dụng |

**Bước 1 – Preview (chưa lưu DB):**
Click **"Tính lại (Preview)"** → hệ thống tính lại risk score trong bộ nhớ và hiển thị:
- **Bảng so sánh Top 20**: thứ hạng cũ vs mới, điểm cũ vs mới, hướng thay đổi (↑ ↓ =)
- **Histogram so sánh**: phân bố risk score trước và sau khi thay trọng số
- **Thống kê thay đổi**: số task đổi thứ hạng, số task đổi kênh liên hệ

**Bước 2 – Apply (lưu vào DB):**
Click **"Áp dụng cho Task Hôm Nay"**:
1. Lưu trọng số mới vào bảng `scoring_config` (kèm username và timestamp)
2. Rebuild toàn bộ data mart với trọng số mới
3. Collector reload trang sẽ thấy thứ tự ưu tiên mới

> **Lưu ý:** Apply không thể hoàn tác từ UI. Để khôi phục, áp dụng lại trọng số gốc (α=20, β=25, γ=0.5, δ=10, ε=5) hoặc chạy lại `python mart/build_mart.py 2024-12-31`.

---

## Model 1 – Phân Loại Kênh Liên Hệ Theo DPD
### (Decision Under Certainty – Quyết định trong điều kiện chắc chắn)

### Mô tả
Model 1 là mô hình **tác nghiệp**, tự động xác định kênh liên hệ phù hợp cho từng khoản nợ dựa trên số ngày quá hạn (DPD – Days Past Due). Đây là quyết định **hoàn toàn xác định**: cùng một giá trị DPD luôn cho ra cùng một kênh liên hệ, không có yếu tố ngẫu nhiên.

### Các biến theo lý thuyết Ch.7

| Loại biến | Biến | Mô tả |
|-----------|------|-------|
| **Biến quyết định** | `assigned_channel` | Kênh liên hệ được chọn (EMAIL / SMS / CALL / FIELD) |
| **Biến không kiểm soát** | `dpd_current` | Số ngày quá hạn thực tế của khách hàng |
| **Biến trung gian** | `dpd_bucket` | Nhóm DPD (A / B / C / D) |
| **Biến kết quả** | `task_status` | Trạng thái xử lý sau khi collector thực hiện |

### Quy tắc phân loại

```
DPD = 0          → Nhóm: ON_TIME  → Kênh: Không cần xử lý
DPD = 1  – 9    → Nhóm: A        → Kênh: EMAIL
DPD = 10 – 19   → Nhóm: B        → Kênh: SMS
DPD = 20 – 29   → Nhóm: C        → Kênh: CALL (Gọi điện)
DPD ≥ 30         → Nhóm: D        → Kênh: FIELD (Gặp trực tiếp)
```

### Ánh xạ kênh → nhóm nhân viên

| Kênh | Nhóm collector |
|------|---------------|
| EMAIL | EMAIL_SMS |
| SMS | EMAIL_SMS |
| CALL | CALL |
| FIELD | FIELD |

### Sơ đồ luồng Model 1

```
┌─────────────────┐
│  fact_debt_      │
│  installment     │
│  (dpd_current)   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│           assign_channel(dpd)           │
│                                         │
│  dpd ≤ 0  → ON_TIME  → NONE            │
│  dpd ≤ 9  → Bucket A → EMAIL           │
│  dpd ≤ 19 → Bucket B → SMS             │
│  dpd ≤ 29 → Bucket C → CALL            │
│  dpd ≥ 30 → Bucket D → FIELD           │
└────────────────┬────────────────────────┘
                 │
                 ▼
        ┌────────────────┐
        │  dpd_bucket    │
        │  assigned_     │
        │  channel       │
        └────────────────┘
```

---

## Model 2 – Tính Điểm Rủi Ro & Xếp Hạng Ưu Tiên
### (Decision Under Risk – Quyết định trong điều kiện rủi ro)

### Mô tả
Model 2 là mô hình **chiến thuật**, tính toán điểm rủi ro (`risk_score`) cho mỗi khoản nợ dựa trên lịch sử hành vi và đặc điểm khoản vay. Đây là quyết định **có rủi ro**: kết quả phụ thuộc vào nhiều yếu tố với trọng số có thể điều chỉnh bởi Manager qua chức năng What-If.

### Công thức tính điểm

```
risk_score = α × normalize(num_overdue_6m)
           + β × normalize(max_dpd_6m)
           + γ × dpd_current
           + δ × amount_band(total_outstanding)
           + ε × source_flag(product_source)
```

### Trọng số mặc định

| Tham số | Ký hiệu | Giá trị mặc định | Ý nghĩa |
|---------|---------|-----------------|---------|
| alpha | α | 20 | Trọng số số lần quá hạn 6 tháng |
| beta | β | 25 | Trọng số DPD cao nhất 6 tháng |
| gamma | γ | 0.5 | Trọng số DPD hiện tại |
| delta | δ | 10 | Trọng số mức dư nợ |
| epsilon | ε | 5 | Trọng số loại sản phẩm |

### Các biến theo lý thuyết Ch.7

| Loại biến | Biến | Mô tả |
|-----------|------|-------|
| **Biến quyết định** | α, β, γ, δ, ε | Trọng số Manager điều chỉnh |
| **Biến không kiểm soát** | `dpd_current`, `total_outstanding`, `num_overdue_6m`, `max_dpd_6m` | Dữ liệu thực tế từ DW |
| **Biến trung gian** | `_norm_overdue`, `_norm_dpd6m`, `_amount_band`, `_source_flag` | Giá trị đã chuẩn hóa |
| **Biến kết quả** | `risk_score`, `priority_rank` | Điểm rủi ro và thứ tự ưu tiên |

### Chi tiết từng thành phần

#### ① α × normalize(num_overdue_6m) — Lịch sử quá hạn 6 tháng
- `num_overdue_6m`: số kỳ có trạng thái OVERDUE hoặc PARTIAL trong 6 tháng gần nhất
- Chuẩn hóa Min-Max về 0–100 trên toàn bộ tập dữ liệu
- α=20 → đóng góp tối đa 2,000 điểm

#### ② β × normalize(max_dpd_6m) — DPD cao nhất 6 tháng
- `max_dpd_6m`: số ngày quá hạn lớn nhất trong 6 tháng gần nhất
- Chuẩn hóa Min-Max về 0–100
- β=25 → **trọng số cao nhất**, đóng góp tối đa 2,500 điểm

#### ③ γ × dpd_current — DPD hiện tại (không chuẩn hóa)
- Giá trị DPD thực tế, không qua chuẩn hóa
- γ=0.5 → ví dụ DPD=60 đóng góp 30 điểm

#### ④ δ × amount_band(total_outstanding) — Mức dư nợ

| Dư nợ còn lại | Điểm band |
|--------------|-----------|
| < 100 triệu VND | 10 |
| 100 – 500 triệu VND | 30 |
| 500 triệu – 1 tỷ VND | 60 |
| > 1 tỷ VND | 100 |

- δ=10 → đóng góp 100–1,000 điểm

#### ⑤ ε × source_flag(product_source) — Loại sản phẩm

| Sản phẩm | Điểm flag |
|----------|-----------|
| COREBANK (vay thế chấp) | 10 |
| CORECARD (thẻ tín dụng) | 5 |

- ε=5 → đóng góp 25 hoặc 50 điểm

### Chuẩn hóa Min-Max

```
normalize(x) = (x - min) / (max - min) × 100
```
- Nếu min = max (tất cả bằng nhau) → normalize = 0

### Xếp hạng ưu tiên

```
priority_rank = rank(risk_score, thứ tự giảm dần)
```
- `priority_rank = 1` → rủi ro cao nhất → được xử lý trước
- Collector thấy danh sách task sắp xếp theo `priority_rank ASC`

---

## Phân Công Collector (Assign Collectors)

### Thuật toán Round-Robin

Sau khi có `risk_score` và `assigned_channel`, hệ thống phân công nhân viên thu hồi nợ:

```
1. Lọc collector đang hoạt động (is_active = 1)
2. Nhóm collector theo (team, branch_sk)
3. Sắp xếp task theo priority_rank (ưu tiên cao → phân công trước)
4. Với mỗi task:
   a. Xác định team cần (EMAIL_SMS / CALL / FIELD)
   b. Tìm nhóm collector cùng team + cùng chi nhánh
   c. Nếu không có → fallback sang team đó ở chi nhánh bất kỳ
   d. Round-robin: chọn collector tiếp theo chưa đủ max_daily_cases
5. Nếu tất cả collector đã đủ tải → task không được phân công
```

### Giới hạn tải mỗi ngày

| Nhóm | max_daily_cases |
|------|----------------|
| EMAIL_SMS | 60 ca/ngày |
| CALL | 40 ca/ngày |
| FIELD | 15 ca/ngày |

---

## Luồng Tổng Thể Model Base

```
fact_debt_installment
        │
        ▼
[Model 1] assign_channel(dpd_current)
        │
        ├── dpd_bucket (A/B/C/D)
        └── assigned_channel (EMAIL/SMS/CALL/FIELD)
        │
        ▼
[Model 2] compute_risk_scores(weights)
        │
        ├── risk_score
        └── priority_rank
        │
        ▼
[Assign] assign_collectors (round-robin)
        │
        ├── collector_sk
        └── collector_name
        │
        ▼
dm_daily_collection_tasks
(Collector xem & xử lý theo priority_rank)
```

---

## Biểu Đồ Trong Ứng Dụng

### Tab Manager – Dashboard

| Biểu đồ | Mô tả | Dữ liệu nguồn |
|---------|-------|--------------|
| **KPI – Tổng khoản quá hạn** | Số hợp đồng có `dpd_current > 0` | `dm_daily_collection_tasks` |
| **KPI – Tổng dư nợ quá hạn** | Tổng `total_outstanding` (đơn vị tỷ VND) | `dm_daily_collection_tasks` |
| **KPI – Tỷ lệ hoàn thành** | % task có `task_status = DONE` | `dm_daily_collection_tasks` |
| **KPI – Collector đang hoạt động** | Số collector được phân công | `dm_daily_collection_tasks` |
| **Bar chart – Phân bố DPD Bucket** | Số task theo nhóm A/B/C/D | Output Model 1 |
| **Doughnut – Phân bố kênh liên hệ** | Số task theo EMAIL/SMS/CALL/FIELD | Output Model 1 |
| **Histogram – Phân bố Risk Score** | Số task theo dải điểm rủi ro | Output Model 2 |
| **Doughnut – Phân bố trạng thái** | PENDING/IN_PROGRESS/DONE/SKIPPED | `dm_daily_collection_tasks` |
| **Bảng – Hiệu suất Collector** | assigned / done / skipped / in_progress | `dm_daily_collection_tasks` |

### Tab Manager – What-If Analysis

| Biểu đồ | Mô tả |
|---------|-------|
| **Bảng so sánh Top 20** | Risk score cũ vs mới, thứ hạng cũ vs mới, chênh lệch |
| **Histogram so sánh** | Phân bố risk score trước và sau khi thay đổi trọng số |
| **Thống kê thay đổi** | Số task đổi thứ hạng, số task đổi kênh liên hệ |

---

## Ánh Xạ Lý Thuyết (Ch.6 & Ch.7)

| Khái niệm | Áp dụng trong dự án |
|-----------|---------------------|
| Semistructured problem (Ch.6) | Thu hồi nợ: structured (DPD rule) + unstructured (chiến lược trọng số) |
| DSS Architecture (Ch.6) | Data = Star Schema; Model = Model 1+2; UI = Web App |
| Compound DSS (Ch.6) | Data-driven (DW, OLAP) + Model-driven (scoring, what-if) |
| Operational model (Ch.6) | Model 1: DPD → Channel assignment |
| Tactical model (Ch.6) | Model 2: Risk Score → Priority |
| Decision under certainty (Ch.7) | Model 1: DPD xác định → channel xác định |
| Decision under risk (Ch.7) | Model 2: behavior lịch sử + trọng số → risk score |
| What-If Analysis (Ch.7) | Tab Manager: thay đổi trọng số → xem preview |
| Sensitivity Analysis (Ch.7) | So sánh current vs new risk_score, đo mức thay đổi ranking |
| Static model (Ch.7) | Model 1 & 2 tính trên snapshot 1 ngày |
| Star Schema (Ch.3) | 5 dim + 1 fact |

---

## Chạy Lại Sau Khi Thay Đổi

Rebuild toàn bộ từ đầu:
```bash
python etl/run_etl.py
python mart/build_mart.py 2024-12-31
python run.py
```

Chỉ rebuild mart (sau khi sửa `scoring_config`):
```bash
python mart/build_mart.py 2024-12-31
```
