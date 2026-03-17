"""
etl/utils.py – ETL-specific utilities: date parsing and branch code mapping.
"""
import re
import os
import sys
from datetime import date

from dateutil import parser as du_parser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_DIR, SNAPSHOT_DATE  # noqa: F401 (re-exported for legacy importers)

# ---------------------------------------------------------------------------
# Branch code mapping: raw → canonical clean code
# ---------------------------------------------------------------------------
RAW_TO_CLEAN = {
    # Already clean
    "BR-HCM01": "BR-HCM01",
    "BR-HCM02": "BR-HCM02",
    "BR-HN01":  "BR-HN01",
    "BR-DN01":  "BR-DN01",
    "BR-CT01":  "BR-CT01",
    "BR-HP01":  "BR-HP01",
    # HCM Q1 variants
    "HCM_Q1":          "BR-HCM01",
    "Ho Chi Minh Q1":  "BR-HCM01",
    "CN-HCM-01":       "BR-HCM01",
    # HCM Q3 variants
    "HCM_Q3":          "BR-HCM02",
    "Ho Chi Minh Q3":  "BR-HCM02",
    "CN-HCM-02":       "BR-HCM02",
    # Ha Noi variants
    "HA_NOI_CN1":  "BR-HN01",
    "Ha Noi CN1":  "BR-HN01",
    "HN-01":       "BR-HN01",
    # Da Nang variants
    "DA_NANG_1":   "BR-DN01",
    "Da Nang CN1": "BR-DN01",
    "DN-01":       "BR-DN01",
    # Can Tho variants
    "CAN_THO_1":   "BR-CT01",
    "Can Tho CN1": "BR-CT01",
    "CT-01":       "BR-CT01",
    # Hai Phong variants
    "HAI_PHONG_1":  "BR-HP01",
    "Hai Phong CN1":"BR-HP01",
    "HP-01":        "BR-HP01",
}


def clean_branch(raw: str) -> str:
    """Map a raw branch code to its canonical form. Returns original if unknown."""
    if not raw or str(raw).strip() == "":
        return "BR-HCM01"  # default fallback
    return RAW_TO_CLEAN.get(str(raw).strip(), str(raw).strip())


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------
_VN_MONTH_RE = re.compile(
    r'^(\d{1,2})\s+[Tt]h[gG]\s+(\d{1,2})\s+(\d{4})$'
)


def parse_dirty_date(raw) -> date | None:
    """Parse a date string from any of the 5 dirty formats used in the dataset."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s.lower() in ("nan", "none", ""):
        return None
    # Vietnamese format: "DD Thg M YYYY"
    m = _VN_MONTH_RE.match(s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    # All other formats handled by dateutil with dayfirst=True
    try:
        return du_parser.parse(s, dayfirst=True).date()
    except Exception:
        return None


def date_to_sk(d: date | None) -> int | None:
    """Convert a date to YYYYMMDD integer key."""
    if d is None:
        return None
    return int(d.strftime("%Y%m%d"))
