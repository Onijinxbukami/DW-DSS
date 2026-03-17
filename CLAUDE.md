# CLAUDE.md – CO5113 DW & DSS: Hệ Thống Thu Hồi Nợ Ngân Hàng A

## Tổng Quan Dự Án

Môn học **CO5113 – Data Warehousing & Decision Support Systems** (HCMUT, Semester 2 2025-2026).

Xây dựng **Compound DSS** (Data-driven + Model-driven) hỗ trợ quy trình **thu hồi nợ** tại ngân hàng giả lập Việt Nam.

**Pipeline tổng thể:**
```
Raw CSV (12 files) → ETL → Star Schema (DW) → Model Base → Data Mart → Web App
```

---

## Dataset – 12 File CSV

Tất cả dữ liệu là **synthetic**, bối cảnh Việt Nam, giai đoạn 2020–2024.
Dữ liệu cố ý "bẩn" ở: **ngày tháng** (nhiều format) và **branch code** (nhiều biến thể).

### Nhóm CoreBank (Vay thế chấp)

| File | Mô tả | PK / FK | ~Rows |
|------|-------|---------|-------|
| `cb_customer.csv` | Thông tin khách hàng CoreBank | PK: `customer_id`; Join key: `national_id` | ~5,000 |
| `cb_mortgage_loan.csv` | Hợp đồng vay thế chấp | PK: `mortgage_loan_id`; FK: `customer_id` | ~7,000 |
| `cb_loan_schedule.csv` | Lịch trả nợ từng kỳ | PK: `loan_schedule_id`; FK: `mortgage_loan_id` | ~100,000+ |
| `cb_payment_transaction.csv` | Giao dịch thanh toán thực tế | PK: `payment_transaction_id`; FK: `mortgage_loan_id + installment_no` | ~50,000–80,000 |

**cb_customer.csv** – Cột chính:
- `customer_id` (INT, PK), `cif` (VARCHAR, dạng `CIF-000001`), `full_name`, `address`, `national_id` (CMND/CCCD – **key chuẩn nhất để merge**), `phone`, `email`

**cb_mortgage_loan.csv** – Cột chính:
- `mortgage_loan_id` (INT, PK), `contract_no` (dạng `ML-2020-000001`), `customer_id` (FK), `product_code` (`HOME/CAR/BUSINESS`), `branch_code_raw` (bẩn), `loan_principal` (BIGINT, ~300tr–5tỷ VND), `interest_rate_annual` (7.5–11%), `disbursement_date_raw` (bẩn), `maturity_date_raw` (bẩn), `outstanding_principal`, `outstanding_interest`, `total_outstanding`

**cb_loan_schedule.csv** – Cột chính:
- `loan_schedule_id` (dạng `SCH-000001-001`), `mortgage_loan_id` (FK), `installment_no`, `installment_due_date_raw` (bẩn), `installment_amount`

**cb_payment_transaction.csv** – Cột chính:
- `payment_transaction_id` (dạng `PAY-000000001`), `mortgage_loan_id` (FK), `installment_no`, `payment_date_raw` (bẩn), `payment_amount`

### Nhóm CoreCard (Thẻ tín dụng)

| File | Mô tả | PK / FK | ~Rows |
|------|-------|---------|-------|
| `cc_user.csv` | Chủ thẻ (~2,500 overlap với CoreBank qua `national_id`) | PK: `cc_user_id`; Join key: `national_id` | ~4,000 |
| `cc_card_account.csv` | Tài khoản thẻ | PK: `card_account_id`; FK: `cc_user_id` | ~5,000–5,500 |
| `cc_card_statement.csv` | Sao kê hàng tháng | PK: `statement_id`; FK: `card_account_id` | ~100,000+ |
| `cc_card_payment.csv` | Thanh toán thẻ | PK: `card_payment_id`; FK: `statement_id + card_account_id` | ~50,000–80,000 |

