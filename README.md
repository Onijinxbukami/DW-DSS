# DSS Thu Hồi Nợ – Ngân Hàng A
**CO5113 – Data Warehousing & Decision Support Systems | HCMUT**

A Compound DSS (Data-driven + Model-driven) for bank debt recovery, built with Python, SQLite, and Flask.

---

## Quick Start

### 1. Install dependencies
```bash
pip install flask pandas python-dateutil
```

### 2. Run ETL (build the Star Schema database)
```bash
python etl/run_etl.py
```
This takes ~2 minutes and creates `database.db` with 800K+ fact rows.

### 3. Build the Data Mart
```bash
python mart/build_mart.py 2024-12-31
```
Populates `dm_daily_collection_tasks` (~12,000 tasks).

### 4. Start the Web Application
```bash
python run.py
```
Open **http://localhost:5000** in your browser.

---

## Login Accounts

### Manager
| Username | Password | Role |
|----------|----------|------|
| `manager` | `admin123` | Manager |

> Manager can view the Dashboard, run What-If Analysis, and apply new scoring configs.

### Collectors
| Username | Password | Name |
|----------|----------|------|
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

> Pattern: username = `COL-XXX`, password = `colXXX`

---

## Project Structure

```
source/
├── config.py                # Centralized config (paths, constants)
├── run.py                   # App entry point
├── requirements.txt
├── data/
│   ├── raw/                 # All 12 raw CSV files
│   └── database.db          # SQLite DB (generated after ETL)
├── etl/
│   ├── utils.py             # parse_dirty_date, RAW_TO_CLEAN, clean_branch
│   ├── load_dimensions.py   # Load 5 dim tables + scoring_config
│   ├── load_fact.py         # Load fact_debt_installment
│   └── run_etl.py           # ETL orchestrator (run this first)
├── models/
│   ├── helpers.py           # Pure math helpers (normalize, amount_band, source_flag)
│   ├── model1_channel.py    # DPD → dpd_bucket + assigned_channel
│   ├── model2_risk_score.py # Weighted risk score formula
│   └── assign_collectors.py # Round-robin collector assignment
├── mart/
│   └── build_mart.py        # Build dm_daily_collection_tasks
└── app/
    ├── __init__.py          # Flask app factory
    ├── db.py                # Unified SQLite connection helper
    ├── auth.py              # Login / session / role guard
    ├── routes/
    │   ├── collector.py     # Collector routes
    │   └── manager.py       # Manager routes (dashboard, what-if)
    ├── templates/
    │   ├── base.html
    │   ├── login.html
    │   ├── collector/tasks.html
    │   └── manager/dashboard.html, whatif.html
    └── static/
        ├── css/style.css
        └── js/
            ├── collector.js  # Collector page JS
            ├── dashboard.js  # Dashboard charts JS
            └── whatif.js     # What-If analysis JS
```

---

## Pipeline Overview