**cc_user.csv**: `cc_user_id`, `full_name`, `address`, `mobile_number`, `email_address`, `national_id`
- ~2,500 user trùng `national_id` với `cb_customer` (overlap)

**cc_card_account.csv**: `card_account_id`, `cc_user_id` (FK), `account_no` (dạng `CA-2022-0000001`), `card_no_masked`, `card_type` (`VISA/MASTERCARD/JCB`), `product_type` (`CLASSIC/GOLD/PLATINUM/INFINITE`), `issuing_branch_code_raw` (bẩn), `credit_limit`, `current_balance`, `available_credit`

**cc_card_statement.csv**: `statement_id`, `card_account_id` (FK), `statement_date_raw` (bẩn), `payment_due_date_raw` (bẩn), `statement_balance`, `minimum_amount_due`

**cc_card_payment.csv**: `card_payment_id` (dạng `CPAY-000000001`), `statement_id` (FK), `card_account_id` (FK), `payment_date_raw` (bẩn), `payment_amount`

### Nhóm Tổ Chức & Config

| File | Mô tả | Rows |
|------|-------|------|
| `collector_staff.csv` | Nhân viên thu hồi nợ | ~20 |
| `branch_master.csv` | Bảng chuẩn chi nhánh | 6 |
| `branch_raw_codes.csv` | Tất cả branch code bẩn (union từ mọi nguồn) | ~25–30 |
| `scoring_config_initial.csv` | Trọng số mặc định Model Risk Score | 1 |

**collector_staff.csv**: `collector_staff_id`, `collector_code` (dạng `COL-001`), `collector_name`, `team` (`EMAIL_SMS/CALL/FIELD`), `branch_code_raw` (bẩn), `max_daily_cases` (60/40/15 tùy team), `email`, `phone`, `is_active`

**branch_master.csv**: `branch_id` (PK), `branch_code_clean` (dạng `BR-HCM01`), `branch_name`, `city` (TP.HCM/Ha Noi/Da Nang/Can Tho/Hai Phong), `region` (South/North/Central)

**branch_raw_codes.csv**: `raw_branch_code`, `raw_branch_name` (thường để trống)
- Union distinct từ: `cb_mortgage_loan.branch_code_raw`, `cc_card_account.issuing_branch_code_raw`, `collector_staff.branch_code_raw`

**scoring_config_initial.csv**: `config_id`, `effective_date`, `alpha_num_overdue_6m`, `beta_max_dpd_6m`, `gamma_dpd_current`, `delta_amount_band`, `epsilon_product_source_mortgage`, `description`

---

## ETL – Xử Lý Dữ Liệu Bẩn

### Chuẩn hóa ngày tháng
Tất cả cột `_date_raw` hoặc `_raw` chứa ngày có thể ở **5 format lẫn lộn trong cùng 1 cột**:
- `YYYY-MM-DD` → `2023-08-15`
- `DD/MM/YYYY` → `15/08/2023`
- `DD-MM-YYYY` → `15-08-2023`
- `DD.MM.YYYY` → `15.08.2023`
- `DD Thg M YYYY` → `15 Thg 8 2023`

→ Cần viết hàm `parse_dirty_date()` nhận diện và chuẩn hóa về `DATE`.

### Chuẩn hóa branch code
Cùng 1 chi nhánh vật lý có nhiều biến thể raw:

| Branch chuẩn | Các biến thể raw |
|-------------|-----------------|
| `BR-HCM01` | `BR-HCM01`, `HCM_Q1`, `Ho Chi Minh Q1`, `CN-HCM-01` |
| `BR-HN01` | `BR-HN01`, `HA_NOI_CN1`, `Ha Noi CN1`, `HN-01` |
| `BR-DN01` | `BR-DN01`, `Da Nang CN1`, `DN-01`, `DA_NANG_1` |
| `BR-HP01` | (tương tự) `HP-01`, ... |

→ Dùng `branch_raw_codes.csv` → mapping table → `branch_master.csv` → `dim_branch`.

### Merge khách hàng
- `national_id` là **key chuẩn nhất** để hợp nhất `cb_customer` và `cc_user` → `dim_customer`
- ~2,500 có ở cả 2 hệ thống; ~2,500 chỉ CoreBank; ~1,500 chỉ CoreCard → ~6,500 rows `dim_customer`
- Ưu tiên thông tin phone/email từ CoreBank; fallback sang CoreCard

---

## Star Schema (Data Warehouse)

### Dimension Tables

**dim_customer**: `customer_sk` (PK surrogate), `national_id` (business key), `full_name`, `phone`, `email`, `address`, `has_mortgage` (BOOL), `has_credit_card` (BOOL), `source_cif`, `source_cc_user_id`

**dim_product**: `product_sk`, `product_source` (`COREBANK/CORECARD`), `product_code`, `product_name`, `card_type` (nullable; VISA/MC/JCB)

**dim_branch**: `branch_sk`, `branch_code_clean`, `branch_name`, `city`, `region`

**dim_collector**: `collector_sk`, `collector_code`, `collector_name`, `team`, `branch_sk` (FK), `max_daily_cases`, `is_active`

**dim_date**: `date_sk` (format YYYYMMDD), `full_date`, `day_of_week`, `day_name`, `month`, `quarter`, `year`, `is_weekend`, `is_working_day`
- Generate mỗi ngày từ `2020-01-01` đến `2024-12-31`

### Fact Table: fact_debt_installment

| Cột | Kiểu | Ghi chú |
|-----|------|---------|
| `fact_id` | BIGINT PK | |
| `customer_sk` | INT FK | → dim_customer |
| `product_sk` | INT FK | → dim_product |
| `branch_sk` | INT FK | → dim_branch |
| `due_date_sk` | INT FK | → dim_date (ngày đến hạn) |
| `payment_date_sk` | INT FK nullable | → dim_date (NULL nếu chưa trả) |
| `contract_no` | VARCHAR | Số HĐ vay hoặc account_no thẻ |
| `installment_no` | INT | Kỳ thứ mấy |
| `amount_due` | BIGINT | Số tiền phải trả |
| `amount_paid` | BIGINT | 0 nếu chưa trả |
| `amount_remaining` | BIGINT | = amount_due - amount_paid |
| `dpd` | INT | Days Past Due |
| `status` | VARCHAR | `PAID/PARTIAL/OVERDUE/PENDING` |
| `total_outstanding` | BIGINT | Tổng dư nợ còn lại của HĐ |

**Tính DPD:**
- CoreBank: join `cb_loan_schedule` + `cb_payment_transaction` trên `mortgage_loan_id + installment_no` → `dpd = payment_date - due_date`. Nếu không có payment → `dpd = snapshot_date (2024-12-31) - due_date`
- CoreCard: join `cc_card_statement` + `cc_card_payment` trên `statement_id` → `dpd = payment_date - payment_due_date`

---

## Model Base

### Model 1 – DPD-Based Channel Assignment (Decision Under Certainty)

Operational model – hỗ trợ quyết định tác nghiệp hàng ngày.

| DPD | dpd_bucket | assigned_channel |
|-----|-----------|-----------------|
| 0 | ON_TIME | (không cần action) |
| 1–9 | A | EMAIL |
| 10–19 | B | SMS |
| 20–29 | C | CALL |
| ≥ 30 | D | FIELD |

**Biến theo Ch.7:** Decision var = `contact_channel`; Uncontrollable = `dpd`; Intermediate = `dpd_bucket`; Result = `assigned_channel`

### Model 2 – Risk Score & Priority Ranking (Decision Under Risk)

Tactical model – hỗ trợ quản lý phân bổ nguồn lực.

```
risk_score = α × normalize(num_overdue_6m)
           + β × normalize(max_dpd_6m)
           + γ × dpd_current
           + δ × amount_band(total_outstanding)
           + ε × source_flag(product_source)
```

**Trọng số mặc định:** α=20, β=25, γ=0.5, δ=10, ε=5