```
12 CSV files (raw)
    └─► ETL (etl/run_etl.py)
            └─► Star Schema in database.db
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

## Web App Pages

| Role | URL | Description |
|------|-----|-------------|
| Both | `/login` | Login page |
| Collector | `/collector/tasks` | Today's task list, sorted by priority |
| Manager | `/manager/dashboard` | KPI cards + DPD/channel charts + collector performance |
| Manager | `/manager/whatif` | Adjust model weights, preview impact, apply config |

---

## UI Guide

### Login
1. Open **http://localhost:5000** — you are redirected to `/login`.
2. Enter username and password from the accounts table above.
3. Collectors are redirected to their task list; the Manager is redirected to the Dashboard.

---

### Collector – Task List (`/collector/tasks`)

The page shows **all debt collection tasks assigned to the logged-in collector** for the snapshot date (2024-12-31), sorted by priority (rank 1 = highest risk first).

| Column | Description |
|--------|-------------|
| # | Priority rank (1 = most urgent) |
| Customer | Full name |
| Contract | Contract or card account number |
| Product | Loan type or card type |
| DPD | Days Past Due |
| Outstanding | Total remaining debt (VND) |
| Channel | Contact channel assigned by Model 1 |
| Risk Score | Computed by Model 2 (higher = more critical) |
| Status | Current task status |

**Actions:**
- **Update status** — Use the dropdown in the Status column to change a task from `PENDING` → `IN_PROGRESS` → `DONE` or `SKIPPED`. The change is saved immediately (no page reload needed).
- **View detail** — Click the eye icon (or customer name) to open a popup showing:
  - Customer contact info (phone, email, address)
  - Last 6 months of installment/payment history for that contract
- **Logout** — Click the username in the top-right navbar → Logout.

**Row color coding:**
- Red row → DPD bucket D (≥ 30 days, FIELD visit required)
- Yellow row → DPD bucket C (20–29 days, phone call)
- Blue row → DPD bucket B (10–19 days, SMS)
- No highlight → DPD bucket A (1–9 days, email)

---

### Manager – Dashboard (`/manager/dashboard`)

Overview of the entire debt collection portfolio for the snapshot date.

**KPI Cards (top row):**
| Card | Meaning |
|------|---------|
| Total Overdue Accounts | Number of contracts with DPD > 0 |
| Total Outstanding (VND) | Sum of all overdue outstanding balances |
| Tasks Done (%) | Proportion of today's tasks marked DONE |
| Active Collectors | Number of collectors with at least 1 assigned task |

**Charts:**
- **DPD Bucket Distribution** (bar chart) — Count of tasks per bucket (A / B / C / D)
- **Channel Distribution** (doughnut chart) — Breakdown by contact channel (EMAIL / SMS / CALL / FIELD)

**Collector Performance Table:**
Shows each collector's assigned task count, completed (DONE), skipped, and a visual progress bar.

---

### Manager – What-If Analysis (`/manager/whatif`)

Experiment with Model 2 weight changes before applying them permanently.

**Left panel – Weight sliders:**
| Slider | Weight | Default | Meaning |
|--------|--------|---------|---------|
| α (Alpha) | `alpha` | 20 | Importance of overdue frequency (last 6 months) |
| β (Beta) | `beta` | 25 | Importance of worst DPD (last 6 months) |
| γ (Gamma) | `gamma` | 0.5 | Importance of current DPD |
| δ (Delta) | `delta` | 10 | Importance of outstanding amount band |
| ε (Epsilon) | `epsilon` | 5 | Mortgage vs credit card penalty |

Each slider is synced to a numeric input box — you can drag the slider or type a value directly.

**Step 1 – Preview (no changes saved):**
Click **"Recalculate (Preview)"**. The system re-scores all tasks in memory using the new weights and shows:
- **Comparison table** (top 20 tasks): old rank vs new rank, old score vs new score, change direction (↑ ↓ =)
- **Risk Score Histogram**: distribution of new scores across all tasks
- **Summary stats**: number of tasks that moved up / stayed / moved down in priority

**Step 2 – Apply (saves to database):**
After previewing, click **"Apply to Today's Tasks"**. This will:
1. Save the new weights as a new row in `scoring_config` (with your username and timestamp)
2. Rebuild the entire data mart for today using the new weights
3. Collectors who reload their task list will immediately see the updated priority order

> **Note:** Apply cannot be undone from the UI. To revert, re-run `python mart/build_mart.py 2024-12-31` or apply the original weights (α=20, β=25, γ=0.5, δ=10, ε=5) again.

---

## Model Summary

### Model 1 – DPD Channel Assignment
| DPD | Bucket | Channel |
|-----|--------|---------|
| 0 | ON_TIME | (no action) |
| 1–9 | A | EMAIL |
| 10–19 | B | SMS |
| 20–29 | C | CALL |
| ≥ 30 | D | FIELD |

### Model 2 – Risk Score
```
risk_score = α × norm(num_overdue_6m)
           + β × norm(max_dpd_6m)
           + γ × dpd_current
           + δ × amount_band(total_outstanding)
           + ε × source_flag(product_source)
```

Default weights: `α=20, β=25, γ=0.5, δ=10, ε=5`

---

## Re-running After Changes

If you need to rebuild everything from scratch:
```bash
python etl/run_etl.py          # ~2 min, recreates all tables
python mart/build_mart.py 2024-12-31
python run.py
```

To rebuild only the mart (e.g. after manually editing scoring_config):
```bash
python mart/build_mart.py 2024-12-31
```