**amount_band(total_outstanding):**
- < 100tr → 10
- 100–500tr → 30
- 500tr–1tỷ → 60
- > 1tỷ → 100

**source_flag:** Mortgage (COREBANK) = cao hơn; Card (CORECARD) = thấp hơn

**Aggregate behavior 6 tháng** (input Model 2):
```sql
SELECT customer_sk, contract_no,
  COUNT(CASE WHEN status IN ('OVERDUE','PARTIAL') AND due_date >= DATE('2024-06-30') THEN 1 END) AS num_overdue_6m,
  MAX(CASE WHEN due_date >= DATE('2024-06-30') THEN dpd ELSE 0 END) AS max_dpd_6m
FROM fact_debt_installment
GROUP BY customer_sk, contract_no
```

**priority_rank:** Sắp xếp `risk_score` giảm dần → rank 1 = ưu tiên nhất

---

## Data Mart: dm_daily_collection_tasks

Mỗi dòng = 1 task cho 1 collector vào 1 ngày.

| Cột chính | Ghi chú |
|-----------|---------|
| `task_id` | BIGINT PK |
| `snapshot_date` | DATE |
| `customer_sk`, `customer_name`, `national_id`, `phone`, `email` | Denormalized |
| `contract_no`, `product_source`, `product_code` | |
| `branch_sk`, `branch_name` | Denormalized |
| `total_outstanding`, `amount_due_current`, `dpd_current` | |
| `dpd_bucket`, `assigned_channel` | Output Model 1 |
| `num_overdue_6m`, `max_dpd_6m` | Input Model 2 |
| `risk_score`, `priority_rank` | Output Model 2 |
| `collector_sk`, `collector_name` | Assigned collector |
| `task_status` | `PENDING/IN_PROGRESS/DONE/SKIPPED` |
| `config_id` | Config trọng số đang áp dụng |

**Logic assign collector:**
1. Lọc fact_debt_installment: `dpd > 0`
2. Chạy Model 1 → `dpd_bucket + assigned_channel`
3. Chạy Model 2 → `risk_score + priority_rank`
4. Match channel → team: `EMAIL/SMS` → `EMAIL_SMS`; `CALL` → `CALL`; `FIELD` → `FIELD`
5. Round-robin theo branch, không vượt `max_daily_cases`

---

## Scoring Config (Phục Vụ What-If & Apply)

**Bảng `scoring_config`** (persistent):
- `config_id` (PK auto-increment), `effective_date` (DATETIME), `alpha_*`, `beta_*`, `gamma_*`, `delta_*`, `epsilon_*`, `applied_by` (username manager), `description`

**Khi Manager bấm "Apply":**
1. INSERT row mới vào `scoring_config` với `effective_date = NOW()`
2. Re-run Model 2 → recalc `risk_score + priority_rank`
3. UPDATE `dm_daily_collection_tasks` ngày hôm nay
4. Collector reload → thấy thứ tự mới

---

## Web Application

### Kiến trúc
```
Frontend (React / Streamlit / Flask-Jinja)
    ↕ REST API
Backend (Python Flask / FastAPI)
    ↕
Database (PostgreSQL / SQLite)
    ├── dim_customer, dim_product, dim_branch, dim_collector, dim_date
    ├── fact_debt_installment
    ├── dm_daily_collection_tasks
    └── scoring_config
```

### Tab 1 – Collector View
- Đăng nhập → danh sách task hôm nay, sort theo `priority_rank ASC`
- Hiển thị: tên KH, SĐT, hợp đồng, sản phẩm, DPD, dư nợ, kênh, risk score, trạng thái
- Dropdown cập nhật status: `PENDING → IN_PROGRESS → DONE/SKIPPED`
- Popup chi tiết khi click: address, email, lịch sử 6 tháng
- Query: `WHERE collector_sk = :id AND snapshot_date = CURRENT_DATE ORDER BY priority_rank ASC`

### Tab 2 – Manager What-If Analysis
- Panel trái: Slider/input cho α, β, γ, δ, ε (so sánh với config hiện tại)
- Nút "Recalculate (Preview)" → không ghi DB
- Panel phải: Bảng so sánh Current vs New (top 20), histogram phân bố risk_score, thống kê đổi thứ tự/channel
- Nút "Apply to Today's Tasks" (chỉ Manager): ghi config + recalc + update DM

### Tab 3 – Manager Dashboard
- KPI Cards: tổng khoản overdue, tổng dư nợ overdue, % task DONE, số collector active
- Bar chart phân bố DPD bucket (A/B/C/D)
- Histogram risk score
- Bảng performance collector (assigned/done/skipped)
- Trend line số khoản overdue & dư nợ theo ngày

---

## Ánh Xạ Lý Thuyết (Chapter 6 & 7)

| Khái niệm | Áp dụng trong dự án |
|-----------|---------------------|
| Semistructured problem (Ch.6) | Thu hồi nợ: structured (DPD rule) + unstructured (chiến lược trọng số) |
| DSS Architecture (Ch.6) | Data = Star Schema; Model = Model 1+2; UI = Web App |
| Compound DSS (Ch.6) | Data-driven (DW, OLAP) + Model-driven (scoring, what-if) |
| Operational model (Ch.6) | Model 1: DPD → Channel assignment |
| Tactical model (Ch.6) | Model 2: Risk Score → Priority |
| Decision under certainty (Ch.7) | Model 1: DPD xác định → channel xác định |
| Decision under risk (Ch.7) | Model 2: behavior lịch sử + trọng số → risk score |
| Variable types (Ch.7) | Decision=trọng số α–ε; Uncontrollable=DPD/outstanding/behavior; Intermediate=normalized scores; Result=risk_score/priority_rank |
| What-If Analysis (Ch.7) | Tab Manager: thay đổi trọng số → xem preview |
| Sensitivity Analysis (Ch.7) | So sánh current vs new risk_score, đo mức thay đổi ranking |
| Static model (Ch.7) | Model 1 & 2 tính trên snapshot 1 ngày |
| MBMS functions (Ch.6) | `scoring_config` cho phép create/update/manage model parameters |
| Star Schema (Ch.3) | 5 dim + 1 fact |

**Tài liệu tham chiếu:**
- `CO5113_DW-DSS-Chapter-6-DSS.pdf` – Semester 2 2025-2026
- `CO5113_DW-DSS-Chapter-7-Modeling-and-Anaysis.pdf` – Semester 2 2025-2026

---

## Checklist Triển Khai

### Phase 1: Data & ETL
- [ ] Generate 12 file CSV
- [ ] Hàm `parse_dirty_date()` xử lý 5 format ngày
- [ ] Bảng mapping `branch_raw → branch_clean`
- [ ] Merge customer trên `national_id`
- [ ] Tính DPD cho từng installment/statement
- [ ] Load vào Star Schema (5 dim + 1 fact)
- [ ] Validate spot-check 10–20 records

### Phase 2: Model Base & Data Mart
- [ ] Model 1 (DPD rule → channel)
- [ ] Aggregate behavior 6 tháng → input Model 2
- [ ] Model 2 (Risk Score formula)
- [ ] Assign collector (round-robin, max_daily_cases)
- [ ] Ghi ra `dm_daily_collection_tasks`

### Phase 3: Web Application
- [ ] Backend setup (Flask/FastAPI/Streamlit)
- [ ] Login + role (Collector vs Manager)
- [ ] Tab 1: Collector Task List
- [ ] Tab 2: Manager What-If (preview + Apply)
- [ ] Tab 3: Manager Dashboard
- [ ] Test end-to-end: Manager Apply → Collector reload → thứ tự mới

### Phase 4: Báo Cáo & Demo
- [ ] Viết báo cáo: ánh xạ lý thuyết Ch.6–7
- [ ] Demo 8 bước (raw data → ETL → Star Schema → Model 1+2 → DM → Collector view → What-If → Dashboard)
