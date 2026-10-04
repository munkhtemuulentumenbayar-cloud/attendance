"""
Цаг бүртгэл ба ирцийн систем — Цөм логик (Core business logic)
================================================================
Time Registration & Employee Attendance System — zero dependency core.

Ажлын цагийн хуваарьтай (ж: 09:00-18:00) харьцуулж:
  * Хоцролт (late arrival) — минут
  * Эрт явсан (early departure) — минут
  * Ажилласан цаг (worked minutes)
  * Хасагдсан минут (deducted minutes) = хоцролт + эрт явсан
  * Төлбөртэй цаг (payable minutes) = ажилласан - хасагдсан
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import hmac
import math
import os
import random
import re
import secrets
import sqlite3
import tempfile
import threading
import uuid
import zipfile
from datetime import date, datetime, time, timedelta
from urllib.parse import unquote
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.environ.get("ATTENDANCE_DB", os.path.join(DATA_DIR, "attendance.db"))

_lock = threading.RLock()

# --------------------------------------------------------------------------
# Тохиргооны үндсэн утгууд (Settings defaults)
# --------------------------------------------------------------------------
DEFAULT_SETTINGS = {
    "company_name": "Барилгын Бригад ХХК",
    "timezone": "Asia/Ulaanbaatar",
    "schedule_start": "09:00",
    "schedule_end": "19:00",          # ажлын өдөр 09:00–19:00
    "lunch_start": "13:00",           # үдийн завсарлага эхлэх
    "lunch_end": "14:00",             # үдийн завсарлага дуусах
    "lunch_paid": "1",                # 1 = үдийн завсарлага ЦАЛИНТАЙ (цагийн тарифт орно)
    "grace_minutes": "0",           # хөнгөлөх минут (grace period)
    "lunch_deduct_minutes": "0",    # өдөрт хасах үдийн завсарлага
    "workdays": "1,2,3,4,5,6",        # 1=Даваа ... 7=Ням
    "geofence_enabled": "1",
    "geofence_name": "Төв оффис — Сүхбаатарын талбай",
    "geofence_lat": "47.918400",
    "geofence_lng": "106.917700",
    "geofence_radius_m": "300",
    "demo_mode": "1",               # GPS байхгүй үед турших горим
    "admin_user": "admin",
    "admin_password": "admin123",
    "min_worked_minutes_for_break": "240",
    # ---- Цалин / ээлж (v2) ----
    "currency": "₮",
    # --- v4.5: сард ХОЁР төлбөр ---
    "pay_day": "10",                  # үндсэн цалин олгох өдөр (11 → 10 үеийн цалин)
    "period_start_day": "11",         # цалингийн үе эхлэх өдөр (өмнөх сар)
    "advance_day": "25",              # аванс олгох өдөр
    "advance_window_end_day": "24",   # авансын хөдөлмөрийн цонх дуусах өдөр (11 → 24)
    "advance_amount": "1000000",      # авансын дүн (₮)
    "advance_min_full_days": "7",     # үүнээс ДЭЭШ бүтэн өдөр ажилласан бол аванс
    "full_day_min_credit": "0.9",     # «бүтэн өдөр» = ээлжийн энэ хэсгээс дээш ажилласан
    "advance_cap_earned": "1",        # аванс нь 11–24-нд ажилласан цалингаас хэтрэхгүй
    "advance_enabled": "1",
    "default_daily_rate": "80000",        # шинэ ажилтны үндсэн өдрийн цалин
    "night_start": "19:00",               # шөнийн ээлж эхлэх
    "night_end": "03:00",                 # шөнийн ээлж дуусах (дараа өдөр)
    "guard_percent": "50",                # шөнийн хамгаалалт — өдрийн цалингийн %
    "worker_percent": "100",              # шөнийн ажилчин — өдрийн цалингийн %
    "overtime_multiplier": "1.0",         # нэмэлт цагийн коэффициент
    "absence_penalty_days": "3",          # дараалан тасрах хоног
    "absence_penalty_percent": "10",      # сарын цалингийн хасалт %
    "paid_leave_kinds": "",                # v3.1: төрлөөр цалинтай болгохгүй — хүсэлт бүр paid=0/1 (админ шийднэ)
    "show_pay_to_employee": "1",          # ажилтанд өөрийн цалин харуулах эсэх
    "absent_minutes_grace": "10",         # 10 минутаас дээш зөвшөөрөлгүй тасалдлыг «ирээгүй» гэж үзнэ
    "leave_request_notify": "1",          # чөлөөний хүсэлтийг админд мэдэгдэнэ
    "leave_reminder_minutes": "30",       # хүсэлт N минут шийдэгдэхгүй бол сануулга
    "notify_start": "1",                  # ажил эхлэхэд бүртгэлгүй бол сануулга
    "notify_end": "1",                    # ажил дуусахад гарах бүртгэлгүй бол сануулга
    "auto_absent": "1",                   # бүртгэлгүй бол «тасарсан» гэж бүртгэнэ
    "notify_missed_minutes": "15",
    "require_photo": "1",              # ажил эхлэх/дуусах, нэмэлт ажил — ЗУРАГ заавал (v3)
    "google_maps_api_key": "",         # v4.2: Google Maps JS API түлхүүр (ажлын байр зурагнаас сонгох)
    "demo_version": "5",
}

WEEKDAY_MN = {1: "Даваа", 2: "Мягмар", 3: "Лхагва", 4: "Пүрэв",
              5: "Баасан", 6: "Бямба", 7: "Ням"}
MONTH_MN = {1: "1-р сар", 2: "2-р сар", 3: "3-р сар", 4: "4-р сар", 5: "5-р сар",
            6: "6-р сар", 7: "7-р сар", 8: "8-р сар", 9: "9-р сар", 10: "10-р сар",
            11: "11-р сар", 12: "12-р сар"}

STATUS_MN = {
    "not_checked_in": "Бүртгүүлээгүй",
    "working": "Ажиллаж байна",
    "done": "Ажил дууссан",
}


# --------------------------------------------------------------------------
# DB холболт
# --------------------------------------------------------------------------
def connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sites (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    address     TEXT DEFAULT '',
    lat         REAL,
    lng         REAL,
    radius_m    REAL NOT NULL DEFAULT 300,
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS employees (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT UNIQUE NOT NULL,
    full_name   TEXT NOT NULL,
    department  TEXT DEFAULT '',
    position    TEXT DEFAULT '',
    pin         TEXT NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1,
    daily_rate  REAL NOT NULL DEFAULT 0,      -- өдрийн цалин (₮)
    night_role  TEXT NOT NULL DEFAULT 'worker', -- guard (50%) | worker (100%)
    site_id     INTEGER REFERENCES sites(id), -- тухайн ажилтны ажлын байр
    geofence_mode TEXT NOT NULL DEFAULT 'site', -- site | custom | off (v4.3: жолооч гэх мэт)
    geo_lat     REAL,                          -- өөрийн байршил (гео хаалтын төв)
    geo_lng     REAL,
    geo_radius_m REAL,                         -- өөрийн радиус (м)
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS leaves (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id  INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL,                 -- v3.1: зөвхөн «чөлөө»
    start_date   TEXT NOT NULL,
    end_date     TEXT,                          -- олон хоногийн чөлөө
    all_day      INTEGER NOT NULL DEFAULT 1,
    start_time   TEXT, end_time TEXT,           -- цагаар олгосон чөлөө
    hours        REAL NOT NULL DEFAULT 0,
    approved     INTEGER NOT NULL DEFAULT 1,    -- хуучин талбар (status-тай нийцүүлнэ)
    status       TEXT NOT NULL DEFAULT 'approved',  -- pending | approved | rejected
    paid         INTEGER NOT NULL DEFAULT 0,        -- тухайн чөлөө цалинтай эсэх
    note         TEXT DEFAULT '',
    requested_by TEXT DEFAULT 'admin',              -- admin | employee
    decided_at   TEXT, decided_by TEXT,
    created_by   TEXT DEFAULT 'admin',
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attendance (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id      INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    work_date        TEXT NOT NULL,              -- YYYY-MM-DD (company timezone)
    clock_in         TEXT,                       -- YYYY-MM-DD HH:MM:SS (local)
    in_lat           REAL, in_lng REAL, in_distance_m REAL, in_accuracy_m REAL,
    clock_out        TEXT,
    out_lat          REAL, out_lng REAL, out_distance_m REAL, out_accuracy_m REAL,
    late_minutes     INTEGER NOT NULL DEFAULT 0,
    early_minutes    INTEGER NOT NULL DEFAULT 0,
    worked_minutes   INTEGER NOT NULL DEFAULT 0,
    break_minutes    INTEGER NOT NULL DEFAULT 0,
    deduct_minutes   INTEGER NOT NULL DEFAULT 0,
    payable_minutes  INTEGER NOT NULL DEFAULT 0,
    is_workday       INTEGER NOT NULL DEFAULT 1,
    -- ---- Цалин / ээлж (v2) ----
    shift_type       TEXT NOT NULL DEFAULT 'day',      -- day | night
    night_role       TEXT,                             -- guard | worker
    site_id          INTEGER,
    day_rate_snapshot REAL NOT NULL DEFAULT 0,         -- тухайн үеийн өдрийн цалин
    day_credit       REAL NOT NULL DEFAULT 0,          -- хэдэн өдрийн хөдөлмөр (1.0 = бүтэн өдөр)
    pay_multiplier   REAL NOT NULL DEFAULT 1,          -- шөнийн коэффициент (0.5 / 1.0)
    excused_minutes  INTEGER NOT NULL DEFAULT 0,       -- чөлөөгөөр хамгаалагдсан минут
    extra_minutes    INTEGER NOT NULL DEFAULT 0,       -- админы нэмсэн нэмэлт цаг
    pay_base         REAL NOT NULL DEFAULT 0,          -- үндсэн цалин
    pay_extra        REAL NOT NULL DEFAULT 0,          -- нэмэлт цагийн цалин
    pay_amount       REAL NOT NULL DEFAULT 0,          -- нийт цалин
    status           TEXT NOT NULL DEFAULT 'working',   -- working | completed
    note             TEXT DEFAULT '',
    edited           INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    UNIQUE(employee_id, work_date)
);
CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT PRIMARY KEY,
    role        TEXT NOT NULL,                 -- employee | admin
    employee_id INTEGER,
    label       TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS api_keys (
    key         TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'agent', -- agent | admin
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    last_used   TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL,
    actor      TEXT NOT NULL,
    action     TEXT NOT NULL,
    detail     TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS work_segments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id  INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    work_date    TEXT NOT NULL,                 -- YYYY-MM-DD
    kind         TEXT NOT NULL DEFAULT 'extra', -- extra | night
    start_ts     TEXT NOT NULL,
    end_ts       TEXT,
    start_photo  TEXT,                          -- нэмэлт ажил эхлэх зураг
    end_photo    TEXT,                          -- нэмэлт ажил дуусах зураг
    minutes      INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'open',  -- open | closed | approved | rejected
    note         TEXT DEFAULT '',
    created_at   TEXT NOT NULL,
    approved_by  TEXT
);
CREATE TABLE IF NOT EXISTS notifications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id  INTEGER,                       -- NULL = админд
    kind         TEXT NOT NULL,                 -- start | end | missed_in | missed_out | absent | info
    title        TEXT NOT NULL,
    body         TEXT DEFAULT '',
    meta         TEXT DEFAULT '',               -- JSON (сонголтоор)
    dedupe       TEXT,                          -- нэг өдөрт нэг л удаа
    created_at   TEXT NOT NULL,
    read_at      TEXT
);
CREATE TABLE IF NOT EXISTS advances (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id  INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    period_key   TEXT NOT NULL,               -- 'YYYY-MM' — 10-нд олгох үндсэн цалингийн үе
    window_start TEXT NOT NULL,               -- авансын цонх (11-ээс)
    window_end   TEXT NOT NULL,               -- ... 24 хүртэл
    full_days    INTEGER NOT NULL DEFAULT 0,  -- бүтэн ажилласан өдрийн тоо
    amount       REAL NOT NULL DEFAULT 0,     -- олгосон аванс (₮)
    status       TEXT NOT NULL DEFAULT 'paid',-- paid | pending | cancelled
    paid_on      TEXT,                        -- олгосон огноо
    note         TEXT DEFAULT '',
    created_by   TEXT DEFAULT 'admin',
    created_at   TEXT NOT NULL,
    updated_at   TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_adv_unique ON advances(employee_id, period_key);
CREATE INDEX IF NOT EXISTS idx_adv_period ON advances(period_key);
CREATE UNIQUE INDEX IF NOT EXISTS idx_notif_dedupe ON notifications(dedupe) WHERE dedupe IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_seg_emp ON work_segments(employee_id, work_date);
CREATE INDEX IF NOT EXISTS idx_att_date ON attendance(work_date);
CREATE INDEX IF NOT EXISTS idx_leave_emp ON leaves(employee_id, start_date);
CREATE INDEX IF NOT EXISTS idx_att_emp  ON attendance(employee_id);
"""


EMPLOYEE_V2_COLS = {
    "daily_rate": "REAL NOT NULL DEFAULT 0",
    "night_role": "TEXT NOT NULL DEFAULT 'worker'",
    "site_id": "INTEGER",
}
EMPLOYEE_V43_COLS = {
    # v4.3: ажилтан бүрийн гео хаалт — талбайгаа дагах | өөрийн байршил+радиус | идэвхгүй
    "geofence_mode": "TEXT NOT NULL DEFAULT 'site'",
    "geo_lat": "REAL",
    "geo_lng": "REAL",
    "geo_radius_m": "REAL",
}
ATTENDANCE_V4_COLS = {
    # v3.1: өдрийн төлөв (хэвийн | чөлөө | ирээгүй | ажиллаж байна | амралтын өдөр)
    "day_status": "TEXT DEFAULT ''",
    "absent_minutes": "INTEGER NOT NULL DEFAULT 0",
    "leave_minutes": "INTEGER NOT NULL DEFAULT 0",
}

ATTENDANCE_V3_COLS = {
    "in_photo": "TEXT",               # ажил эхлэх зургийн зам (data/photos/…)
    "out_photo": "TEXT",              # ажил дуусах зургийн зам
    "in_photo_ts": "TEXT",            # зураг авсан цаг
    "out_photo_ts": "TEXT",
    "photo_source": "TEXT",           # camera | file
    "extra_admin_minutes": "INTEGER NOT NULL DEFAULT 0",    # админы гараар нэмсэн
    "extra_segment_minutes": "INTEGER NOT NULL DEFAULT 0",  # нэмэлт ажлын сегментээс
}
ATTENDANCE_V2_COLS = {
    "shift_type": "TEXT NOT NULL DEFAULT 'day'",
    "night_role": "TEXT",
    "site_id": "INTEGER",
    "day_rate_snapshot": "REAL NOT NULL DEFAULT 0",
    "day_credit": "REAL NOT NULL DEFAULT 0",
    "pay_multiplier": "REAL NOT NULL DEFAULT 1",
    "excused_minutes": "INTEGER NOT NULL DEFAULT 0",
    "extra_minutes": "INTEGER NOT NULL DEFAULT 0",
    "pay_base": "REAL NOT NULL DEFAULT 0",
    "pay_extra": "REAL NOT NULL DEFAULT 0",
    "pay_amount": "REAL NOT NULL DEFAULT 0",
}


def migrate(con) -> None:
    """Хуучин мэдээллийн санг v2 схем рүү шилжүүлнэ (idempotent)."""
    def cols(table):
        return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}

    ec = cols("employees")
    for name, ddl in EMPLOYEE_V2_COLS.items():
        if name not in ec:
            con.execute(f"ALTER TABLE employees ADD COLUMN {name} {ddl}")
    for name, ddl in EMPLOYEE_V43_COLS.items():
        if name not in ec:
            con.execute(f"ALTER TABLE employees ADD COLUMN {name} {ddl}")
    ac = cols("attendance")
    for name, ddl in ATTENDANCE_V2_COLS.items():
        if name not in ac:
            con.execute(f"ALTER TABLE attendance ADD COLUMN {name} {ddl}")
    for name, ddl in ATTENDANCE_V3_COLS.items():
        if name not in ac:
            con.execute(f"ALTER TABLE attendance ADD COLUMN {name} {ddl}")
    # v2 → v3: ажлын хуваарийг 09:00–19:00 + үдийн завсарлага 13:00–14:00 болгож шилжүүлнэ
    row = con.execute("SELECT value FROM settings WHERE key='demo_version'").fetchone()
    ver = int(float(row["value"])) if row and str(row["value"]).strip() else 2
    if ver < 3:
        stamp = now_local().strftime("%Y-%m-%d %H:%M:%S")
        for k, v in (("schedule_start", "09:00"), ("schedule_end", "19:00"),
                     ("lunch_start", "13:00"), ("lunch_end", "14:00"), ("lunch_paid", "0"),
                     ("require_photo", "1"), ("demo_version", "3")):
            con.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, v))
        con.execute("UPDATE attendance SET extra_admin_minutes = extra_minutes"
                    " WHERE COALESCE(extra_minutes,0) > 0 AND COALESCE(extra_admin_minutes,0) = 0")
        con.execute("INSERT INTO audit_log(ts,actor,action,detail) VALUES(?,?,?,?)",
                    (stamp, "system", "migrate_v3",
                     "Ажлын хуваарь 09:00–19:00, үдийн завсарлага 13:00–14:00, фото шаардлагатай"))
    # v3.1: нэг төрлийн чөлөө (чөлөө / ирээгүй / хэвийн) + хүсэлт→батлах урсгал
    lc = cols("leaves")
    for name, ddl in (("status", "TEXT NOT NULL DEFAULT 'approved'"),
                      ("paid", "INTEGER NOT NULL DEFAULT 0"),
                      ("requested_by", "TEXT DEFAULT 'admin'"),
                      ("decided_at", "TEXT"), ("decided_by", "TEXT")):
        if name not in lc:
            con.execute(f"ALTER TABLE leaves ADD COLUMN {name} {ddl}")
    ac2 = cols("attendance")
    for name, ddl in ATTENDANCE_V4_COLS.items():
        if name not in ac2:
            con.execute(f"ALTER TABLE attendance ADD COLUMN {name} {ddl}")
    row = con.execute("SELECT value FROM settings WHERE key='demo_version'").fetchone()
    ver2 = int(float(row["value"])) if row and str(row["value"]).strip() else 2
    if ver2 < 4:
        # хуучин амралт/өвчтэй → чөлөө (цалинтай нь хэвээр)
        con.execute("UPDATE leaves SET paid=1 WHERE kind IN ('амралт','өвчтэй')")
        con.execute("UPDATE leaves SET kind='чөлөө' WHERE kind <> 'чөлөө'")
        con.execute("UPDATE leaves SET status=CASE WHEN approved=1 THEN 'approved' ELSE 'rejected' END"
                    " WHERE COALESCE(status,'')=''")
        con.execute("UPDATE leaves SET approved=CASE WHEN status='approved' THEN 1 ELSE 0 END")
        stamp2 = now_local().strftime("%Y-%m-%d %H:%M:%S")
        for k, v in (("demo_version", "4"), ("paid_leave_kinds", "")):
            con.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, v))
        con.execute("INSERT INTO audit_log(ts,actor,action,detail) VALUES(?,?,?,?)",
                    (stamp2, "system", "migrate_v31",
                     "Чөлөөний төрөл нэг болов (амралт/өвчтэй → чөлөө, paid=1); хүсэлт→батлах урсгал нэмэгдэв"))
    # v4.1: цагийн тариф — өдрийн цалинг ажлын бүтэн цагт (үдийн завсарлага орсон) хуваана
    row = con.execute("SELECT value FROM settings WHERE key='demo_version'").fetchone()
    ver3 = int(float(row["value"])) if row and str(row["value"]).strip() else 2
    if ver3 < 5:
        stamp3 = now_local().strftime("%Y-%m-%d %H:%M:%S")
        con.execute("INSERT INTO settings(key,value) VALUES('lunch_paid','1')"
                    " ON CONFLICT(key) DO UPDATE SET value='1'")
        con.execute("INSERT INTO settings(key,value) VALUES('demo_version','5')"
                    " ON CONFLICT(key) DO UPDATE SET value='5'")
        con.execute("INSERT INTO audit_log(ts,actor,action,detail) VALUES(?,?,?,?)",
                    (stamp3, "system", "migrate_v41",
                     "Үдийн завсарлага цалинтай болов: цагийн тариф = өдрийн цалин ÷ 10ц (150 000₮ → 15 000₮/ц), "
                     "шөнийн 19:00–03:00 = 8ц (18 750₮/ц)"))
    # v4.3: ажилтан бүрд гео хаалтын горим (талбайгаа дагах | өөрийн | идэвхгүй)
    row = con.execute("SELECT value FROM settings WHERE key='demo_version'").fetchone()
    ver4 = int(float(row["value"])) if row and str(row["value"]).strip() else 2
    if ver4 < 6:
        stamp4 = now_local().strftime("%Y-%m-%d %H:%M:%S")
        con.execute("INSERT INTO settings(key,value) VALUES('demo_version','6')"
                    " ON CONFLICT(key) DO UPDATE SET value='6'")
        con.execute("INSERT INTO audit_log(ts,actor,action,detail) VALUES(?,?,?,?)",
                    (stamp4, "system", "migrate_v43",
                     "Ажилтан бүрийн гео хаалт: горим (талбай/өөрийн/идэвхгүй) + өөрийн байршил, радиус"))


def init_db(seed: bool = True) -> None:
    seeded = False
    with _lock, connect() as con:
        con.executescript(SCHEMA)
        migrate(con)
        for k, v in DEFAULT_SETTINGS.items():
            con.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?,?)", (k, v))
        n = con.execute("SELECT COUNT(*) c FROM employees").fetchone()["c"]
        if seed and n == 0:
            _seed(con)
            seeded = True
        con.commit()
    # v4.5: 25-ны авансын демо төлөв — шинэ сан дээр нэг удаа (тусдаа холболт)
    if seeded:
        try:
            demo_seed_advances(period_key_for(), pending_codes=("EMP011",))
        except Exception as e:                               # noqa
            print("авансын демо seed алгасав:", e)


# --------------------------------------------------------------------------
# Тохиргоо (settings helpers)
# --------------------------------------------------------------------------
def get_setting(key: str, default: str = "") -> str:
    with connect() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else DEFAULT_SETTINGS.get(key, default)


def get_settings() -> dict:
    with connect() as con:
        rows = con.execute("SELECT key, value FROM settings").fetchall()
    out = dict(DEFAULT_SETTINGS)
    out.update({r["key"]: r["value"] for r in rows})
    return out


SCHEDULE_KEYS = {"schedule_start", "schedule_end", "grace_minutes",
                 "lunch_deduct_minutes", "workdays", "min_worked_minutes_for_break"}


def set_settings(values: dict) -> dict:
    changed = []
    with _lock, connect() as con:
        for k, v in values.items():
            if k not in DEFAULT_SETTINGS:
                continue
            if k == "admin_password" and not str(v):
                continue
            before = con.execute("SELECT value FROM settings WHERE key=?", (k,)).fetchone()
            if before and before["value"] == str(v):
                continue
            con.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))
            changed.append(k)
        con.commit()
    # Хуваарьт нөлөөлөх тохиргоо өөрчлөгдвөл бүх бүртгэлийг дахин тооцоолно
    if changed and SCHEDULE_KEYS & set(changed):
        n = recalc_all()
        audit("system", "recalc_all", f"{n} бүртгэл дахин тооцоологдлоо (тохиргоо өөрчлөгдсөн)")
    return get_settings()


def tz() -> ZoneInfo:
    try:
        return ZoneInfo(get_setting("timezone") or "Asia/Ulaanbaatar")
    except Exception:
        return ZoneInfo("Asia/Ulaanbaatar")


def now_local() -> datetime:
    return datetime.now(tz()).replace(tzinfo=None)


def today_str() -> str:
    return now_local().strftime("%Y-%m-%d")


# --------------------------------------------------------------------------
# Ажлын хуваарь (schedule helpers)
# --------------------------------------------------------------------------
def parse_hhmm(value: str) -> time:
    try:
        h, m = str(value).strip().split(":")[:2]
        return time(int(h) % 24, int(m) % 60)
    except Exception:
        return time(9, 0)


def workday_list() -> list[int]:
    raw = get_setting("workdays") or "1,2,3,4,5"
    days = []
    for part in str(raw).split(","):
        part = part.strip()
        if part.isdigit() and 1 <= int(part) <= 7:
            days.append(int(part))
    return sorted(set(days)) or [1, 2, 3, 4, 5]


def is_workday(d: date | str) -> bool:
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return d.isoweekday() in workday_list()


def schedule_window(day: str) -> tuple[datetime, datetime]:
    """Ажлын эхлэх / дуусах цагийг тухайн өдрийн datetime болгоно."""
    d = date.fromisoformat(day)
    s = get_settings()
    start = datetime.combine(d, parse_hhmm(s["schedule_start"]))
    end = datetime.combine(d, parse_hhmm(s["schedule_end"]))
    if end <= start:                             # шөнийн ээлж (жишээ: 22:00-06:00)
        end += timedelta(days=1)
    return start, end


def lunch_window(day: str) -> tuple[datetime, datetime] | None:
    """Үдийн завсарлагын цонх (хоосон бол None)."""
    s = get_settings()
    a, b = str(s.get("lunch_start") or ""), str(s.get("lunch_end") or "")
    if not a or not b:
        return None
    d = date.fromisoformat(day)
    st, en = datetime.combine(d, parse_hhmm(a)), datetime.combine(d, parse_hhmm(b))
    if en <= st:
        en += timedelta(days=1)
    return st, en


def shift_minutes(day: str | None = None, shift: str = "day") -> int:
    """
    Ээлжийн бүтэн цонхны минут:
      * өдрийн ээлж 09:00–19:00 = 600 мин (10 цаг) — үдийн завсарлага ОРСОН
      * шөнийн ээлж 19:00–03:00 = 480 мин (8 цаг)
    """
    day = day or today_str()
    if shift == "night":
        ns, ne = night_window(day)
        return max(1, _minutes_between(ns, ne))
    return paid_minutes_per_day(day)


def paid_minutes_per_day(day: str | None = None) -> int:
    """
    Бүтэн ажлын өдрийн ТӨЛБӨРТЭЙ минут = ажлын цагийн цонх (09:00–19:00 = 600 мин = 10 цаг).
    Үдийн завсарлага 13:00–14:00 нь `lunch_paid=1` үед цалинтай тул хасагдахгүй
    (`lunch_paid=0` бол хуучин горимоор 540 мин).
    """
    day = day or today_str()
    s = get_settings()
    start, end = schedule_window(day)
    total = max(1, _minutes_between(start, end))
    lw = lunch_window(day)
    if lw and str(s.get("lunch_paid") or "0") != "1":
        total -= max(0, _minutes_between(*lw))
    return max(1, total)


def lunch_deducted(cin: datetime | None, cout: datetime | None, day: str) -> int:
    """Хэрэв ажилтан үдийн завсарлагын үеэр ажил дээр байсан бол хасагдах минут."""
    s = get_settings()
    if not cin or not cout or str(s.get("lunch_paid") or "0") == "1":
        return 0
    lw = lunch_window(day)
    if not lw:
        # хуучин горим: тогтмол хасалт
        flat = int(float(s.get("lunch_deduct_minutes") or 0))
        worked = _minutes_between(cin, cout)
        if flat and worked >= int(float(s.get("min_worked_minutes_for_break") or 240)):
            return min(flat, worked)
        return 0
    lo, hi = max(cin, lw[0]), min(cout, lw[1])
    return max(0, _minutes_between(lo, hi)) if hi > lo else 0


def segment_day_night_minutes(employee_id: int, day: str) -> tuple[int, int]:
    """
    Тухайн өдрийн нэмэлт ажлын сегментүүдийг 19:00–03:00 шөнийн цонхтой харьцуулж
    (өдрийн минут, шөнийн минут) болгон хуваана. Шөнийн минут 18 750₮/ц,
    өдрийн минут 15 000₮/ц (150 000₮ өдрийн цалингийн жишээгээр) тооцогдоно.
    """
    try:
        ns, ne = night_window(day)
    except Exception:
        return 0, 0
    day_min = night_min = 0
    with connect() as con:
        segs = con.execute(
            "SELECT start_ts, end_ts, minutes FROM work_segments"
            " WHERE employee_id=? AND work_date=?", (employee_id, day)).fetchall()
    for sg in segs:
        st = parse_dt(sg["start_ts"])
        en = parse_dt(sg["end_ts"]) or parse_dt(sg["start_ts"])
        if not st or not en:
            continue
        total = int(sg["minutes"] or 0) or max(0, _minutes_between(st, en))
        if en <= ns or st >= ne:
            night = 0
        else:
            night = max(0, _minutes_between(max(st, ns), min(en, ne)))
        night_min += night
        day_min += max(0, total - night)
    return day_min, night_min


def hourly_rate(daily_rate, shift: str = "day", mult: float = 1.0) -> float:
    """
    Цагийн тариф = (өдрийн цалин × ээлжийн коэффициент) ÷ ээлжийн бүтэн цаг.
      * өдөр: 150 000₮ ÷ 10ц = 15 000₮/ц (үдийн завсарлага орсон)
      * шөнө: 150 000₮ ÷ 8ц  = 18 750₮/ц (хамгаалалт 50% бол 9 375₮/ц)
    """
    mins = shift_minutes(today_str(), shift)
    return float(daily_rate or 0) * float(mult or 1.0) / (mins / 60.0)


# --------------------------------------------------------------------------
# Гео хаалт (geofencing)
# --------------------------------------------------------------------------
def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def check_geofence(lat, lng, demo: bool = False, emp: dict | None = None) -> dict:
    """Ажлын байрны хүрээнд байгаа эсэхийг шалгана (ажилтны талбайг харгалзана)."""
    s = get_settings()
    geo = effective_geo(emp)
    if geo["enabled"] != "1" if isinstance(geo["enabled"], str) else not geo["enabled"]:
        msg = ("Энэ ажилтанд гео хаалт идэвхгүй — байршил хязгаарлагдахгүй."  # v4.3: жолооч г.м.
               if (geo.get("mode") == "off" or geo.get("source") == "off") else "")
        return {"ok": True, "enabled": False, "distance_m": None, "mode": geo.get("mode", "site"),
                "radius_m": geo["radius_m"], "site": geo["name"], "message": msg}
    if (lat is None or lng is None) and demo and s["demo_mode"] == "1":
        # Туршилтийн горим — хэрэглэгч зөвшөөрсөн, аудит бүртгэлд тэмдэглэнэ
        return {"ok": True, "enabled": True, "distance_m": None,
                "radius_m": geo["radius_m"], "site": geo["name"], "demo": True,
                "mode": geo.get("mode", "site"), "source": geo.get("source", "site"),
                "message": "Туршилтийн горимд бүртгэл хийгдлээ."}
    if lat is None or lng is None:
        return {"ok": False, "enabled": True, "distance_m": None, "site": geo["name"],
                "radius_m": geo["radius_m"], "mode": geo.get("mode", "site"),
                "source": geo.get("source", "site"),
                "message": "Байршил тодорхойлогдоогүй. Та GPS-ээ асаана уу."}
    try:
        lat = float(lat); lng = float(lng)
    except (TypeError, ValueError):
        return {"ok": False, "enabled": True, "distance_m": None, "site": geo["name"],
                "radius_m": geo["radius_m"], "mode": geo.get("mode", "site"),
                "source": geo.get("source", "site"),
                "message": "Байршлын утга буруу байна."}
    dist = haversine_m(lat, lng, geo["lat"], geo["lng"])
    radius = float(geo["radius_m"])
    ok = dist <= radius
    return {
        "ok": ok, "enabled": True, "distance_m": round(dist, 1), "radius_m": radius,
        "site_id": geo["site_id"], "site": geo["name"],
        "mode": geo.get("mode", "site"), "source": geo.get("source", "site"),
        "message": "" if ok else "Та ажлын байрандаа байхгүй байна. Бүртгэл амжилтгүй.",
    }


# --------------------------------------------------------------------------
# Тооцоолол (variance calculation)
# --------------------------------------------------------------------------
def _minutes_between(a: datetime, b: datetime) -> int:
    return int(round((b - a).total_seconds() / 60.0))


def night_window(day: str) -> tuple[datetime, datetime]:
    """Шөнийн ээлжийн цонх — тухайн өдрийн 19:00 → дараа өдрийн 03:00."""
    s = get_settings()
    d = date.fromisoformat(day)
    ns = datetime.combine(d, parse_hhmm(s["night_start"]))
    ne = datetime.combine(d, parse_hhmm(s["night_end"]))
    if ne <= ns:
        ne += timedelta(days=1)
    return ns, ne


NIGHT_EARLY_MINUTES = 90   # шөнийн ээлжид цагаасаа өмнө ирэх зөвшөөрөгдөх хугацаа


def detect_shift(cin: datetime | None, day: str) -> str:
    """
    Ирсэн цагаар өдрийн / шөнийн ээлжийг тодорхойлно.
    19:00-ийн 90 минутын өмнөөс хойш ирсэн бол шөнийн ээлж (хамгаалагч цагаасаа
    өмнө ирдэг), шөнө дундын дараах (03:00 хүртэлх) бүртгэл мөн шөнийн ээлж.
    """
    if not cin:
        return "day"
    s = get_settings()
    ns, ne = parse_hhmm(s["night_start"]), parse_hhmm(s["night_end"])
    t = cin.time()
    early_from = (datetime.combine(cin.date(), ns) - timedelta(minutes=NIGHT_EARLY_MINUTES)).time()
    if t >= early_from or t < min(ne, time(6, 0)):
        return "night"
    return "day"


def leave_minutes_for_window(employee_id: int, day: str,
                             window_start: datetime, window_end: datetime) -> int:
    """Тухайн өдөрт олгогдсон, зөвшөөрөгдсөн чөлөөний минут (цонхтой давхцал)."""
    if not employee_id:
        return 0
    total = 0
    with connect() as con:
        rows = con.execute(
            "SELECT * FROM leaves WHERE employee_id=? AND status='approved' AND start_date<=? "
            "AND COALESCE(end_date, start_date)>=?",
            (employee_id, day, day)).fetchall()
    d = date.fromisoformat(day)
    spans: list[tuple[datetime, datetime]] = []
    for r in rows:
        if int(r["all_day"] or 0) == 1:
            return _minutes_between(window_start, window_end)   # бүтэн өдөр чөлөө
        st, et = r["start_time"], r["end_time"]
        if not st or not et:
            continue
        a = datetime.combine(d, parse_hhmm(st))
        b = datetime.combine(d, parse_hhmm(et))
        if b <= a:                      # шөнийн цагаар олгосон чөлөө (ж: 22:00–02:00)
            b += timedelta(days=1)
        lo = max(a, window_start)
        hi = min(b, window_end)
        if hi > lo:
            spans.append((lo, hi))
    # Давхцсан чөлөөнүүдийг нэгтгэнэ (давхар тоолохгүй)
    spans.sort()
    end = None
    for lo, hi in spans:
        if end is None or lo > end:
            total += _minutes_between(lo, hi)
            end = hi
        elif hi > end:
            total += _minutes_between(end, hi)
            end = hi
    return total


def recalc(record: dict, day: str | None = None, force_workday: bool = False,
           employee: dict | None = None, extra_minutes: int | None = None) -> dict:
    """
    Бүртгэлийг ажлын хуваарь болон ээлжийн төрлөөр дахин тооцоолно:
    хоцролт, эрт явалт, ажилласан минут, өдрийн хөдөлмөр (day_credit) ба цалин.
    """
    s = get_settings()
    day = day or record.get("work_date") or today_str()
    d = date.fromisoformat(day)
    start, end = schedule_window(day)
    ns, ne = night_window(day)
    grace = int(float(s["grace_minutes"] or 0))
    workday = True if force_workday else is_workday(day)
    if not workday and record.get("clock_in"):
        workday = True          # бүртгэл (ажил) байгаа өдөр = ажлын өдөр — төлөв «off» болж хувирахгүй

    cin = parse_dt(record.get("clock_in"))
    cout = parse_dt(record.get("clock_out"))

    emp = employee
    if emp is None and record.get("employee_id"):
        emp = get_employee(int(record["employee_id"]))
    rate = float(record.get("day_rate_snapshot") or 0) or float(
        (emp or {}).get("daily_rate") or 0) or float(s["default_daily_rate"] or 0)
    role = record.get("night_role") or (emp or {}).get("night_role") or "worker"

    stored = record.get("shift_type")
    shift = detect_shift(cin, day) if stored in (None, "", "day") else stored
    if shift not in ("day", "night"):
        shift = "day"

    late = early = excused = 0
    worked = 0
    if cin and cout:
        # зөвхөн ээлжийн цонх доторх цаг тооцогдоно (цагнаас өмнөх/хойшхи цаг нь
        # «нэмэлт ажил» сегментээр тусдаа бүртгэгдэнэ)
        w_lo, w_hi = (ns, ne) if shift == "night" else (start, end)
        worked = max(0, _minutes_between(max(cin, w_lo), min(cout, w_hi)))

    if shift == "night":
        window = max(1, _minutes_between(ns, ne))
        if cin and workday:
            late = max(0, _minutes_between(ns + timedelta(minutes=grace), cin))
        if cout and workday:
            early = max(0, _minutes_between(cout, ne))
        excused = leave_minutes_for_window(record.get("employee_id"), day, ns, ne)
        credit = min(1.0, worked / window) if worked else 0.0
        mult = (float(s["guard_percent"]) if role == "guard" else float(s["worker_percent"])) / 100.0
    else:
        window = paid_minutes_per_day(day)      # 09:00–19:00 = 600 мин = 10ц (үдийн завсарлага цалинтай)
        late_raw = max(0, _minutes_between(start + timedelta(minutes=grace), cin)) if cin and workday else 0
        early_raw = max(0, _minutes_between(cout, end)) if cout and workday else 0
        excused = leave_minutes_for_window(record.get("employee_id"), day, start, end)
        # чөлөө эхлээд хоцролтыг, дараа нь эрт явалтыг нөхнө
        late = max(0, late_raw - excused)
        early = max(0, early_raw - max(0, excused - late_raw))
        credit = 0.0
        mult = 1.0

    brk = lunch_deducted(cin, cout, day) if worked else 0

    net_worked = max(0, worked - brk)
    deduct = min(net_worked, late + early) if net_worked else (late + early)
    payable = max(0, net_worked - deduct)

    if shift == "night":
        # шөнийн ээлжид өдрийн хөдөлмөрийн хэмжээг бүтэн цонхоор тооцно (19:00–03:00 = 1 өдөр)
        credit = min(1.0, (net_worked or 0) / window) if net_worked else 0.0
        pay_base = rate * mult * credit
    else:
        credited = min(window, payable)          # нэг өдөр хамгийн ихдээ = 1.0 ажлын өдөр
        credit = round(credited / window, 4) if window else 0.0
        pay_base = rate * (credited / window) if window else 0.0

    # Нэмэлт цаг = админы гараар нэмсэн + нэмэлт ажлын сегмент (фототой)
    admin_extra = int(record.get("extra_admin_minutes") or 0)
    seg_extra = int(record.get("extra_segment_minutes") or 0) if extra_minutes is None else int(extra_minutes)
    extra = admin_extra + seg_extra
    # Цагийн тариф (v4.1): өдрийн цалин ÷ ээлжийн бүтэн цаг — өдөр 10ц (15 000₮/ц),
    # шөнө 19:00–03:00 нь 8ц (18 750₮/ц). Сегментүүд цагийнхаа дагуу хуваагдана.
    ot_mult = float(s["overtime_multiplier"] or 1.0)
    night_mult = (float(s["guard_percent"]) if role == "guard" else float(s["worker_percent"])) / 100.0
    eid_for_seg = record.get("employee_id")
    seg_day, seg_night = (segment_day_night_minutes(int(eid_for_seg), day)
                          if eid_for_seg else (0, 0))
    if extra_minutes is not None and int(extra_minutes) and not (seg_day or seg_night):
        seg_day = int(extra_minutes)                    # хуучин дуудлага: өдрийн тарифаар
    if shift == "night":
        seg_night += admin_extra                        # шөнийн ээлжийн гараар нэмсэн цаг
    else:
        seg_day += admin_extra
    seg_day = max(seg_day, 0)
    pay_extra = (hourly_rate(rate, "day") * (seg_day / 60.0)
                 + hourly_rate(rate, "night", night_mult) * (seg_night / 60.0)) * ot_mult

    # ---- v3.1: өдрийн төлөв — зөвхөн хэвийн / чөлөө / ирээгүй -------------------
    grace_abs = int(float(s.get("absent_minutes_grace") or 10))
    now_dt = now_local()
    leave_minutes = excused if shift != "night" else 0
    if not workday:
        day_status, absent_m = "off", 0
    elif shift == "night":
        # шөнийн ээлж: бүтэн цонх эсвэл чөлөө
        if cin and cout:
            day_status, absent_m = ("normal", 0) if payable > 0 else ("absent", window)
        elif cin and not cout and now_dt < end + timedelta(minutes=grace_abs):
            day_status, absent_m = "working", 0
        elif cin and not cout:
            day_status, absent_m = "absent", window        # бүртгэлээ хаагаагүй — ажилтны буруу
        elif excused >= window - grace_abs:
            day_status, absent_m = "leave", 0
        else:
            day_status, absent_m = "absent", max(0, window - excused)
    elif not cin:
        if excused >= window - grace_abs:
            day_status, absent_m = "leave", 0
        else:
            day_status, absent_m = "absent", max(0, window - excused)   # ирээгүй
    elif not cout:
        if now_dt < end + timedelta(minutes=grace_abs):
            day_status, absent_m = "working", 0                          # ажиллаж байна
        else:
            day_status, absent_m = "absent", max(0, window - excused)    # хаагаагүй — ирээгүй
    else:
        # эрт явсан бол эсвэл дутуу ажилласан бол → «ирээгүй» цагууд
        tail = max(0, _minutes_between(cout, end))
        rest_leave = leave_minutes_for_window(int(record.get("employee_id") or 0), day,
                                              cout, end) if cout < end else 0
        lost = max(0, tail - rest_leave)
        if excused >= window - grace_abs and net_worked == 0:
            day_status, absent_m = "leave", 0
        elif lost > grace_abs:
            day_status, absent_m = "absent", min(window, lost)
        else:
            day_status, absent_m = ("leave" if excused > 0 else "normal"), 0

    rec = dict(record)
    rec.update({
        "work_date": day,
        "shift_type": shift,
        "day_status": day_status,
        "day_status_label": DAY_STATUS_LABEL.get(day_status, day_status),
        "day_status_color": DAY_STATUS_COLOR.get(day_status, "gray"),
        "absent_minutes": int(absent_m),
        "leave_minutes": int(leave_minutes),
        "night_role": role if shift == "night" else None,
        "day_rate_snapshot": round(rate, 2),
        "pay_multiplier": mult,
        "day_credit": round(credit, 4),
        "excused_minutes": int(excused),
        "extra_minutes": extra,
        "extra_admin_minutes": admin_extra,
        "extra_segment_minutes": seg_extra,
        "late_minutes": int(late),
        "early_minutes": int(early),
        "worked_minutes": net_worked,
        "break_minutes": brk,
        "deduct_minutes": int(deduct),
        "payable_minutes": int(payable),
        "pay_base": round(pay_base, 2),
        "pay_extra": round(pay_extra, 2),
        "pay_amount": round(pay_base + pay_extra, 2),
        "is_workday": 1 if workday else 0,
        "status": "completed" if cout else ("working" if cin else "not_checked_in"),
    })
    return rec


def parse_dt(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    txt = str(value).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(txt, fmt)
        except ValueError:
            continue
    return None


def fmt_time(value) -> str:
    dt = parse_dt(value)
    return dt.strftime("%H:%M") if dt else "—"


def fmt_hm(minutes: int | None) -> str:
    """Минутыг '8ц 15м' хэлбэрээр."""
    if minutes is None:
        return "—"
    m = int(minutes)
    sign = "-" if m < 0 else ""
    m = abs(m)
    return f"{sign}{m // 60}ц {m % 60:02d}м"


def fmt_hhmm(minutes: int | None) -> str:
    """Минутыг '08:15' (цаг:мин) хэлбэрээр — тайланд."""
    if minutes is None:
        return "00:00"
    m = int(minutes)
    sign = "-" if m < 0 else ""
    m = abs(m)
    return f"{sign}{m // 60:02d}:{m % 60:02d}"



# --------------------------------------------------------------------------
# Ажлын байрууд (sites) — ажилтан тус бүрд өөр байршил өгөх боломжтой
# --------------------------------------------------------------------------
def list_sites(active_only: bool = False) -> list[dict]:
    q = "SELECT * FROM sites"
    if active_only:
        q += " WHERE active=1"
    q += " ORDER BY id"
    with connect() as con:
        return [dict(r) for r in con.execute(q).fetchall()]


def get_site(site_id) -> dict | None:
    if not site_id:
        return None
    with connect() as con:
        r = con.execute("SELECT * FROM sites WHERE id=?", (int(site_id),)).fetchone()
    return dict(r) if r else None


_DMS_RE = re.compile(
    r"(?P<d>\d{1,3})[°\s]+(?:(?P<m>\d{1,2})['\u2032\s]+)?(?:(?P<s>\d{1,2}(?:\.\d+)?)[\"\u2033\s]*)?"
    r"(?P<h>[NSEWnsew])")


def _dms_to_deg(m: "re.Match[str]") -> float:
    d = float(m.group("d")) + float(m.group("m") or 0) / 60.0 + float(m.group("s") or 0) / 3600.0
    return -d if m.group("h").upper() in ("S", "W") else d


def parse_geo_text(text: str) -> dict:
    """
    Google Maps холбоос эсвэл координатын бичвэрээс (lat, lng) задлан авна.
    Гадаад сан, сүлжээ шаардахгүй — зөвхөн тэмдэгт мөр шинжилнэ.

    Дэмжих хэлбэрүүд:
      * https://www.google.com/maps/@47.9184,106.9177,16z
      * https://www.google.com/maps/place/.../data=...!3d47.9184!4d106.9177
      * https://maps.google.com/?q=47.9184,106.9177   (?query=, ?ll=, ?daddr=, ?center=)
      * https://www.google.com/maps/dir/47.9184,106.9177/47.92,106.93
      * 47.9184, 106.9177   эсвэл   47.9184 106.9177
      * 47°55'06.2"N 106°55'03.7"E   (DMS)
    Богино холбоос (maps.app.goo.gl) нь сүлжээгүйгээр задлагдахгүй — тодорхой алдаа буцаана.
    """
    raw = (text or "").strip()
    if not raw:
        return {"ok": False, "error": "Холбоос эсвэл координат оруулна уу."}
    t = unquote(raw).replace("\u00a0", " ")
    low = t.lower()
    if "goo.gl/maps" in low or "maps.app.goo.gl" in low:
        return {"ok": False, "short_link": True,
                "error": "Богино холбоосыг шууд задлах боломжгүй. Google Maps дээр нээгээд "
                         "хаягийн мөрнөөс бүтэн холбоосыг хуулж тавина уу."}
    if "google." not in low and "maps" not in low and not re.search(r"\d", t):
        return {"ok": False, "error": "Google Maps холбоос эсвэл координат олдсонгүй."}

    patterns = [
        ("google_link", r"!3d(-?\d{1,3}\.\d+)!4d(-?\d{1,3}\.\d+)"),
        ("google_link", r"@(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)"),
        ("google_link", r"[?&](?:q|query|ll|sll|daddr|destination|center)=(-?\d{1,3}\.\d+),\s*(-?\d{1,3}\.\d+)"),
        ("google_link", r"/(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)"),
        ("coords", r"(-?\d{1,3}\.\d+)\s*[,; ]\s*(-?\d{1,3}\.\d+)"),
    ]
    for source, pat in patterns:
        m = re.search(pat, t)
        if m:
            lat, lng = float(m.group(1)), float(m.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                zm = re.search(r",(\d{1,2}(?:\.\d+)?)z", t)
                return {"ok": True, "lat": round(lat, 6), "lng": round(lng, 6),
                        "zoom": int(float(zm.group(1))) if zm else None,
                        "source": source}

    # DMS: 47°55'06.2"N 106°55'03.7"E
    ms = list(_DMS_RE.finditer(t))
    if len(ms) >= 2:
        lat = next((_dms_to_deg(m) for m in ms if m.group("h").upper() in "NS"), None)
        lng = next((_dms_to_deg(m) for m in ms if m.group("h").upper() in "EW"), None)
        if lat is not None and lng is not None and -90 <= lat <= 90 and -180 <= lng <= 180:
            return {"ok": True, "lat": round(lat, 6), "lng": round(lng, 6),
                    "zoom": None, "source": "dms"}

    return {"ok": False, "error": "Координат олдсонгүй. Google Maps холбоос эсвэл "
                                  "«өргөрөг, уртраг» (ж: 47.9184, 106.9177) хэлбэрээр оруулна уу."}


def create_site(name, lat=None, lng=None, radius_m=300, address="") -> dict:
    now = now_local().strftime("%Y-%m-%d %H:%M:%S")
    with _lock, connect() as con:
        cur = con.execute(
            "INSERT INTO sites(name, address, lat, lng, radius_m, active, created_at) VALUES(?,?,?,?,?,1,?)",
            (name.strip(), address.strip(), lat, lng, float(radius_m or 300), now))
        con.commit()
        sid = cur.lastrowid
    audit("admin", "site_create", f"{name}")
    return get_site(sid)


def update_site(site_id: int, fields: dict) -> dict | None:
    allowed = {"name", "address", "lat", "lng", "radius_m", "active"}
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed and v is not None and v != "":
            sets.append(f"{k}=?")
            vals.append(float(v) if k in ("lat", "lng", "radius_m") else
                        (int(v) if k == "active" else str(v).strip()))
    if sets:
        vals.append(site_id)
        with _lock, connect() as con:
            con.execute(f"UPDATE sites SET {', '.join(sets)} WHERE id=?", vals)
            con.commit()
        audit("admin", "site_update", f"id={site_id} {fields}")
    return get_site(site_id)


def delete_site(site_id: int) -> None:
    with _lock, connect() as con:
        con.execute("UPDATE sites SET active=0 WHERE id=?", (site_id,))
        con.execute("UPDATE employees SET site_id=NULL WHERE site_id=?", (site_id,))
        con.commit()
    audit("admin", "site_delete", f"id={site_id}")


def employee_site(emp: dict | None) -> dict | None:
    """Ажилтны ажлын байр; тохируулаагүй бол үндсэн гео хаалт."""
    if not emp:
        return None
    site = get_site(emp.get("site_id"))
    if site and site.get("lat") is not None and site.get("lng") is not None:
        return site
    return None


GEOFENCE_MODES = ("site", "custom", "off")
GEOFENCE_MODE_LABEL = {"site": "Талбайгаа дагах", "custom": "Өөрийн байршил/радиус",
                       "off": "Идэвхгүй (хязгааргүй)"}


def effective_geo(emp: dict | None = None) -> dict:
    """
    Ажилтанд хамаарах гео хязгаар (v4.3):
      * `off`    — тухайн ажилтанд гео хаалт ХҮЧИНГҮЙ (жолооч, хээрийн ажилтан);
      * `custom` — ажилтны өөрийн байршил + радиус;
      * `site`   — (анхдагч) оноосон талбай, байхгүй бол баазын гео хаалт.
    """
    s = get_settings()
    if emp is not None and hasattr(emp, "keys"):        # sqlite3.Row → dict
        emp = dict(emp)
    emp = emp or {}
    mode = (emp.get("geofence_mode") or "site")
    if mode == "off":
        return {"source": "off", "mode": "off", "site_id": None,
                "name": (emp or {}).get("full_name") or "Ажилтан",
                "lat": None, "lng": None, "radius_m": None, "enabled": False}
    if mode == "custom" and emp and emp.get("geo_lat") is not None and emp.get("geo_lng") is not None:
        return {"source": "custom", "mode": "custom", "site_id": None,
                "name": f"{emp.get('full_name') or 'Ажилтан'} — өөрийн байршил",
                "lat": float(emp["geo_lat"]), "lng": float(emp["geo_lng"]),
                "radius_m": float(emp.get("geo_radius_m") or 300),
                "enabled": s["geofence_enabled"] == "1"}
    site = employee_site(emp)
    if site:
        return {"source": "site", "mode": "site", "site_id": site["id"], "name": site["name"],
                "lat": float(site["lat"]), "lng": float(site["lng"]),
                "radius_m": float(site["radius_m"] or 300),
                "enabled": s["geofence_enabled"] == "1"}
    return {"source": "default", "mode": "site", "site_id": None, "name": s["geofence_name"],
            "lat": float(s["geofence_lat"]), "lng": float(s["geofence_lng"]),
            "radius_m": float(s["geofence_radius_m"]),
            "enabled": s["geofence_enabled"] == "1"}


# --------------------------------------------------------------------------
# Чөлөө / амралт / өвчтэй (leaves)
# --------------------------------------------------------------------------
LEAVE_KINDS = ["чөлөө"]                       # v3.1: зөвхөн нэг төрөл
LEAVE_COLORS = {"чөлөө": "blue", "амралт": "blue", "өвчтэй": "blue"}
LEAVE_ALIASES = {"амралт": "чөлөө", "өвчтэй": "чөлөө", "чөлөө": "чөлөө"}
ABSENT_COLOR = "red"
LEAVE_STATUS_LABEL = {"pending": "Хүлээгдэж байна", "approved": "Батлагдсан",
                      "rejected": "Татгалзсан", "cancelled": "Цуцлагдсан"}
LEAVE_STATUS_COLOR = {"pending": "amber", "approved": "green", "rejected": "red",
                      "cancelled": "gray"}
# Өдрийн төлөв — зөвхөн гурван үндсэн төлөв (+ ажиллаж байна / амралтын өдөр)
DAY_STATUS_LABEL = {"normal": "Хэвийн", "leave": "Чөлөө", "absent": "Ирээгүй",
                    "working": "Ажиллаж байна", "off": "Амралтын өдөр",
                    "pending": "Хүлээгдэж байна"}     # v4.3: ажлын цаг эхлээгүй
DAY_STATUS_COLOR = {"normal": "green", "leave": "blue", "absent": "red",
                    "working": "teal", "off": "gray", "pending": "gray"}


def add_leave(employee_id: int, kind: str, start_date: str, end_date: str | None = None,
              all_day: bool = True, start_time: str | None = None,
              end_time: str | None = None, note: str = "", created_by: str = "admin",
              status: str = "approved", paid: int | None = None) -> dict:
    kind = LEAVE_ALIASES.get((kind or "").strip(), "чөлөө")
    if status not in ("pending", "approved", "rejected"):
        status = "approved"
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", start_date or ""):
        return {"ok": False, "error": "Эхлэх огноо буруу байна."}
    end = end_date or start_date
    if end < start_date:
        return {"ok": False, "error": "Дуусах огноо эхлэхээс өмнө байна."}
    hours = 0.0
    if not all_day:
        if not start_time or not end_time:
            return {"ok": False, "error": "Цагаар олгох бол эхлэх/дуусах цаг оруулна уу."}
        a, b = parse_hhmm(start_time), parse_hhmm(end_time)
        mins = (b.hour * 60 + b.minute) - (a.hour * 60 + a.minute)
        if mins <= 0:
            mins += 24 * 60
        hours = round(mins / 60.0, 2)
    else:
        dd, ed = date.fromisoformat(start_date), date.fromisoformat(end)
        days = 0
        while dd <= ed:
            if is_workday(dd):
                days += 1
            dd += timedelta(days=1)
        hours = round(days * (paid_minutes_per_day(start_date) / 60.0), 2)
    now = now_local().strftime("%Y-%m-%d %H:%M:%S")
    paid_v = 0 if paid is None else (1 if paid else 0)
    appr = 1 if status == "approved" else 0
    with _lock, connect() as con:
        cur = con.execute(
            "INSERT INTO leaves(employee_id, kind, start_date, end_date, all_day, start_time, "
            "end_time, hours, approved, status, paid, note, requested_by, created_by, created_at, "
            "decided_at, decided_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (employee_id, kind, start_date, end, 1 if all_day else 0,
             start_time if not all_day else None, end_time if not all_day else None,
             hours, appr, status, paid_v, note.strip(), created_by, created_by, now,
             now if status != "pending" else None, created_by if status != "pending" else None))
        con.commit()
        lid = cur.lastrowid
    if status == "approved":
        recalc_all(month=start_date[:7])
    audit(created_by if created_by in ("admin", "employee") else "admin",
          "leave_request" if status == "pending" else "leave_add",
          f"emp={employee_id} {kind} {start_date}→{end} "
          f"{'бүтэн өдөр' if all_day else str(start_time) + '-' + str(end_time)} status={status} paid={paid_v}")
    when = 'бүтэн өдөр' if all_day else f"{start_time}–{end_time}"
    msg = (f"{kind} хүсэлт илгээгдлээ ({when}). Админ баталсны дараа хүчинтэй болно."
           if status == "pending" else
           f"{kind} амжилттай олгогдлоо ({when})." + (" Цалинтай." if paid_v else " Цалингүй."))
    return {"ok": True, "leave": get_leave(lid), "message": msg}


def request_leave(employee_id: int, start_date: str, end_date: str | None = None,
                  all_day: bool = True, start_time: str | None = None,
                  end_time: str | None = None, note: str = "") -> dict:
    """Ажилтан аппаас чөлөө хүсэлт илгээнэ → админд мэдэгдэл очно."""
    end = end_date or start_date
    for x in list_leaves(None, employee_id):
        if int(x["all_day"] or 0) == 1 or all_day:
            xs, xe = str(x["start_date"]), str(x["end_date"] or x["start_date"])
            if not (end < xs or start_date > xe):
                if x["status"] == "approved":
                    return {"ok": False,
                            "error": f"Энэ хугацаанд чөлөө аль хэдийн батлагдсан байна ({xs} → {xe})."}
                if x["status"] == "pending":
                    return {"ok": False,
                            "error": f"Энэ хугацааны хүсэлт аль хэдийн илгээгдсэн, админы хариуг хүлээнэ үү ({xs} → {xe})."}
    res = add_leave(employee_id, "чөлөө", start_date, end_date, all_day, start_time, end_time,
                    note, created_by="employee", status="pending", paid=0)
    if not res.get("ok"):
        return res
    lv = res["leave"]
    e = get_employee(employee_id) or {}
    when = ("бүтэн өдөр" if int(lv["all_day"]) else f"{lv['start_time']}–{lv['end_time']}") \
        if lv["start_date"] == (lv["end_date"] or lv["start_date"]) else \
        f"{lv['start_date']} → {lv['end_date']}"
    # 1) Ажилтанд: хүсэлт хүлээн авсан баталгаа (шийдвэрийг хүлээнэ)
    notify(employee_id, "leave_request", "Чөлөөний хүсэлт илгээгдлээ",
           f"{when} ({lv['hours']}ц). Админ баталсны дараа хүчинтэй болно — "
           "батлагдах хүртэл тухайн цаг/өдөр «ирээгүй» хэвээр тооцогдоно.",
           meta={"leave_id": lv["id"], "status": "pending"},
           dedupe=f"leave_sent_{lv['id']}")
    # 2) Админд нэг л мэдэгдэл (мэдэгдлийн панелаас шууд Батлах/Татгалзах боломжтой)
    notify(None, "leave_request",
           f"ЧӨЛӨӨНИЙ ХҮСЭЛТ — {e.get('code','')} {e.get('full_name','')}",
           f"{when} · {lv['hours']}ц. Хүсэлтийг батлах эсвэл татгалзана уу."
           + (f" Тэмдэглэл: {lv.get('note')}" if lv.get("note") else ""),
           meta={"leave_id": lv["id"], "employee_id": employee_id, "code": e.get("code"),
                 "when": when, "hours": lv["hours"], "note": lv.get("note") or ""},
           dedupe=f"leave_req_{lv['id']}")
    return res


def decide_leave(leave_id: int, approve: bool = True, paid: int | None = None,
                 by: str = "admin") -> dict:
    """Админ хүсэлтийг батална/татгалзана → ажилтанд мэдэгдэл очно."""
    lv = get_leave(leave_id)
    if not lv:
        return {"ok": False, "error": "Хүсэлт олдсонгүй."}
    if (lv.get("status") or "") != "pending":
        return {"ok": False,
                "error": f"Энэ хүсэлт аль хэдийн шийдэгдсэн ({LEAVE_STATUS_LABEL.get(lv['status'], lv['status'])}). "
                         "Зөвхөн хүлээгдэж буй хүсэлтийг шийдэж болно."}
    status = "approved" if approve else "rejected"
    paid_v = int(lv.get("paid") or 0) if paid is None else (1 if paid else 0)
    stamp = now_local().strftime("%Y-%m-%d %H:%M:%S")
    with _lock, connect() as con:
        con.execute("UPDATE leaves SET status=?, approved=?, paid=?, decided_at=?, decided_by=?"
                    " WHERE id=?", (status, 1 if approve else 0, paid_v, stamp, by, leave_id))
        con.commit()
    if approve:
        recalc_all(month=str(lv["start_date"])[:7])
    who = f"{lv.get('code','')} {lv.get('full_name','')}".strip()
    when = ("бүтэн өдөр" if int(lv["all_day"]) else f"{lv['start_time']}–{lv['end_time']}")
    if lv["start_date"] != (lv["end_date"] or lv["start_date"]):
        when = f"{lv['start_date']} → {lv['end_date']}"
    notify(int(lv["employee_id"]), "leave_approved" if approve else "leave_rejected",
           "Чөлөөний хүсэлт батлагдлаа" if approve else "Чөлөөний хүсэлт татгалзагдлаа",
           (f"{when} — чөлөө олгогдлоо ({'цалинтай' if paid_v else 'цалингүй'})."
            if approve else
            f"{when} — хүсэлт татгалзагдлаа, тухайн цаг/өдөр «ирээгүй» хэвээр тооцогдоно."),
           meta={"leave_id": leave_id, "status": status, "paid": paid_v},
           dedupe=f"leave_dec_{leave_id}_{status}")
    audit(by, "leave_decide", f"id={leave_id} emp={lv['employee_id']} {status} paid={paid_v}")
    return {"ok": True, "leave": get_leave(leave_id),
            "message": (f"{who} — чөлөө батлагдлаа" + (" (цалинтай)." if paid_v else " (цалингүй)."))
                       if approve else f"{who} — чөлөөний хүсэлт татгалзагдлаа."}


def get_leave(leave_id: int) -> dict | None:
    with connect() as con:
        r = con.execute(
            "SELECT l.*, e.full_name, e.code FROM leaves l JOIN employees e ON e.id=l.employee_id "
            "WHERE l.id=?", (leave_id,)).fetchone()
    return dict(r) if r else None


def cancel_leave(leave_id: int, employee_id: int | None = None) -> dict:
    """Ажилтан өөрийн ХҮЛЭЭГДЭЖ БУЙ хүсэлтийг цуцална (админд мэдэгдэнэ)."""
    lv = get_leave(leave_id)
    if not lv:
        return {"ok": False, "error": "Хүсэлт олдсонгүй."}
    if employee_id and int(lv["employee_id"]) != int(employee_id):
        return {"ok": False, "error": "Энэ хүсэлт таных байхгүй байна."}
    if (lv.get("status") or "") != "pending":
        return {"ok": False, "error": "Зөвхөн хүлээгдэж буй хүсэлтийг цуцалж болно."}
    stamp = now_local().strftime("%Y-%m-%d %H:%M:%S")
    with _lock, connect() as con:
        con.execute("UPDATE leaves SET status='cancelled', approved=0, decided_at=?, decided_by=?"
                    " WHERE id=?", (stamp, lv.get("code") or "employee", leave_id))
        con.commit()
    e = get_employee(int(lv["employee_id"])) or {}
    notify_admins("leave_cancel",
                  f"ХҮСЭЛТ ЦУЦЛАГДЛАА — {e.get('code','')} {e.get('full_name','')}",
                  f"{lv['start_date']} өдрийн чөлөөний хүсэлтээ цуцаллаа (шийдвэр шаардлагагүй).",
                  meta={"leave_id": leave_id, "employee_id": lv["employee_id"]},
                  dedupe=f"leave_cancel_{leave_id}")
    audit("employee", "leave_cancel", f"id={leave_id} emp={lv['employee_id']}")
    return {"ok": True, "leave": get_leave(leave_id), "message": "Хүсэлт цуцлагдлаа."}


def list_leaves(month: str | None = None, employee_id: int | None = None,
                status: str | None = None) -> list[dict]:
    """Чөлөөний жагсаалт (бүх статус). status='approved' гэвэл зөвхөн батлагдсаныг."""
    q = ("SELECT l.*, e.full_name, e.code, e.position FROM leaves l "
         "JOIN employees e ON e.id=l.employee_id WHERE 1=1")
    args: list = []
    if month:
        q += " AND (l.start_date LIKE ? OR COALESCE(l.end_date,l.start_date) LIKE ?)"
        args += [f"{month}-%", f"{month}-%"]
    if employee_id:
        q += " AND l.employee_id=?"
        args.append(employee_id)
    if status and status != "all":
        q += " AND l.status=?"
        args.append(status)
    q += " ORDER BY CASE l.status WHEN 'pending' THEN 0 ELSE 1 END, l.start_date DESC, l.id DESC"
    with connect() as con:
        rows = [dict(r) for r in con.execute(q, args).fetchall()]
    for r in rows:                     # өнгөний код + статус (UI-д шууд хэрэглэнэ)
        r["color"] = LEAVE_COLORS.get(r.get("kind"), "blue")
        r["status"] = r.get("status") or ("approved" if int(r.get("approved") or 0) else "rejected")
        r["status_label"] = LEAVE_STATUS_LABEL.get(r["status"], r["status"])
        r["status_color"] = LEAVE_STATUS_COLOR.get(r["status"], "gray")
        r["paid"] = int(r.get("paid") or 0)
    return rows


def delete_leave(leave_id: int) -> dict:
    with _lock, connect() as con:
        r = con.execute("SELECT * FROM leaves WHERE id=?", (leave_id,)).fetchone()
        con.execute("DELETE FROM leaves WHERE id=?", (leave_id,))
        con.commit()
    if r:
        recalc_all(month=str(r["start_date"])[:7])
        audit("admin", "leave_delete", f"id={leave_id} emp={r['employee_id']} {r['kind']}")
    return {"ok": True, "message": "Чөлөө устгагдлаа."}


def leave_summary(employee_id: int, month: str) -> dict:
    """Сарын чөлөөний хураангуй (нэг төрөл) + хүлээгдэж буй/батлагдсан/татгалзсан."""
    out = {k: {"days": 0, "hours": 0.0, "paid": False} for k in LEAVE_KINDS}
    for k in list(LEAVE_KINDS):
        out[k]["status"] = {}
    paid_hours = 0.0
    for lv in list_leaves(month, employee_id, status="approved"):
        kind = lv["kind"] if lv["kind"] in out else "чөлөө"
        is_paid = int(lv.get("paid") or 0) == 1
        if int(lv["all_day"] or 0) == 1:
            dd = date.fromisoformat(lv["start_date"])
            ed = date.fromisoformat(lv["end_date"] or lv["start_date"])
            days = 0
            while dd <= ed:
                if is_workday(dd) and dd.isoformat().startswith(month):
                    days += 1
                dd += timedelta(days=1)
            hrs = days * (paid_minutes_per_day(month + "-01") / 60.0)
            out[kind]["days"] += days
            out[kind]["hours"] += hrs
        else:
            hrs = float(lv["hours"] or 0)
            out[kind]["hours"] += hrs
        if is_paid:                     # v3.1: чөлөө бүр paid=0/1 (админ шийднэ)
            paid_hours += hrs
            out[kind]["paid"] = True
    for k, v in out.items():
        v["hours"] = round(v["hours"], 2)
        v["paid_hours"] = round(paid_hours, 2) if k == "чөлөө" else 0.0
    for lv in list_leaves(month, employee_id):
        k = lv["kind"] if lv["kind"] in out else "чөлөө"
        st = out[k].setdefault("status", {})
        st[lv["status"]] = st.get(lv["status"], 0) + 1
    return out


# --------------------------------------------------------------------------
# Тасалсан (зөвшөөрөлгүй) хоног ба 10% торгууль
# --------------------------------------------------------------------------
def month_workdays(month: str, upto_today: bool = True) -> list[str]:
    y, m = int(month[:4]), int(month[5:7])
    first = date(y, m, 1)
    nxt = date(y + (m == 12), (m % 12) + 1, 1)
    last = nxt - timedelta(days=1)
    if upto_today:
        today = date.fromisoformat(today_str())
        if last > today:
            last = today
    days, d = [], first
    while d <= last:
        if is_workday(d):
            days.append(d.isoformat())
        d += timedelta(days=1)
    return days


def absent_days(employee_id: int, month: str) -> list[str]:
    """
    «Ирээгүй» (absent) ажлын өдрүүд.
    Дүрэм: бүртгэл огт хийгээгүй, эсвэл ажил дуусах цаг хүртэл бүртгэлээ хаагаагүй /
    зөвшөөрөлгүй эрт явсан өдөр. БАТЛАГДСАН чөлөө нь тасалдлыг нөхнө.
    """
    with connect() as con:
        rows = {r["work_date"]: dict(r) for r in con.execute(
            "SELECT * FROM attendance WHERE employee_id=? AND work_date LIKE ?",
            (employee_id, f"{month}-%")).fetchall()}
    covered: set[str] = set()
    for lv in list_leaves(month, employee_id, status="approved"):
        if int(lv["all_day"] or 0) != 1:
            continue
        dd = date.fromisoformat(lv["start_date"])
        ed = date.fromisoformat(lv["end_date"] or lv["start_date"])
        while dd <= ed:
            covered.add(dd.isoformat())
            dd += timedelta(days=1)
    today = today_str()
    out = []
    for d in month_workdays(month):
        if d in covered:
            continue
        r = rows.get(d)
        if not r:
            if d <= today:                 # бүртгэл огт байхгүй
                out.append(d)
            continue
        st = r.get("day_status") or ""
        if st == "absent":
            out.append(d)
        elif st == "" and not r.get("clock_in") and d <= today:
            out.append(d)
    # Ажлын хуваарьт ороогүй ч бүртгэл үүссэн өдөр (ж: ажилласан амралтын өдөр)
    # хагас дутуу бол мөн «ирээгүй» өдөрт тооцогдоно.
    sched = set(month_workdays(month))
    for d, r in rows.items():
        if d in sched or d in covered or d > today:
            continue
        if (r.get("day_status") or "") == "absent" and int(r.get("is_workday") or 0) == 1:
            out.append(d)
    return sorted(set(out))


def max_absent_streak(days: list[str], month: str) -> tuple[int, list[str]]:
    """Дараалан тасарсан ажлын өдрүүдийн дээд урт."""
    if not days:
        return 0, []
    workdays = month_workdays(month)
    index = {d: i for i, d in enumerate(workdays)}
    idxs = sorted(index[d] for d in days if d in index)
    best, best_run, run, prev = 0, [], [], None
    for i in idxs:
        if prev is not None and i == prev + 1:
            run.append(workdays[i])
        else:
            run = [workdays[i]]
        if len(run) > best:
            best, best_run = len(run), list(run)
        prev = i
    return best, best_run


# --------------------------------------------------------------------------
# Ажилтнууд
# --------------------------------------------------------------------------
def set_employee_geofence(eid: int, mode: str, lat=None, lng=None,
                          radius_m=None) -> tuple[dict | None, dict | None]:
    """
    Ажилтан бүрийн гео хаалтыг тохируулна (v4.3).
      * mode='site'   — оноосон талбай / үндсэн гео хаалт (радиус нь талбайгаас);
      * mode='custom' — өөрийн байршил (lat/lng) + радиус (анхдагч 300 м);
      * mode='off'    — гео хаалт ХҮЧИНГҮЙ (жолооч, хээрийн ажилтан).
    """
    emp = get_employee(eid)
    if not emp:
        return None, None
    mode = (mode or "site").strip().lower()
    if mode not in GEOFENCE_MODES:
        raise ValueError("Гео хаалтын горим буруу: site | custom | off")
    note = ""
    if mode == "custom":
        try:
            lat = float(lat); lng = float(lng)
        except (TypeError, ValueError):
            raise ValueError("Өөрийн горимд өргөрөг, уртраг шаардлагатай.")
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            raise ValueError("Координат хүрээнээс гарсан байна.")
        radius = float(radius_m or 300)
        if not (20 <= radius <= 20000):
            raise ValueError("Радиус 20–20 000 м хооронд байх ёстой.")
        update_employee(eid, {"geofence_mode": "custom", "geo_lat": lat,
                              "geo_lng": lng, "geo_radius_m": radius})
        note = f" ({lat:.5f}, {lng:.5f}, {radius:.0f} м)"
    else:
        update_employee(eid, {"geofence_mode": mode})       # update_employee хоосон утгыг алгасдаг
        with _lock, connect() as con:
            con.execute("UPDATE employees SET geo_lat=NULL, geo_lng=NULL, geo_radius_m=NULL"
                        " WHERE id=?", (eid,))
            con.commit()
    emp = get_employee(eid)
    audit("admin", "employee_geofence",
          f"{emp['code']} {emp['full_name']}: {GEOFENCE_MODE_LABEL[mode]}{note}")
    return emp, effective_geo(emp)


def employee_public(row) -> dict:
    keys = row.keys() if hasattr(row, "keys") else []
    out = {
        "id": row["id"], "code": row["code"], "full_name": row["full_name"],
        "department": row["department"] or "", "position": row["position"] or "",
        "active": int(row["active"]),
    }
    if "daily_rate" in keys:
        out["daily_rate"] = float(row["daily_rate"] or 0)
    if "night_role" in keys:
        out["night_role"] = row["night_role"] or "worker"
    if "site_id" in keys:
        out["site_id"] = row["site_id"]
    if "geofence_mode" in keys:
        out["geofence_mode"] = row["geofence_mode"] or "site"
        out["geofence_mode_label"] = GEOFENCE_MODE_LABEL.get(out["geofence_mode"], "")
        out["geo_lat"] = row["geo_lat"]
        out["geo_lng"] = row["geo_lng"]
        out["geo_radius_m"] = float(row["geo_radius_m"]) if row["geo_radius_m"] is not None else None
    return out


def list_employees(active_only: bool = False) -> list[dict]:
    q = "SELECT * FROM employees"
    if active_only:
        q += " WHERE active=1"
    q += " ORDER BY code"
    with connect() as con:
        return [employee_public(r) for r in con.execute(q).fetchall()]


def get_employee(employee_id: int) -> dict | None:
    with connect() as con:
        r = con.execute("SELECT * FROM employees WHERE id=?", (employee_id,)).fetchone()
    return employee_public(r) if r else None


def get_employee_by_code(code: str) -> dict | None:
    with connect() as con:
        r = con.execute("SELECT * FROM employees WHERE code=? COLLATE NOCASE", (code.strip(),)).fetchone()
    return employee_public(r) if r else None


def create_employee(code, full_name, department, position, pin, daily_rate=None,
                    night_role="worker", site_id=None) -> dict:
    now = now_local().strftime("%Y-%m-%d %H:%M:%S")
    rate = float(daily_rate) if daily_rate not in (None, "") else float(
        get_settings()["default_daily_rate"] or 0)
    with _lock, connect() as con:
        cur = con.execute(
            "INSERT INTO employees(code, full_name, department, position, pin, active, "
            "daily_rate, night_role, site_id, created_at) VALUES(?,?,?,?,?,1,?,?,?,?)",
            (code.strip().upper(), full_name.strip(), department.strip(), position.strip(),
             str(pin), rate, night_role or "worker", site_id, now))
        con.commit()
        eid = cur.lastrowid
    audit("admin", "employee_create", f"{code} {full_name} цалин={rate}")
    return get_employee(eid)


def update_employee(eid: int, fields: dict) -> dict | None:
    allowed = {"code", "full_name", "department", "position", "pin", "active",
               "daily_rate", "night_role", "site_id",
               "geofence_mode", "geo_lat", "geo_lng", "geo_radius_m"}
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed and v is not None and v != "":
            sets.append(f"{k}=?")
            if k in ("active", "site_id"):
                vals.append(int(v))
            elif k == "daily_rate":
                vals.append(float(v))
            elif k in ("geo_lat", "geo_lng", "geo_radius_m"):
                vals.append(float(v))
            elif k == "geofence_mode":
                vals.append(str(v).strip() if str(v).strip() in GEOFENCE_MODES else "site")
            else:
                vals.append(str(v).strip())
    if not sets:
        return get_employee(eid)
    vals.append(eid)
    with _lock, connect() as con:
        con.execute(f"UPDATE employees SET {', '.join(sets)} WHERE id=?", vals)
        con.commit()
    if {"daily_rate", "night_role"} & set(fields.keys()):
        recalc_all()          # цалин/ээлж өөрчлөгдвөл бүх бүртгэлийг дахин тооцоолно
    audit("admin", "employee_update", f"id={eid} {fields}")
    return get_employee(eid)


def verify_pin(code: str, pin: str) -> dict | None:
    with connect() as con:
        r = con.execute("SELECT * FROM employees WHERE code=? COLLATE NOCASE AND active=1",
                        (code.strip(),)).fetchone()
    if r and hmac.compare_digest(str(r["pin"]), str(pin).strip()):
        return employee_public(r)
    return None


# --------------------------------------------------------------------------
# Ирцийн бүртгэл (attendance records)
# --------------------------------------------------------------------------
def get_record(employee_id: int, day: str) -> dict | None:
    with connect() as con:
        r = con.execute("SELECT * FROM attendance WHERE employee_id=? AND work_date=?",
                        (employee_id, day)).fetchone()
    return dict(r) if r else None


def _save_record(rec: dict, con) -> None:
    cols = ["employee_id", "work_date", "clock_in", "in_lat", "in_lng", "in_distance_m",
            "in_accuracy_m", "clock_out", "out_lat", "out_lng", "out_distance_m",
            "out_accuracy_m", "late_minutes", "early_minutes", "worked_minutes",
            "break_minutes", "deduct_minutes", "payable_minutes", "is_workday",
            "shift_type", "night_role", "site_id", "day_rate_snapshot", "day_credit",
            "pay_multiplier", "excused_minutes", "extra_minutes",
            "extra_admin_minutes", "extra_segment_minutes",
            "in_photo", "out_photo", "in_photo_ts", "out_photo_ts", "photo_source",
            "pay_base", "pay_extra", "pay_amount",
            "day_status", "absent_minutes", "leave_minutes",
            "status", "note", "edited", "updated_at"]
    now = now_local().strftime("%Y-%m-%d %H:%M:%S")
    if rec.get("id"):
        rec["updated_at"] = now
        sets = ", ".join(f"{c}=?" for c in cols)
        con.execute(f"UPDATE attendance SET {sets} WHERE id=?", [rec.get(c) for c in cols] + [rec["id"]])
    else:
        rec["created_at"] = rec.get("created_at") or now
        rec["updated_at"] = now
        c2 = cols + ["created_at"]
        ph = ", ".join("?" for _ in c2)
        cur = con.execute(f"INSERT INTO attendance({', '.join(c2)}) VALUES({ph})",
                          [rec.get(c) for c in c2])
        rec["id"] = cur.lastrowid


def recalc_all(month: str | None = None) -> int:
    """
    Одоогийн тохиргоогоор бүх бүртгэлийг дахин тооцоолно.
    (Ажлын цаг, хөнгөлөлт, үдийн завсарлага өөрчлөгдөхөд дуудна.)
    """
    with _lock, connect() as con:
        q = "SELECT * FROM attendance"
        args = ()
        if month:
            q += " WHERE work_date LIKE ?"
            args = (f"{month}-%",)
        rows = [dict(r) for r in con.execute(q, args).fetchall()]
        n = 0
        emps = {e["id"]: e for e in list_employees()}
        for r in rows:
            keep = bool(int(r.get("is_workday") or 0))
            rec = recalc(r, r["work_date"], force_workday=keep,
                         employee=emps.get(r["employee_id"]))
            _save_record(rec, con)
            n += 1
        con.commit()
    return n


def clock_in(employee_id: int, lat=None, lng=None, accuracy=None,
             note: str = "", force: bool = False, demo: bool = False,
             photo=None, photo_source: str = "camera") -> dict:
    s = get_settings()
    day = today_str()
    now = now_local()
    emp = get_employee(employee_id)
    emp_code = (emp or {}).get("code", employee_id)
    if str(s.get("require_photo") or "1") == "1" and not photo and not force:
        return {"ok": False, "error": "Ажил эхлэхийн тулд ЗУРАГ авах шаардлагатай.",
                "need_photo": True}
    shot = {"ok": True, "path": None}
    if photo:
        shot = save_photo(photo, employee_id, day, "in", photo_source)
        if not shot.get("ok"):
            return shot
    _eg = effective_geo(emp)                              # v4.3: ажилтны гео горим/радиус
    geo = {"ok": True, "enabled": _eg["enabled"] and s["geofence_enabled"] == "1",
           "distance_m": None, "radius_m": _eg["radius_m"], "mode": _eg.get("mode", "site"),
           "source": _eg.get("source", "site"), "site": _eg.get("name", ""), "message": ""}
    if not force:
        geo = check_geofence(lat, lng, demo, emp)
        if not geo["ok"]:
            audit(f"employee:{employee_id}", "clock_in_blocked", geo["message"])
            return {"ok": False, "error": geo["message"], "geofence": geo}

    with _lock, connect() as con:
        existing = con.execute("SELECT * FROM attendance WHERE employee_id=? AND work_date=?",
                               (employee_id, day)).fetchone()
        if existing and existing["clock_in"]:
            return {"ok": False, "error": "Та өнөөдөр ажилд орох бүртгэлээ хийсэн байна.",
                    "record": apply_flags(dict(existing))}
        rec = recalc({
            "id": existing["id"] if existing else None,
            "employee_id": employee_id, "work_date": day,
            "in_photo": shot.get("path"),
            "in_photo_ts": shot.get("ts") if photo else None,
            "photo_source": photo_source if photo else None,
            "clock_in": now.strftime("%Y-%m-%d %H:%M:%S"),
            "in_lat": lat, "in_lng": lng, "in_distance_m": geo.get("distance_m"),
            "in_accuracy_m": accuracy,
            "site_id": geo.get("site_id"),
            "shift_type": detect_shift(now, day),
            "clock_out": None, "out_lat": None, "out_lng": None,
            "out_distance_m": None, "out_accuracy_m": None,
            "note": note or (existing["note"] if existing else ""),
            "edited": 0,
        }, day, employee=emp)
        _save_record(rec, con)
        con.commit()
    audit(f"employee:{employee_id}", "clock_in",
          f"{day} {rec['clock_in']} dist={geo.get('distance_m')} фото={'тийм' if photo else 'үгүй'}"
          + (" [ДЕМО ГОРИМ]" if geo.get("demo") else ""))
    if photo:
        notify(employee_id, "info", "Ажил эхлэх бүртгэл хийгдлээ",
               f"{now.strftime('%H:%M')} — зураг хадгалагдсан. Ажлын өдөр 09:00–19:00.",
               dedupe=f"in:{day}:{employee_id}:{now.strftime('%H%M%S')}")
    return {"ok": True, "record": apply_flags(rec), "geofence": geo, "photo": shot.get("path")}


def clock_out(employee_id: int, lat=None, lng=None, accuracy=None,
              note: str = "", force: bool = False, demo: bool = False,
              photo=None, photo_source: str = "camera") -> dict:
    s = get_settings()
    day = today_str()
    now = now_local()
    emp = get_employee(employee_id)
    if str(s.get("require_photo") or "1") == "1" and not photo and not force:
        return {"ok": False, "error": "Ажил дуусгахын тулд ЗУРАГ авах шаардлагатай.",
                "need_photo": True}
    shot = {"ok": True, "path": None}
    if photo:
        shot = save_photo(photo, employee_id, day, "out", photo_source)
        if not shot.get("ok"):
            return shot
    _eg = effective_geo(emp)                              # v4.3: ажилтны гео горим/радиус
    geo = {"ok": True, "enabled": _eg["enabled"] and s["geofence_enabled"] == "1",
           "distance_m": None, "radius_m": _eg["radius_m"], "mode": _eg.get("mode", "site"),
           "source": _eg.get("source", "site"), "site": _eg.get("name", ""), "message": ""}
    if not force:
        geo = check_geofence(lat, lng, demo, emp)          # v4.3: ажилтны горим/радиус
        if not geo["ok"]:
            audit(f"employee:{employee_id}", "clock_out_blocked", geo["message"])
            return {"ok": False, "error": geo["message"], "geofence": geo}

    with _lock, connect() as con:
        existing = con.execute("SELECT * FROM attendance WHERE employee_id=? AND work_date=?",
                               (employee_id, day)).fetchone()
        out_day = day
        if (not existing or not existing["clock_in"]):
            # Шөнийн ээлж: 19:00-нд эхэлсэн, дараа өдөр 03:00-д дуусна
            yday = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
            prev = con.execute("SELECT * FROM attendance WHERE employee_id=? AND work_date=?",
                               (employee_id, yday)).fetchone()
            if prev and prev["clock_in"] and not prev["clock_out"] and \
                    (prev["shift_type"] or detect_shift(parse_dt(prev["clock_in"]), yday)) == "night":
                existing, out_day = prev, yday
        if not existing or not existing["clock_in"]:
            return {"ok": False, "error": "Эхлээд ажилд орох бүртгэлээ хийнэ үү."}
        if existing["clock_out"]:
            return {"ok": False, "error": "Та өнөөдөр ажлаас буух бүртгэлээ хийсэн байна.",
                    "record": apply_flags(dict(existing))}
        rec = dict(existing)
        force_wd = bool(int(existing["is_workday"] or 0))
        rec.update({
            "clock_out": now.strftime("%Y-%m-%d %H:%M:%S"),
            "out_lat": lat, "out_lng": lng, "out_distance_m": geo.get("distance_m"),
            "out_accuracy_m": accuracy,
            "out_photo": shot.get("path"),
            "out_photo_ts": shot.get("ts") if photo else None,
        })
        if note:
            rec["note"] = note
        rec = recalc(rec, out_day, force_workday=force_wd, employee=emp)
        _save_record(rec, con)
        con.commit()
    audit(f"employee:{employee_id}", "clock_out",
          f"{rec['work_date']} {rec['clock_out']} dist={geo.get('distance_m')}"
          f" фото={'тийм' if photo else 'үгүй'}"
          + (" [ШӨНИЙН ЭЭЛЖ]" if (rec.get("shift_type") == "night") else "")
          + (" [ДЕМО ГОРИМ]" if geo.get("demo") else ""))
    if photo:
        notify(employee_id, "info", "Ажил дуусах бүртгэл хийгдлээ",
               f"{now.strftime('%H:%M')} — ажилласан "
               f"{fmt_hhmm(rec.get('worked_minutes'))}, хөдөлмөрийн өдөр "
               f"{float(rec.get('day_credit') or 0):.2f}. Зураг хадгалагдсан.",
               dedupe=f"out:{day}:{employee_id}:{now.strftime('%H%M%S')}")
    return {"ok": True, "record": apply_flags(rec), "geofence": geo, "photo": shot.get("path")}


def apply_flags(rec: dict | None) -> dict | None:
    """Дэлгэцэд харагдах нэмэлт талбарууд (флаг + монгол шошго)."""
    if not rec:
        return None
    out = dict(rec)
    late = int(rec.get("late_minutes") or 0)
    early = int(rec.get("early_minutes") or 0)
    out["is_late"] = late > 0                      # УЛААНААР тэмдэглэнэ
    out["is_early_leave"] = early > 0
    out["late_label"] = f"Хоцорсон +{late} мин" if late > 0 else ""
    out["early_label"] = f"Эрт явсан −{early} мин" if early > 0 else ""
    out["clock_in_hm"] = fmt_time(rec.get("clock_in"))
    out["clock_out_hm"] = fmt_time(rec.get("clock_out"))
    out["worked_hm"] = fmt_hm(rec.get("worked_minutes"))
    out["payable_hm"] = fmt_hm(rec.get("payable_minutes"))
    out["deduct_hm"] = fmt_hm(rec.get("deduct_minutes"))
    return out


def employee_day_view(employee_id: int, day: str | None = None) -> dict:
    """Ажилтны тухайн өдрийн самбарын өгөгдөл."""
    day = day or today_str()
    s = get_settings()
    rec = get_record(employee_id, day)
    start, end = schedule_window(day)
    workday = is_workday(day)
    if not workday:
        # Ажлын бус өдөр ч тухайн өдөрт ажлын өдрөөр тэмдэглэгдсэн бүртгэл байвал
        # (ж: демо өгөгдөл) самбартай ижил үзэл баримтлал баримтална
        with connect() as con:
            forced = con.execute(
                "SELECT 1 FROM attendance WHERE work_date=? AND is_workday=1 LIMIT 1",
                (day,)).fetchone()
        if forced:
            workday = True
    status, status_code = "not_checked_in", "not_checked_in"
    if rec and rec.get("clock_in") and not rec.get("clock_out"):
        status_code, status = "working", STATUS_MN["working"]
    elif rec and rec.get("clock_out"):
        status_code, status = "done", STATUS_MN["done"]
    emp = get_employee(employee_id) or {}
    geo = effective_geo(emp)
    today_leave = [lv for lv in list_leaves(day[:7], employee_id, status="approved")
                   if lv["start_date"] <= day <= (lv["end_date"] or lv["start_date"])]
    today_pending = [lv for lv in list_leaves(day[:7], employee_id, status="pending")
                     if lv["start_date"] <= day <= (lv["end_date"] or lv["start_date"])]
    dstat = ((rec or {}).get("day_status") or "")
    if not dstat:                                            # v4.3: самбартай ижил логик
        if not workday:
            dstat = "off"
        elif (rec or {}).get("clock_in"):
            dstat = "working" if not rec.get("clock_out") else "normal"
        elif today_leave:
            dstat = "leave"                                  # батлагдсан чөлөө
        elif now_local() < start + timedelta(
                minutes=int(float(s.get("absent_minutes_grace") or 10))):
            dstat = "pending"                                # ажлын цаг хараахан эхлээгүй
        else:
            dstat = "absent"
    return {
        "date": day,
        "weekday_mn": WEEKDAY_MN[date.fromisoformat(day).isoweekday()],
        "is_workday": workday,
        "schedule": {"start": s["schedule_start"], "end": s["schedule_end"],
                     "grace_minutes": int(float(s["grace_minutes"] or 0)),
                     "night_start": s["night_start"], "night_end": s["night_end"]},
        "status": status,
        "status_code": status_code,
        "status_label": STATUS_MN.get(status_code, status),
        "record": apply_flags(rec),
        "server_time": now_local().strftime("%Y-%m-%d %H:%M:%S"),
        # ---- Барилгын бригадын нэмэлт ----
        "geo": geo,                                   # өөрийн ажлын байрны хүрээ
        "site": employee_site(emp),
        "daily_rate": float(emp.get("daily_rate") or 0),
        "night_role": emp.get("night_role") or "worker",
        "shift_today": (rec or {}).get("shift_type") or "day",
        "today_leave": today_leave,
        "on_leave": bool(today_leave),
        "today_pending_leave": today_pending,
        "day_status": dstat,
        "day_status_label": DAY_STATUS_LABEL.get(dstat, dstat),
        "day_status_color": DAY_STATUS_COLOR.get(dstat, "gray"),
        "absent_minutes": int((rec or {}).get("absent_minutes") or 0) if rec else (
            paid_minutes_per_day(day) if dstat == "absent" else 0),   # бүртгэлгүй = бүтэн ээлж
        "leave_minutes": int((rec or {}).get("leave_minutes") or 0) or (
            paid_minutes_per_day(day) if dstat == "leave" and not rec else 0),
        "leave_label": (f"{today_leave[0]['kind']} "
                        + ("бүтэн өдөр" if int(today_leave[0]["all_day"]) else
                           f"{today_leave[0]['start_time']}–{today_leave[0]['end_time']}"))
        if today_leave else "",
        "pay_today": round(float((rec or {}).get("pay_amount") or 0), 2),
        # ---- v3: фото ба нэмэлт ажил ----
        "photo_required": str(get_settings().get("require_photo") or "1") == "1",
        "in_photo": (rec or {}).get("in_photo"),
        "out_photo": (rec or {}).get("out_photo"),
        "extra_open": open_segment(employee_id),
        "extra_minutes": segment_minutes(employee_id, (day or today_str())[:7]),
    }


def employee_history(employee_id: int, month: str) -> dict:
    with connect() as con:
        rows = con.execute(
            "SELECT * FROM attendance WHERE employee_id=? AND work_date LIKE ? ORDER BY work_date DESC",
            (employee_id, f"{month}-%")).fetchall()
    recs = [apply_flags(dict(r)) for r in rows]
    tot = aggregate(recs)
    return {"month": month, "records": recs, "summary": tot}


def aggregate(records: list[dict]) -> dict:
    present = [r for r in records if r.get("clock_in")]
    return {
        "present_days": len(present),
        "worked_minutes": sum(int(r.get("worked_minutes") or 0) for r in present),
        "payable_minutes": sum(int(r.get("payable_minutes") or 0) for r in present),
        "late_days": sum(1 for r in present if int(r.get("late_minutes") or 0) > 0),
        "late_minutes": sum(int(r.get("late_minutes") or 0) for r in present),
        "early_days": sum(1 for r in present if int(r.get("early_minutes") or 0) > 0),
        "early_minutes": sum(int(r.get("early_minutes") or 0) for r in present),
        "deduct_minutes": sum(int(r.get("deduct_minutes") or 0) for r in present),
    }


# --------------------------------------------------------------------------
# Удирдлагын самбар (manager live board)
# --------------------------------------------------------------------------
def last_workday_on_or_before(d: date) -> date:
    while not is_workday(d):
        d -= timedelta(days=1)
    return d


def demo_seed_today(force_workday: bool = True) -> dict:
    """
    ТУРШИЛТЫН (демо) өдрийн бүртгэл — самбарын бүх төлөв харагдахын тулд.
    Зөвхөн «Демо өгөгдөл» тэмдэглэлтэй бичлэгүүдийг устгаж, дахин үүсгэнэ.
    """
    day = today_str()
    now = now_local()
    rng = random.Random(int(day.replace("-", "")))
    s = get_settings()
    start_t = parse_hhmm(s["schedule_start"])
    end_t = parse_hhmm(s["schedule_end"])
    sched_start = datetime.combine(date.fromisoformat(day), start_t)
    sched_end = datetime.combine(date.fromisoformat(day), end_t)

    with _lock, connect() as con:
        emps = [r["id"] for r in con.execute(
            "SELECT id FROM employees WHERE active=1 ORDER BY code").fetchall()]
        # зөвхөн демо бичлэгүүдийг цэвэрлэнэ
        con.execute("DELETE FROM attendance WHERE work_date=? AND note LIKE '%Демо өгөгдөл%'", (day,))

    if now < sched_start:                       # ажил эхлээгүй бол эхлэх цагийг хүлээнэ
        return {"ok": False, "created": 0,
                "message": f"Ажлын цаг эхлээгүй байна ({s['schedule_start']}). Дараа оролдоно уу."}

    # Төлөвүүдийн загвар: (ирсэн минутын зөрүү, явсан?, төлөв)
    plan = [
        (-9, "working"), (-6, "working"), (-4, "done"), (-2, "done"),
        (18, "working"), (34, "working"), (52, "done"),
        (-11, "done_early"), (-7, "done_early"), (12, "done_late_early"),
        (-1, "working"), (0, "absence"),
    ]
    created = 0
    with _lock, connect() as con:
        for i, eid in enumerate(emps):
            in_off, kind = plan[i % len(plan)]
            if kind == "absence":
                continue
            cin = sched_start + timedelta(minutes=in_off, seconds=rng.randint(0, 59))
            if cin > now:
                continue
            cout = None
            # v3.1: ажлын цаг дууссаны дараа «ажиллаж байгаа» бичлэг үлдээхгүй —
            # нэг ажилтан мэдэгдэлгүй явсан (гарах бүртгэлгүй) хэвээр үлдэнэ.
            if kind == "working" and now >= sched_end + timedelta(minutes=10):
                cout = None if i == 4 else sched_end + timedelta(minutes=rng.randint(0, 9))
            if kind.startswith("done"):
                base = sched_end if now >= sched_end else now
                if kind == "done_early":
                    cout = min(base, sched_end) - timedelta(minutes=rng.randint(35, 95))
                elif kind == "done_late_early":
                    cout = sched_end - timedelta(minutes=rng.randint(25, 70))
                else:
                    cout = base + timedelta(minutes=rng.choice([-6, -2, 0, 3, 9]))
                    if cout > now:
                        cout = now
                if cout <= cin:
                    cout = None
            note = "Демо өгөгдөл (туршилт)"
            if kind == "working" and not cout and now >= sched_end + timedelta(minutes=10):
                note = "Демо өгөгдөл (туршилт) — гарах бүртгэл хийгээгүй, мэдэгдэлгүй явсан"
            rec = recalc({
                "id": None, "employee_id": eid, "work_date": day,
                "clock_in": cin.strftime("%Y-%m-%d %H:%M:%S"),
                "clock_out": cout.strftime("%Y-%m-%d %H:%M:%S") if cout else None,
                "in_lat": 47.9184, "in_lng": 106.9177,
                "in_distance_m": round(rng.uniform(4, 210), 1), "in_accuracy_m": 9.0,
                "out_lat": 47.9184 if cout else None, "out_lng": 106.9177 if cout else None,
                "out_distance_m": round(rng.uniform(4, 210), 1) if cout else None,
                "out_accuracy_m": 9.0 if cout else None,
                "note": note, "edited": 0,
            }, day, force_workday=force_workday)
            _save_record(rec, con)
            created += 1
        con.commit()
    # v3.1: «Чөлөө» төлөв самбар дээр харагдахын тулд нэг ажилтанд батлагдсан чөлөө олгоно
    try:
        with connect() as con:
            last = con.execute("SELECT id FROM employees WHERE active=1 ORDER BY code DESC "
                               "LIMIT 1").fetchone()
            has_leave = con.execute("SELECT 1 FROM leaves WHERE employee_id=? AND start_date<=? "
                                    "AND COALESCE(end_date,start_date)>=? AND status='approved'",
                                    (last["id"], day, day)).fetchone() if last else None
        if last and not has_leave:
            add_leave(int(last["id"]), "чөлөө", day, day, True,
                      note="Демо: батлагдсан чөлөө (хүсэлтээр)", created_by="admin",
                      status="approved", paid=0)
    except Exception:
        pass
    audit("admin", "demo_seed", f"{day} — {created} туршилтын бүртгэл")
    return {"ok": True, "created": created,
            "message": f"{created} ажилтны туршилтын бүртгэл үүсгэгдлээ. (Демо өгөгдөл)"}


def demo_clear_today() -> dict:
    day = today_str()
    with _lock, connect() as con:
        cur = con.execute("DELETE FROM attendance WHERE work_date=? AND note LIKE '%Демо өгөгдөл%'",
                          (day,))
        con.commit()
    audit("admin", "demo_clear", f"{day} — {cur.rowcount} бичлэг устгав")
    return {"ok": True, "deleted": cur.rowcount,
            "message": f"{cur.rowcount} туршилтын бичлэг устгагдлаа."}


def live_board(day: str | None = None) -> dict:
    day = day or today_str()
    now = now_local()
    settings = get_settings()
    start, end = schedule_window(day)
    grace = timedelta(minutes=int(float(settings["grace_minutes"] or 0)))
    workday = is_workday(day)
    is_today = (day == today_str())

    with connect() as con:
        emps = con.execute("SELECT * FROM employees WHERE active=1 ORDER BY code").fetchall()
        recs = {r["employee_id"]: dict(r) for r in con.execute(
            "SELECT * FROM attendance WHERE work_date=?", (day,)).fetchall()}

    # Демо бичлэг байгаа бол уг өдрийг ажлын өдөр гэж үзнэ
    if any(int(r.get("is_workday") or 0) == 1 for r in recs.values()):
        workday = True

    # v4: тухайн өдөр БАТЛАГДСАН чөлөө (бүртгэл байхгүй ажилтныг «Чөлөө» болгоно)
    #     болон хүлээгдэж буй хүсэлт (тасалдлыг НӨХӨХГҮЙ — зөвхөн сануулга)
    day_leaves: dict[int, dict] = {}
    day_pending: dict[int, dict] = {}
    for lv in list_leaves(day[:7]):
        if not (lv["start_date"] <= day <= (lv["end_date"] or lv["start_date"])):
            continue
        if lv.get("status") == "approved":
            day_leaves[lv["employee_id"]] = lv
        elif lv.get("status") == "pending":
            day_pending[lv["employee_id"]] = lv

    rows, summary = [], {"total": len(emps), "working": 0, "late": 0, "absent": 0,
                         "done": 0, "early": 0, "on_time": 0, "leave": 0}
    for e in emps:
        emp = employee_public(e)
        rec = recs.get(e["id"])
        r = apply_flags(rec) if rec else None
        late = int(rec["late_minutes"]) if rec else 0
        early = int(rec["early_minutes"]) if rec else 0
        status_code, label, color = "pending", "Хүлээгдэж байна", "gray"
        # v3.1: зөвхөн гурван үндсэн төлөв — чөлөө / ирээгүй / хэвийн (ажиллаж байна)
        dstat = (rec or {}).get("day_status") or ""
        leave_min = int((rec or {}).get("leave_minutes") or 0)
        absent_min = int((rec or {}).get("absent_minutes") or 0)
        if not rec:
            # бүртгэлгүй өдөр: чөлөө / ирээгүй / хэвийн-г чөлөө ба хуваариар тодорхойлно
            lv_day = day_leaves.get(e["id"])
            if lv_day:
                pday = paid_minutes_per_day(day)
                leave_min = (pday if int(lv_day["all_day"])
                             else min(pday, leave_minutes_for_window(e["id"], day)))
                left = max(0, pday - leave_min)
                grace_abs = int(float(settings.get("absent_minutes_grace") or 10))
                if left <= grace_abs:
                    dstat, absent_min = "leave", 0
                elif workday:
                    dstat, absent_min = "absent", left
                else:
                    dstat, absent_min = "leave", 0
            elif workday and (not is_today or now >= start + timedelta(
                    minutes=int(float(settings.get("absent_minutes_grace") or 10)))):
                # бүртгэлгүй ажлын өдөр = бүтэн ээлж тасарсан (өдрийн ээлжийн цонхоор)
                dstat, absent_min = "absent", paid_minutes_per_day(day)
            elif workday and is_today:
                # v4.3: ажлын цаг эхлээгүй байхад бүртгэлгүй бол «Хүлээгдэж байна»
                dstat = "pending"
        if dstat == "leave":
            status_code, label, color = "leave", "Чөлөө", "blue"
            summary["leave"] += 1
        elif dstat == "absent":
            status_code, label, color = "absent", "Ирээгүй", "red"
            summary["absent"] += 1
        elif not workday:
            status_code, label, color = "day_off", "Амралтын өдөр", "gray"
        elif rec and rec.get("clock_in") and not rec.get("clock_out"):
            status_code, color = ("working_late", "red") if late > 0 else ("working", "green")
            label = "Ажиллаж байна" + (f" (Хоцорсон +{late} мин)" if late > 0 else "")
        elif rec and rec.get("clock_out"):
            if early > 0 and late > 0:
                status_code, label, color = "done_both", "Хоцорсон • Эрт явсан", "red"
            elif early > 0:
                status_code, label, color = "done_early", f"Эрт явсан (−{early} мин)", "amber"
            elif late > 0:
                status_code, label, color = "done_late", f"Хоцорсон (+{late} мин)", "red"
            else:
                status_code, label, color = "done", "Ажил дууссан", "green"
        else:
            # бүртгэлгүй / ирээгүй
            if is_today and now < start:
                status_code, label, color = "pending", "Хүлээгдэж байна", "gray"
            elif is_today and now < start + grace:
                status_code, label, color = "pending", "Хүлээгдэж байна", "gray"
            elif workday:
                status_code, label, color = "absent", "Ирээгүй", "darkred"
                summary["absent"] += 1
            else:
                status_code, label, color = "day_off", "Амралтын өдөр", "gray"

        if status_code == "working":
            summary["working"] += 1; summary["on_time"] += 1
        elif status_code == "working_late":
            summary["working"] += 1; summary["late"] += 1
        elif status_code in ("done", "done_early", "done_late", "done_both"):
            summary["done"] += 1
            if late > 0:
                summary["late"] += 1
            if early > 0:
                summary["early"] += 1
            if late == 0 and early == 0:
                summary["on_time"] += 1

        if status_code in ("leave", "absent"):
            summary["on_time"] += 0

        rows.append({
            **emp,
            "status_code": status_code, "status_label": label, "color": color,
            "record_id": rec["id"] if rec else None,
            "clock_in": rec["clock_in"] if rec else None,
            "clock_out": rec["clock_out"] if rec else None,
            "clock_in_hm": fmt_time(rec["clock_in"]) if rec else "—",
            "clock_out_hm": fmt_time(rec["clock_out"]) if rec else "—",
            "late_minutes": late, "early_minutes": early,
            "worked_hm": fmt_hm(rec["worked_minutes"]) if rec and rec.get("clock_out") else (
                fmt_hm(_minutes_between(parse_dt(rec["clock_in"]), now_local())) if rec and rec.get("clock_in") else "—"),
            "payable_hm": fmt_hm(rec["payable_minutes"]) if rec and rec.get("clock_out") else "—",
            "deduct_minutes": int(rec["deduct_minutes"]) if rec else 0,
            "in_distance_m": rec["in_distance_m"] if rec else None,
            "out_distance_m": rec["out_distance_m"] if rec else None,
            "note": (rec["note"] if rec else "") or "",
            "on_site": bool(rec and rec.get("clock_in") and not rec.get("clock_out")),
            "is_late": late > 0, "is_early_leave": early > 0,
            "day_status": dstat,
            "day_status_label": DAY_STATUS_LABEL.get(dstat, dstat),
            "day_status_color": DAY_STATUS_COLOR.get(dstat, "gray"),
            "absent_minutes": absent_min, "leave_minutes": leave_min,
            "on_leave": bool(dstat == "leave"),
            "pending_leave": bool(day_pending.get(e["id"])),
        })

    demo_data = any("Демо" in (r.get("note") or "") for r in recs.values())
    # «Сүүлийн ажлын өдөр» — хамгийн сүүлд БҮРТГЭЛТЭЙ өдөр (хэрэв тухайн өдөр хоосон бол).
    lw = last_workday_on_or_before(date.fromisoformat(day))
    if not recs:
        with connect() as con:
            row = con.execute(
                "SELECT MAX(work_date) d FROM attendance WHERE work_date <= ? AND work_date >= ?",
                (day, (date.fromisoformat(day) - timedelta(days=14)).isoformat())).fetchone()
        if row and row["d"]:
            lw = date.fromisoformat(row["d"])
    return {
        "date": day,
        "weekday_mn": WEEKDAY_MN[date.fromisoformat(day).isoweekday()],
        "is_workday": workday,
        "is_today": is_today,
        "demo_data": demo_data,
        "last_workday": lw.isoformat(),
        "server_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "schedule": {"start": settings["schedule_start"], "end": settings["schedule_end"],
                     "grace_minutes": int(float(settings["grace_minutes"] or 0))},
        "employees": rows,
        "summary": summary,
    }


def daily_records(day: str) -> dict:
    """Тухайн өдрийн дэлгэрэнгүй бүртгэл + ирээгүй ажилтнууд."""
    with connect() as con:
        rows = con.execute(
            "SELECT a.*, e.code, e.full_name, e.department, e.position FROM attendance a "
            "JOIN employees e ON e.id = a.employee_id WHERE a.work_date=? ORDER BY a.clock_in",
            (day,)).fetchall()
    present = [apply_flags(dict(r)) for r in rows]
    with connect() as con:
        absent = [employee_public(r) for r in con.execute(
            "SELECT * FROM employees e WHERE e.active=1 AND NOT EXISTS "
            "(SELECT 1 FROM attendance a WHERE a.employee_id=e.id AND a.work_date=?) ORDER BY e.code",
            (day,)).fetchall()]
    wd = is_workday(day) or any(int(r["is_workday"] or 0) == 1 for r in rows)
    return {"date": day, "is_workday": wd, "records": present,
            "absent": absent if wd else [], "summary": aggregate(present)}


def manual_record(employee_id: int, day: str, clock_in_t, clock_out_t, note="") -> dict:
    """Удирдлага гараар засварлах / нэмэх (audit-тай)."""
    with _lock, connect() as con:
        existing = con.execute("SELECT * FROM attendance WHERE employee_id=? AND work_date=?",
                               (employee_id, day)).fetchone()
        rec = dict(existing) if existing else {
            "id": None, "employee_id": employee_id, "work_date": day, "note": "",
            "in_lat": None, "in_lng": None, "in_distance_m": None, "in_accuracy_m": None,
            "out_lat": None, "out_lng": None, "out_distance_m": None, "out_accuracy_m": None,
        }
        rec["clock_in"] = f"{day} {clock_in_t}:00" if clock_in_t else None
        if clock_out_t:
            out_date = date.fromisoformat(day)
            if clock_in_t and parse_hhmm(clock_out_t) <= parse_hhmm(clock_in_t):
                out_date += timedelta(days=1)      # 19:00–03:00 шөнийн ээлж
            rec["clock_out"] = f"{out_date.isoformat()} {clock_out_t}:00"
        else:
            rec["clock_out"] = None
        rec["note"] = note or rec.get("note") or ""
        rec["edited"] = 1
        if existing and existing["shift_type"]:
            rec["shift_type"] = existing["shift_type"]
        else:
            rec.pop("shift_type", None)
        rec = recalc(rec, day, employee=get_employee(employee_id))
        _save_record(rec, con)
        con.commit()
    audit("admin", "manual_record", f"emp={employee_id} {day} {clock_in_t}-{clock_out_t}")
    return apply_flags(rec)



# ==========================================================================
# Фото бүртгэл (ажил эхлэх/дуусах, нэмэлт ажил) — v3
# ==========================================================================
PHOTO_DIR = os.path.join(DATA_DIR, "photos")
_DATAURL_RE = re.compile(r"^data:image/(jpeg|jpg|png|webp);base64,([A-Za-z0-9+/=\s]+)$", re.I)


def photo_path(rel: str | None) -> str | None:
    """Харьцангуй замаас бүтэн зам."""
    if not rel:
        return None
    rel = rel.replace("\\", "/").lstrip("/")
    full = os.path.join(DATA_DIR, rel)
    root = os.path.realpath(DATA_DIR)
    if not os.path.realpath(full).startswith(root):      # замын халдлагаас хамгаалах
        return None
    return full


def photo_exists(rel: str | None) -> bool:
    fp = photo_path(rel)
    return bool(fp and os.path.isfile(fp))


def save_photo(data_url: str, employee_id: int, day: str, kind: str,
               source: str = "camera") -> dict:
    """
    Base64 data-URL зургийг data/photos/YYYY-MM/<emp>_<ts>_<kind>.jpg болгож хадгална.
    """
    s = get_settings()
    max_kb = int(float(s.get("photo_max_kb") or 1500))
    if not data_url:
        return {"ok": False, "error": "Зураг хоосон байна."}
    m = _DATAURL_RE.match(str(data_url).strip())
    if not m:
        return {"ok": False, "error": "Зургийн формат буруу (JPEG/PNG base64 шаардлагатай)."}
    ext = "jpg" if m.group(1).lower() in ("jpeg", "jpg") else m.group(1).lower()
    try:
        raw = base64.b64decode(re.sub(r"\s+", "", m.group(2)), validate=False)
    except Exception:
        return {"ok": False, "error": "Зургийг задлах боломжгүй."}
    if not raw:
        return {"ok": False, "error": "Зураг хоосон байна."}
    if len(raw) > max_kb * 1024:
        return {"ok": False, "error": f"Зураг хэт том байна (дээд {max_kb} KB)."}
    sub = os.path.join(PHOTO_DIR, day[:7])
    os.makedirs(sub, exist_ok=True)
    ts = now_local().strftime("%Y%m%d_%H%M%S")
    name = f"{employee_id:03d}_{ts}_{kind}.{ext}"
    with open(os.path.join(sub, name), "wb") as f:
        f.write(raw)
    rel = f"photos/{day[:7]}/{name}"
    return {"ok": True, "path": rel, "bytes": len(raw), "source": source,
            "sha256": hashlib.sha256(raw).hexdigest()[:16], "ts": now_str()}


def now_str() -> str:
    return now_local().strftime("%Y-%m-%d %H:%M:%S")


def photo_url(rel: str | None) -> str | None:
    return f"/api/photos?path={rel}" if rel else None


# ==========================================================================
# Нэмэлт ажлын сегмент (нэмэлт цаг / шөнийн нэмэлт) — эхлэх ба дуусах зурагтай
# ==========================================================================
def extra_start(employee_id: int, photo=None, kind: str = "extra",
                note: str = "", source: str = "camera") -> dict:
    s = get_settings()
    day, now = today_str(), now_str()
    if str(s.get("require_photo") or "1") == "1" and not photo:
        return {"ok": False, "error": "Нэмэлт ажил эхлэхийн тулд ЗУРАГ авах шаардлагатай."}
    with _lock, connect() as con:
        open_seg = con.execute(
            "SELECT * FROM work_segments WHERE employee_id=? AND status='open'", (employee_id,)).fetchone()
        if open_seg:
            return {"ok": False, "error": "Нэмэлт ажил аль хэдийн эхэлсэн байна.",
                    "segment": dict(open_seg)}
        shot = save_photo(photo, employee_id, day, "extra_in", source) if photo else {"ok": True, "path": None}
        if photo and not shot.get("ok"):
            return shot
        cur = con.execute(
            "INSERT INTO work_segments(employee_id, work_date, kind, start_ts, start_photo,"
            " status, note, created_at) VALUES(?,?,?,?,?,'open',?,?)",
            (employee_id, day, kind, now, shot.get("path"), note, now))
        con.commit()
        seg = dict(con.execute("SELECT * FROM work_segments WHERE id=?", (cur.lastrowid,)).fetchone())
    audit(f"employee:{employee_id}", "extra_start", f"{day} {now} фото={'тийм' if photo else 'үгүй'}")
    return {"ok": True, "segment": seg, "message": "Нэмэлт ажил эхэллээ (зураг хадгалагдсан)."}


def extra_stop(employee_id: int, photo=None, note: str = "", source: str = "camera") -> dict:
    s = get_settings()
    day, now = today_str(), now_str()
    if str(s.get("require_photo") or "1") == "1" and not photo:
        return {"ok": False, "error": "Нэмэлт ажил дуусгахын тулд ЗУРАГ авах шаардлагатай."}
    with _lock, connect() as con:
        seg = con.execute(
            "SELECT * FROM work_segments WHERE employee_id=? AND status='open' "
            "ORDER BY id DESC LIMIT 1", (employee_id,)).fetchone()
        if not seg:
            return {"ok": False, "error": "Эхлээгүй нэмэлт ажил байхгүй байна."}
        shot = save_photo(photo, employee_id, day, "extra_out", source) if photo else {"ok": True, "path": None}
        if photo and not shot.get("ok"):
            return shot
        mins = max(0, _minutes_between(parse_dt(seg["start_ts"]), parse_dt(now)))
        auto = str(s.get("auto_approve_extra") or "1") == "1"
        con.execute(
            "UPDATE work_segments SET end_ts=?, end_photo=?, minutes=?, status=?, note=?"
            " WHERE id=?",
            (now, shot.get("path"), mins, "approved" if auto else "closed",
             (note or seg["note"] or ""), seg["id"]))
        con.commit()
        seg2 = dict(con.execute("SELECT * FROM work_segments WHERE id=?", (seg["id"],)).fetchone())
    recalc_day(employee_id, seg["work_date"])
    audit(f"employee:{employee_id}", "extra_stop", f"{mins} мин, статус={seg2['status']}")
    return {"ok": True, "segment": seg2,
            "message": f"Нэмэлт ажил дууслаа: {mins} минут ({mins/60:.1f} цаг)."}


def list_segments(employee_id: int | None = None, month: str | None = None,
                  status: str | None = None) -> list[dict]:
    q = ("SELECT s.*, e.code, e.full_name FROM work_segments s "
         "JOIN employees e ON e.id=s.employee_id WHERE 1=1")
    args: list = []
    if employee_id:
        q += " AND s.employee_id=?"; args.append(employee_id)
    if month:
        q += " AND s.work_date LIKE ?"; args.append(f"{month}-%")
    if status:
        q += " AND s.status=?"; args.append(status)
    q += " ORDER BY s.start_ts DESC"
    with connect() as con:
        return [dict(r) for r in con.execute(q, args).fetchall()]


def open_segment(employee_id: int) -> dict | None:
    with connect() as con:
        r = con.execute("SELECT * FROM work_segments WHERE employee_id=? AND status='open'"
                        " ORDER BY id DESC LIMIT 1", (employee_id,)).fetchone()
    return dict(r) if r else None


def approve_segment(segment_id: int, approve: bool = True, by: str = "admin") -> dict:
    with _lock, connect() as con:
        seg = con.execute("SELECT * FROM work_segments WHERE id=?", (segment_id,)).fetchone()
        if not seg:
            return {"ok": False, "error": "Сегмент олдсонгүй."}
        if seg["status"] == "open":
            return {"ok": False, "error": "Эхлээд ажлаа дуусгах бүртгэл хийгдэх ёстой."}
        con.execute("UPDATE work_segments SET status=?, approved_by=? WHERE id=?",
                    ("approved" if approve else "rejected", by, segment_id))
        con.commit()
    recalc_day(seg["employee_id"], seg["work_date"])
    audit(by, "segment_approve" if approve else "segment_reject", f"id={segment_id}")
    return {"ok": True, "message": "Баталгаажлаа." if approve else "Татгалзлаа."}


def segment_minutes(employee_id: int, month: str) -> dict:
    """Сарын нэмэлт ажлын минут (зөвшөөрөгдсөн) ба нээлттэй сегментийн мэдээлэл."""
    with connect() as con:
        rows = [dict(r) for r in con.execute(
            "SELECT * FROM work_segments WHERE employee_id=? AND work_date LIKE ?",
            (employee_id, f"{month}-%")).fetchall()]
    approved = sum(int(r["minutes"] or 0) for r in rows if r["status"] == "approved")
    open_rows = [r for r in rows if r["status"] == "open"]
    open_min = sum(max(0, _minutes_between(parse_dt(r["start_ts"]), now_local())) for r in open_rows)
    today = today_str()
    today_min = sum(max(0, _minutes_between(parse_dt(r["start_ts"]), parse_dt(r["end_ts"])))
                    for r in rows if r["status"] == "approved" and r["work_date"] == today)
    return {"approved_minutes": approved, "open_minutes": open_min, "open": open_rows[0] if open_rows else None,
            "today_minutes": today_min, "count": len(rows),
            "pending": sum(1 for r in rows if r["status"] == "closed")}


def hours_by_day(employee_id: int, month: str) -> list[dict]:
    """Ажилтны өөрийн өдөр тутмын ажилласан цаг (зөвхөн өөрийн — нууцлал)."""
    with connect() as con:
        rows = [dict(r) for r in con.execute(
            "SELECT * FROM attendance WHERE employee_id=? AND work_date LIKE ? ORDER BY work_date",
            (employee_id, f"{month}-%")).fetchall()]
    out = []
    for r in rows:
        iv = segment_minutes_window(employee_id, r["work_date"])
        out.append({
            "work_date": r["work_date"],
            "clock_in": r["clock_in"], "clock_out": r["clock_out"],
            "worked_minutes": int(r["worked_minutes"] or 0),
            "extra_minutes": int(r["extra_minutes"] or 0) + iv,
            "break_minutes": int(r["break_minutes"] or 0),
            "day_credit": round(float(r["day_credit"] or 0), 3),
            "shift_type": r["shift_type"] or "day",
            "status": r["status"], "note": r.get("note") or "",
            "in_photo": r.get("in_photo"), "out_photo": r.get("out_photo"),
            "pay_base": round(float(r["pay_base"] or 0), 2),
            "pay_extra": round(float(r["pay_extra"] or 0), 2),
        })
    return out


def segment_minutes_window(employee_id: int, day: str) -> int:
    with connect() as con:
        r = con.execute("SELECT COALESCE(SUM(minutes),0) m FROM work_segments WHERE employee_id=?"
                        " AND work_date=? AND status='approved'", (employee_id, day)).fetchone()
    return int(r["m"] or 0)


def recalc_day(employee_id: int, day: str) -> dict | None:
    """Нэг өдрийн бүртгэлийг дахин тооцоолно (нэмэлт сегмент нэмэгдсэний дараа)."""
    with _lock, connect() as con:
        row = con.execute("SELECT * FROM attendance WHERE employee_id=? AND work_date=?",
                          (employee_id, day)).fetchone()
        if not row:
            return None
        rec = dict(row)
        extra = segment_minutes_window(employee_id, day)
        rec["extra_segment_minutes"] = extra
        rec = recalc(rec, day, force_workday=bool(int(row["is_workday"] or 0)),
                     employee=get_employee(employee_id), extra_minutes=extra)
        _save_record(rec, con)
        con.commit()
    return rec


# ==========================================================================
# Мэдэгдэл (notifications) — ажил эхлэх/дуусах сануулга, тасарсан бүртгэл
# ==========================================================================
def notify(employee_id: int | None, kind: str, title: str, body: str = "",
           meta: dict | None = None, dedupe: str | None = None) -> dict:
    """Мэдэгдэл бүртгэнэ. dedupe ижил бол давхар илгээхгүй."""
    ts = now_str()
    with _lock, connect() as con:
        if dedupe:
            ex = con.execute("SELECT id FROM notifications WHERE dedupe=?", (dedupe,)).fetchone()
            if ex:
                return {"ok": True, "skipped": True, "id": ex["id"]}
        cur = con.execute(
            "INSERT INTO notifications(employee_id, kind, title, body, meta, dedupe, created_at)"
            " VALUES(?,?,?,?,?,?,?)",
            (employee_id, kind, title, body, json_dumps(meta or {}), dedupe, ts))
        con.commit()
    return {"ok": True, "id": cur.lastrowid}


def json_dumps(obj) -> str:
    import json as _json
    return _json.dumps(obj, ensure_ascii=False)


def list_notifications(employee_id: int | None = None, limit: int = 50,
                       unread_only: bool = False, admin_view: bool = False) -> list[dict]:
    q = ("SELECT n.*, e.code, e.full_name FROM notifications n "
         "LEFT JOIN employees e ON e.id=n.employee_id WHERE 1=1")
    args: list = []
    if employee_id is not None:
        q += " AND n.employee_id=?"; args.append(employee_id)
    elif admin_view:
        pass
    if unread_only:
        q += " AND n.read_at IS NULL"
    q += " ORDER BY n.id DESC LIMIT ?"; args.append(int(limit))
    with connect() as con:
        return [dict(r) for r in con.execute(q, args).fetchall()]


def unread_count(employee_id: int | None) -> int:
    with connect() as con:
        if employee_id is None:
            r = con.execute("SELECT COUNT(*) c FROM notifications WHERE read_at IS NULL").fetchone()
        else:
            r = con.execute("SELECT COUNT(*) c FROM notifications WHERE employee_id=? AND read_at IS NULL",
                            (employee_id,)).fetchone()
    return int(r["c"] or 0)


def mark_notifications_read(ids: list[int] | None = None, employee_id: int | None = None) -> int:
    ts = now_str()
    with _lock, connect() as con:
        if ids:
            q = f"UPDATE notifications SET read_at=? WHERE id IN ({','.join('?' * len(ids))})"
            cur = con.execute(q, [ts] + [int(i) for i in ids])
        elif employee_id is not None:
            cur = con.execute("UPDATE notifications SET read_at=? WHERE employee_id=? AND read_at IS NULL",
                              (ts, employee_id))
        else:
            cur = con.execute("UPDATE notifications SET read_at=? WHERE read_at IS NULL", (ts,))
        con.commit()
    return cur.rowcount


def notify_admins(kind: str, title: str, body: str = "", meta: dict | None = None,
                  dedupe: str | None = None) -> dict:
    return notify(None, kind, title, body, meta=meta, dedupe=dedupe)


def scheduler_tick(now: datetime | None = None, force: bool = False) -> dict:
    """
    Цаг хугацааны мэдэгдэл:
      * ажил эхлэх үед   → бүртгэл хийгээгүй ажилтнуудад сануулга
      * ажил дуусах үед  → гарах бүртгэл хийгээгүйд сануулга
      * дууссанаас хойш  → бүртгэлгүй бол «тасарсан» гэж бүртгэж мэдэгдэнэ
      * шөнийн ээлж 19:00 → хамгаалагчдад ээлжийн сануулга
    """
    now = now or now_local()
    s = get_settings()
    day = now.date().isoformat()
    if not (is_workday(day) or force):
        return {"ok": True, "skipped": "амралтын өдөр"}
    start, end = schedule_window(day)
    lw = lunch_window(day)
    out = {"started": 0, "ending": 0, "missed": 0, "absent": 0, "night": 0}
    emps = list_employees(active_only=True)

    with connect() as con:
        recs = {r["employee_id"]: dict(r) for r in con.execute(
            "SELECT * FROM attendance WHERE work_date=?", (day,)).fetchall()}

    grace = timedelta(minutes=int(float(s.get("notify_missed_minutes") or 15)))

    for e in emps:
        eid, code = e["id"], e["code"]
        rec = recs.get(eid)
        on_leave = leave_minutes_for_window(eid, day, start, end) > 0
        # 1) Ажил эхэлсэн — бүртгэлгүй бол сануулга
        if str(s.get("notify_start") or "1") == "1" and now >= start and not rec and not on_leave:
            r = notify(eid, "start", "Ажил эхэлсэн — бүртгүүлнэ үү",
                       f"{start.strftime('%H:%M')} цагаас ажил эхэлсэн. Зурагтай бүртгэл хийнэ үү.",
                       meta={"date": day, "at": start.strftime("%H:%M")}, dedupe=f"start:{day}:{eid}")
            out["started"] += 1 if not r.get("skipped") else 0
        # 2) Ажил дуусах гэж байна — гарах бүртгэл хийгээгүй бол
        if str(s.get("notify_end") or "1") == "1" and rec and rec.get("clock_in") and not rec.get("clock_out")                 and now >= end - grace:
            notify(eid, "end", "Ажлын цаг дууслаа — гарах бүртгэл хийнэ үү",
                   f"{end.strftime('%H:%M')} цагт ажил дуусна. Зурагтай бүртгэл хийгээгүй бол "
                   "ажилласан цаг тооцогдохгүй.", meta={"date": day}, dedupe=f"end:{day}:{eid}")
        # 3) Ажил дууссанаас хойш бүртгэлгүй → тасарсан
        if str(s.get("auto_absent") or "1") == "1" and now >= end + grace and not rec and not on_leave:
            notify(eid, "absent", "Тасарсан өдөр бүртгэгдлээ",
                   f"{day} өдөр ажилд ирэх бүртгэл хийгдээгүй тул тасарсан гэж тооцогдлоо. "
                   "3 хоног дараалан тасарвал сарын цалин 10% хасагдана.",
                   meta={"date": day}, dedupe=f"absent:{day}:{eid}")
            notify_admins("absent", f"{code} тасарсан",
                          f"{e['full_name']} {day} өдөр бүртгэл хийгээгүй.", dedupe=f"absent-adm:{day}:{eid}")
            out["absent"] += 1
        # 4) Шөнийн ээлж эхлэх — хамгаалагч/шөнийн ажилтанд
        nstart, nend = night_window(day)
        if e.get("night_role") == "guard" and now >= nstart and now < nstart + timedelta(hours=2):
            notify(eid, "night", "Шөнийн ээлж эхэллээ",
                   "19:00–03:00 шөнийн ээлж. Эхлэх ба дуусах зурагтай бүртгэл хийнэ үү.",
                   meta={"date": day}, dedupe=f"night:{day}:{eid}")
            out["night"] += 1

    # 5) Хүлээгдэж буй чөлөөний хүсэлт → админд сануулга (зөвхөн нэг удаа)
    out["leave_pending"] = 0
    if str(s.get("leave_request_notify") or "1") == "1":
        wait_min = int(float(s.get("leave_reminder_minutes") or 30))
        cutoff = (now or now_local()) - timedelta(minutes=wait_min)
        for p in pending_leave_requests():
            created = parse_dt(p.get("created_at"))
            if created and created > cutoff:
                continue                     # саяхан ирсэн — сануулах шаардлагагүй
            notify_admins("leave_pending",
                          f"САНУУЛГА: ХҮСЭЛТ ХҮЛЭЭГДЭЖ БАЙНА — {p['code']} {p['full_name']}",
                          f"{p['start_date']}"
                          f"{'→' + p['end_date'] if p.get('end_date') else ''} "
                          f"({p['hours']}ц) — {wait_min} минутаас дээш шийдэгдээгүй байна. "
                          "Батлах эсвэл татгалзана уу.",
                          meta={"leave_id": p["id"]}, dedupe=f"leave_pend_sched_{p['id']}")
            out["leave_pending"] += 1

    # 6) Ажлаас мэдэгдэлгүй явсан / хаагаагүй бүртгэл → «ирээгүй» цаг + мэдэгдэл
    out["left_early"] = 0
    for e in emps:
        eid, code = e["id"], e["code"]
        rec = recs.get(eid)
        if not rec or not rec.get("clock_in") or rec.get("clock_out"):
            continue
        if now < end + grace:
            continue
        notify(eid, "absent", "Бүртгэл хаагдаагүй — «ирээгүй» цаг тооцогдлоо",
               f"{end.strftime('%H:%M')} цагт ажил дууссан боловч гарах бүртгэл хийгдээгүй тул "
               f"энэ өдрийн дутуу цаг «ирээгүй» гэж тооцогдлоо. Ажилтны буруу.",
               meta={"date": day, "kind": "no_clockout"}, dedupe=f"left:{day}:{eid}")
        notify_admins("shift_unclosed", "Хаагдаагүй бүртгэл — «ирээгүй» цаг",
                      f"{code} {e['full_name']} — {day} өдөр гарах бүртгэлгүй. Дутуу цаг нь ирээгүй цагт тооцогдлоо.",
                      meta={"date": day, "employee_id": eid}, dedupe=f"left-adm:{day}:{eid}")
        out["left_early"] += 1

    # 7) Өдрийн төлөвийг (хэвийн/чөлөө/ирээгүй) дахин тооцож хадгална
    if recs:
        with _lock, connect() as con:
            for e in emps:
                r = recs.get(e["id"])
                if not r:
                    continue
                fixed = recalc(r, day, employee=e)
                _save_record(fixed, con)
            con.commit()

    out["ok"] = True
    out["at"] = now.strftime("%Y-%m-%d %H:%M")
    return out


def pending_leave_requests(employee_id: int | None = None) -> list[dict]:
    """Хүлээгдэж буй чөлөөний хүсэлтүүд (админд)."""
    with connect() as con:
        q = ("SELECT l.*, e.code, e.full_name FROM leaves l JOIN employees e ON e.id=l.employee_id "
             "WHERE l.status='pending'")
        args: list = []
        if employee_id:
            q += " AND l.employee_id=?"; args.append(employee_id)
        q += " ORDER BY l.id DESC"
        return [dict(r) for r in con.execute(q, args).fetchall()]


def missed_clockouts(day: str | None = None) -> list[dict]:
    """Тухайн өдөр орсон ч гараагүй ажилтнууд (админд харагдана)."""
    day = day or today_str()
    with connect() as con:
        rows = [dict(r) for r in con.execute(
            "SELECT a.*, e.code, e.full_name FROM attendance a JOIN employees e ON e.id=a.employee_id"
            " WHERE a.work_date=? AND a.clock_in IS NOT NULL AND (a.clock_out IS NULL OR a.clock_out='')",
            (day,)).fetchall()]
    return rows


# ==========================================================================
# Ажилтны бодит цагийн цалин (real-time)
# ==========================================================================
def live_pay(employee_id: int, month: str | None = None) -> dict:
    """
    Ажилтны энэ сарын бодит цаг хугацааны цалин:
    хаагдсан өдрүүд + өнөөдрийн идэвхтэй цаг (минут тутам) + нэмэлт ажил − торгууль.
    """
    month = month or today_str()[:7]
    emp = get_employee(employee_id) or {}
    rate = float(emp.get("daily_rate") or 0)
    s = get_settings()
    row = None
    for r in monthly_payroll(month)["rows"]:
        if r["employee_id"] == employee_id:
            row = r
            break
    if not row:
        return {"ok": False, "error": "Ажилтан олдсонгүй."}

    today = today_str()
    seg = segment_minutes(employee_id, month)
    open_seg = seg.get("open")
    open_min = 0
    if open_seg:
        open_min = max(0, _minutes_between(parse_dt(open_seg["start_ts"]), now_local()))
    open_is_night = str(open_seg.get("kind") or "") == "night" if open_seg else False
    open_mult = (float(s["guard_percent"]) if str(emp.get("night_role") or "") == "guard"
                 else float(s["worker_percent"])) / 100.0
    open_pay = hourly_rate(rate, "night" if open_is_night else "day",
                           open_mult if open_is_night else 1.0) * (open_min / 60.0)

    with connect() as con:
        row_today = con.execute("SELECT * FROM attendance WHERE employee_id=? AND work_date=?",
                                (employee_id, today)).fetchone()
    t = dict(row_today) if row_today else None
    today_live_min, today_live_pay, on_shift = 0, 0.0, False
    if t and t.get("clock_in") and not t.get("clock_out"):
        on_shift = True
        since = parse_dt(t["clock_in"])
        today_live_min = max(0, _minutes_between(since, now_local()))
        lunched = lunch_deducted(since, now_local(), today) if today_live_min else 0
        win_today = shift_minutes(today, "night" if str(t.get("shift_type")) == "night" else "day")
        credited = min(win_today, max(0, today_live_min - lunched))
        mult = float(t.get("pay_multiplier") or 1)
        today_live_pay = rate * mult * (credited / win_today)

    accrued = float(row["total"]) + today_live_pay + open_pay
    hours_closed = float(row["day_credit"]) * (paid_minutes_per_day() / 60.0)
    return {
        "month": month,
        "employee": {"id": employee_id, "code": emp.get("code"), "full_name": emp.get("full_name"),
                     "daily_rate": rate, "night_role": emp.get("night_role")},
        "as_of": now_str(),
        "schedule": {"start": s["schedule_start"], "end": s["schedule_end"],
                     "lunch": f"{s.get('lunch_start')}–{s.get('lunch_end')}",
                     "lunch_paid": str(s.get("lunch_paid") or "0") == "1",
                     "paid_minutes_per_day": paid_minutes_per_day(),
                     "paid_hours_per_day": round(paid_minutes_per_day() / 60.0, 2),
                     "hourly_rate": round(hourly_rate(rate), 2),
                     "night_start": s["night_start"], "night_end": s["night_end"],
                     "night_minutes": shift_minutes(today, "night"),
                     "night_hours": round(shift_minutes(today, "night") / 60.0, 2),
                     "night_hourly_rate": round(hourly_rate(
                         rate, "night", (float(t.get("pay_multiplier") or 1) if t else 1.0)), 2)},
        "hours": {
            "closed_days": round(float(row["day_credit"]), 3),
            "closed_hours": round(hours_closed, 2),
            "today_minutes": today_live_min,
            "today_hours": round(today_live_min / 60.0, 2),
            "extra_hours": round((seg["approved_minutes"] + seg["open_minutes"]) / 60.0, 2),
            "on_shift": on_shift,
        },
        "today_status": {
            "code": (t or {}).get("day_status") or ("working" if on_shift else ""),
            "label": DAY_STATUS_LABEL.get((t or {}).get("day_status") or "", "—"),
            "absent_minutes": int((t or {}).get("absent_minutes") or 0),
            "leave_minutes": int((t or {}).get("leave_minutes") or 0),
        },
        "leave_requests": {
            "pending": len([x for x in list_leaves(month, employee_id, status="pending")]),
            "approved": len([x for x in list_leaves(month, employee_id, status="approved")]),
        },
        "pay": {
            "base": row["pay_base"], "extra": row["pay_extra"], "leave": row["leave_pay"],
            "penalty": row["penalty"],
            "today_accrued": round(today_live_pay, 2),
            "open_extra_accrued": round(open_pay, 2),
            "accrued_total": round(accrued, 2),
        },
        "night_shifts": row["night_days"],
        "absent": {"days": row["absent_days"], "streak": row["absent_streak"], "list": row["absent_list"]},
        "photo_required": str(s.get("require_photo") or "1") == "1",
        "unread_notifications": unread_count(employee_id),
    }


# --------------------------------------------------------------------------
# Цалин — барилгын бригадын загвар (өдрийн цалин, шөнийн ээлж, нэмэлт цаг)
# --------------------------------------------------------------------------
def fmt_money(v) -> str:
    try:
        return f"{round(float(v)):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def night_role_label(role: str | None) -> str:
    if role == "guard":
        return "Хамгаалалт"
    if role == "worker":
        return "Ажилчин"
    return "—"


def employee_pay(eid: int) -> dict:
    e = get_employee(eid)
    if not e:
        return {}
    s = get_settings()
    rate = float(e["daily_rate"] or 0)
    return {
        "employee_id": e["id"], "code": e["code"], "full_name": e["full_name"],
        "daily_rate": rate,
        "night_role": e["night_role"] or "worker",
        "site": employee_site(e),
        "night_half": round(rate * float(s["guard_percent"]) / 100.0, 2),
        "night_full": round(rate * float(s["worker_percent"]) / 100.0, 2),
    }


def set_extra_hours(employee_id: int, day: str, hours, note: str = "") -> dict:
    """Админ ажилтанд нэмэлт ажлын цаг гараар нэмнэ (эсвэл 0 болгож хасна)."""
    try:
        hrs = round(float(hours), 2)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Цагийн утга буруу байна."}
    if hrs < 0:
        return {"ok": False, "error": "Нэмэлт цаг сөрөг байж болохгүй."}
    emp = get_employee(employee_id)
    if not emp:
        return {"ok": False, "error": "Ажилтан олдсонгүй."}
    day = day or today_str()
    rec = get_record(employee_id, day)
    if not rec:
        rec = {
            "employee_id": employee_id, "work_date": day, "clock_in": None, "clock_out": None,
            "note": "", "edited": 1,
        }
        if is_workday(day):
            rec["is_workday"] = 1
    rec["extra_admin_minutes"] = int(round(hrs * 60))
    rec["extra_minutes"] = int(round(hrs * 60)) + int(rec.get("extra_segment_minutes") or 0)
    rec["edited"] = 1
    if note:
        rec["note"] = note.strip()
    new = recalc(rec, day, employee=emp)
    with _lock, connect() as con:
        _save_record(new, con)
        con.commit()
    audit("admin", "extra_hours", f"emp={employee_id} {day} +{hrs}ц")
    return {"ok": True, "record": get_record(employee_id, day),
            "message": f"Нэмэлт цаг {hrs}ц бүртгэгдлээ ({fmt_money(new['pay_extra'])} ₮)."}


def worked_day_credit(rec: dict) -> float:
    """Тухайн бүртгэл хэдэн өдрийн хөдөлмөр болохыг буцаана (шөнө = бүтэн өдөр)."""
    if not rec or not rec.get("clock_in"):
        return 0.0
    return float(rec.get("day_credit") or 0)


def payroll_extra(emp_row, recs: list[dict], month: str) -> dict:
    """
    Нэг ажилтны сарын цалин:
    үндсэн цалин (хөдөлмөрийн өдөр × өдрийн цалин, шөнийн коэффициент) +
    нэмэлт цаг + цалинтай чөлөө − 3 хоног дараалан тасарвал 10% торгууль.
    """
    s = get_settings()
    eid, rate = emp_row["id"], float(emp_row["daily_rate"] or 0)
    credit = sum(worked_day_credit(r) for r in recs)
    days_worked = sum(1 for r in recs if r.get("clock_in"))
    night_days = sum(1 for r in recs if r.get("clock_in") and (r.get("shift_type") or "day") == "night")
    role_days = {"guard": 0, "worker": 0}
    for r in recs:
        if r.get("clock_in") and (r.get("shift_type") or "day") == "night":
            role = r.get("night_role") or emp_row["night_role"]
            role_days["guard" if role == "guard" else "worker"] += 1
    pay_base = round(sum(float(r.get("pay_base") or 0) for r in recs), 2)
    pay_extra = round(sum(float(r.get("pay_extra") or 0) for r in recs), 2)
    extra_minutes = sum(int(r.get("extra_minutes") or 0) for r in recs)

    lv = leave_summary(eid, month)
    # v3.1: цалинтай эсэхийг чөлөө бүрийн `paid` талбараар шийднэ (админ батлахдаа тэмдэглэнэ)
    paid_hours = 0.0
    for x in list_leaves(month, eid, status="approved"):
        if not int(x.get("paid") or 0):
            continue
        if int(x["all_day"] or 0) == 1:
            days = 0
            dd = date.fromisoformat(x["start_date"])
            ed = date.fromisoformat(x["end_date"] or x["start_date"])
            while dd <= ed:
                if is_workday(dd) and dd.isoformat().startswith(month):
                    days += 1
                dd += timedelta(days=1)
            paid_hours += days * (paid_minutes_per_day(month + "-01") / 60.0)
        else:
            paid_hours += float(x["hours"] or 0)
    paid_hours = round(paid_hours, 2)
    leave_pay = round(hourly_rate(rate) * paid_hours, 2)

    absent = absent_days(eid, month)
    streak, streak_run = max_absent_streak(absent, month)
    thr = int(float(s["absence_penalty_days"] or 3))
    pct = float(s["absence_penalty_percent"] or 10)
    penalty = round((pay_base + pay_extra + leave_pay) * pct / 100.0, 2) if streak >= thr else 0.0

    gross = round(pay_base + pay_extra + leave_pay, 2)      # торгуулийн өмнөх цалин
    total = round(gross - penalty, 2)                        # олгох цалин
    if streak >= thr:
        pay_status, color = "Шийтгэл −10%", "red"
    elif absent:
        pay_status, color = "Тасалсан хоногтой", "orange"
    elif days_worked == 0 and sum(v["hours"] for v in lv.values()):
        pay_status, color = "Чөлөөтэй", LEAVE_COLORS.get("чөлөө", "blue")
    elif days_worked == 0:
        pay_status, color = "Бүртгэлгүй", "grey"
    else:
        pay_status, color = "Хэвийн", "green"

    return {
        "days_worked": days_worked,
        "day_credit": round(credit, 3),
        "credit_hm": fmt_hhmm(int(round(credit * paid_minutes_per_day(month + "-01")))),
        "night_days": night_days,
        "night_guard_days": role_days["guard"],
        "night_worker_days": role_days["worker"],
        "daily_rate": rate,
        "pay_base": pay_base,
        "pay_extra": pay_extra,
        "extra_hours": round(extra_minutes / 60.0, 2),
        "leave_pay": leave_pay,
        "paid_leave_hours": paid_hours,
        "leave": lv,
        "absent_days": len(absent),
        "absent_list": absent,
        "absent_hours": round(sum(int(r.get("absent_minutes") or 0) for r in recs) / 60.0, 2),
        "leave_hours": round(sum(int(r.get("leave_minutes") or 0) for r in recs) / 60.0, 2),
        "absent_streak": streak,
        "absent_streak_run": streak_run,
        "penalty_percent": pct if penalty else 0,
        "penalty": penalty,
        "gross": gross,
        "total": total,
        "pay_status": pay_status,
        "color": color,
    }


def monthly_payroll(month: str) -> dict:
    """Сарын цалингийн тооцоо — админд зориулсан бүрэн хүснэгт."""
    y, m = int(month[:4]), int(month[5:7])
    with connect() as con:
        emps = [dict(r) for r in con.execute(
            "SELECT * FROM employees WHERE active=1 ORDER BY code").fetchall()]
        recs = [dict(r) for r in con.execute(
            "SELECT * FROM attendance WHERE work_date LIKE ? ORDER BY work_date",
            (f"{month}-%",)).fetchall()]
    by_emp: dict[int, list[dict]] = {}
    for r in recs:
        by_emp.setdefault(r["employee_id"], []).append(r)

    rows = []
    for e in emps:
        pl = payroll_extra(e, by_emp.get(e["id"], []), month)
        site = employee_site(e) or {}
        rows.append({
            "employee_id": e["id"], "code": e["code"], "full_name": e["full_name"],
            "position": e["position"] or "", "department": e["department"] or "",
            "site_name": site.get("name") or get_setting("geofence_name"),
            "site_id": e["site_id"], "night_role": e["night_role"] or "worker",
            **pl,
        })
    totals = {
        "employees": len(rows),
        "days_worked": sum(r["days_worked"] for r in rows),
        "day_credit": round(sum(r["day_credit"] for r in rows), 2),
        "night_days": sum(r["night_days"] for r in rows),
        "extra_hours": round(sum(r["extra_hours"] for r in rows), 2),
        "pay_base": round(sum(r["pay_base"] for r in rows), 2),
        "pay_extra": round(sum(r["pay_extra"] for r in rows), 2),
        "leave_pay": round(sum(r["leave_pay"] for r in rows), 2),
        "penalty": round(sum(r["penalty"] for r in rows), 2),
        "gross": round(sum(r["gross"] for r in rows), 2),
        "total": round(sum(r["total"] for r in rows), 2),
        "penalized_employees": sum(1 for r in rows if r["penalty"]),
    }
    return {
        "month": month, "month_label": f"{y} оны {MONTH_MN[m]}",
        "currency": get_setting("currency"),
        "generated_at": now_local().strftime("%Y-%m-%d %H:%M:%S"),
        "company_name": get_setting("company_name"),
        "rules": {
            "night_start": get_setting("night_start"),
            "night_end": get_setting("night_end"),
            "guard_percent": float(get_setting("guard_percent")),
            "worker_percent": float(get_setting("worker_percent")),
            "absence_penalty_days": int(float(get_setting("absence_penalty_days"))),
            "absence_penalty_percent": float(get_setting("absence_penalty_percent")),
            "paid_leave_kinds": [x.strip() for x in
                                 str(get_setting("paid_leave_kinds")).split(",") if x.strip()],
        },
        "rows": rows, "totals": totals,
    }


# --------------------------------------------------------------------------
# ХОЁР ТӨЛБӨР (v4.5): ҮНДСЭН ЦАЛИН 10-нд (11 → 10 үе) · АВАНС 25-нд (11 → 24)
# --------------------------------------------------------------------------
ADVANCE_STATUS_LABEL = {"paid": "Олгосон", "pending": "Хүлээгдэж байна",
                        "cancelled": "Цуцлагдсан", "none": "Олгоогүй"}
ADVANCE_STATUS_COLOR = {"paid": "green", "pending": "orange",
                        "cancelled": "gray", "none": "gray"}
def full_day_credit_min() -> float:
    """«Бүтэн ажлын өдөр» гэж тооцох доод хэмжээ (анхдагч: ээлжийн 90%)."""
    try:
        v = float(get_setting("full_day_min_credit") or 0.9)
    except (TypeError, ValueError):
        v = 0.9
    return min(1.0, max(0.1, v))


def is_full_day(rec: dict, min_credit: float | None = None) -> bool:
    """Тухайн бүртгэл «бүтэн өдөр» эсэх (шөнийн ээлж ч бүтэн өдөр)."""
    if not rec or not rec.get("clock_in"):
        return False
    need = full_day_credit_min() if min_credit is None else min_credit
    return float(rec.get("day_credit") or 0) >= need - 1e-9


def _pd(name: str, default: int) -> int:
    try:
        v = int(float(get_setting(name) or default))
    except (TypeError, ValueError):
        v = default
    return max(1, min(28, v))


def pay_period_bounds(period_key: str) -> dict:
    """
    period_key = 'YYYY-MM' — тухайн сарын 10-нд ОЛГОХ үндсэн цалингийн үе:
      * эхлэл: өмнөх сарын 11 (period_start_day)
      * төгсгөл: тухайн сарын 10 (pay_day)
      * аванс: энэ үеийн эхний хагас (11 → 24), 25-нд олгогдоно
    """
    y, m = int(period_key[:4]), int(period_key[5:7])
    pay_day = _pd("pay_day", 10)
    start_day = _pd("period_start_day", 11)
    adv_day = _pd("advance_day", 25)
    adv_end = _pd("advance_window_end_day", 24)
    prev_last = date(y, m, 1) - timedelta(days=1)
    start = prev_last.replace(day=min(start_day, prev_last.day))
    end = date(y, m, pay_day)
    adv_win_start = start
    adv_win_end = prev_last.replace(day=min(adv_end, prev_last.day))
    adv_pay = prev_last.replace(day=min(adv_day, prev_last.day))
    return {
        "period": period_key,
        "start": start.isoformat(), "end": end.isoformat(),
        "payout_date": end.isoformat(),
        "advance_window": [adv_win_start.isoformat(), adv_win_end.isoformat()],
        "advance_pay_date": adv_pay.isoformat(),
        "label": f"{start.strftime('%Y-%m-%d')} → {end.strftime('%Y-%m-%d')}",
        "payout_label": f"{end.strftime('%Y-%m-%d')}-нд олгоно",
        "advance_label": (f"{adv_win_start.strftime('%m-%d')} → {adv_win_end.strftime('%m-%d')} "
                          f"({adv_pay.strftime('%Y-%m-%d')}-нд олгоно)"),
    }


def period_key_for(d=None) -> str:
    """Тухайн өдрийн хамаарах үе: 10-ны дотор бол энэ сар, 11-нээс хойш бол дараа сар."""
    d = date.fromisoformat(d) if isinstance(d, str) else (d or date.fromisoformat(today_str()))
    if d.day <= _pd("pay_day", 10):
        return f"{d.year}-{d.month:02d}"
    nxt = (d.replace(day=1) + timedelta(days=32)).replace(day=1)
    return f"{nxt.year}-{nxt.month:02d}"


def recent_periods(n: int = 14) -> list[str]:
    """Сүүлийн n үе (хамгийн сүүлийнх эхэнд)."""
    key = period_key_for()
    y, m = int(key[:4]), int(key[5:7])
    out = []
    for _ in range(n):
        out.append(f"{y}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def period_workdays(start: str, end: str, upto_today: bool = False) -> list[str]:
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    if upto_today:
        today = date.fromisoformat(today_str())
        if d1 > today:
            d1 = today
    out, d = [], d0
    while d <= d1:
        if is_workday(d):
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _period_rows(employee_id: int, start: str, end: str) -> list[dict]:
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM attendance WHERE employee_id=? AND work_date BETWEEN ? AND ?"
            " ORDER BY work_date", (employee_id, start, end)).fetchall()]


def full_work_days(employee_id: int, start: str, end: str) -> dict:
    """Цонх дотор БҮТЭН ээлж ажилласан өдрүүд (шөнийн ээлж ч бүтэн өдөр)."""
    need = full_day_credit_min()
    rows = _period_rows(employee_id, start, end)
    full = [r["work_date"] for r in rows if is_full_day(r, need)]
    partial = [r["work_date"] for r in rows
               if r.get("clock_in") and 0 < float(r.get("day_credit") or 0) < need - 1e-9]
    return {"full_days": len(full), "full_list": full,
            "partial_days": len(partial), "worked_days": len(full) + len(partial),
            "min_credit": need}


def advance_window_full_days(employee_id: int, period_key: str) -> dict:
    b = pay_period_bounds(period_key)
    return full_work_days(employee_id, b["advance_window"][0], b["advance_window"][1])


def window_earnings(employee_id: int, period_key: str) -> float:
    """Авансын цонх (11 → 24)-онд ажилласан цалин — авансын дээд хязгаар."""
    b = pay_period_bounds(period_key)
    rows = _period_rows(employee_id, b["advance_window"][0], b["advance_window"][1])
    return round(sum(float(r.get("pay_base") or 0) + float(r.get("pay_extra") or 0)
                     for r in rows), 2)


def advance_rules() -> dict:
    return {
        "enabled": str(get_setting("advance_enabled") or "1") == "1",
        "advance_day": _pd("advance_day", 25),
        "advance_window_end_day": _pd("advance_window_end_day", 24),
        "amount": float(get_setting("advance_amount") or 1000000),
        "min_full_days": int(float(get_setting("advance_min_full_days") or 7)),
        "min_credit": full_day_credit_min(),
        "cap_earned": str(get_setting("advance_cap_earned") or "1") == "1",
        "pay_day": _pd("pay_day", 10),
        "period_start_day": _pd("period_start_day", 11),
    }


def get_advance(employee_id: int, period_key: str) -> dict | None:
    with connect() as con:
        r = con.execute("SELECT * FROM advances WHERE employee_id=? AND period_key=?",
                        (employee_id, period_key)).fetchone()
    return dict(r) if r else None


def list_advances(period_key: str, status: str | None = None) -> list[dict]:
    q = ("SELECT a.*, e.code, e.full_name, e.position, e.daily_rate FROM advances a "
         "JOIN employees e ON e.id=a.employee_id WHERE a.period_key=?")
    args: list = [period_key]
    if status:
        q += " AND a.status=?"
        args.append(status)
    q += " ORDER BY e.code"
    with connect() as con:
        return [dict(r) for r in con.execute(q, args).fetchall()]


def advance_candidates(period_key: str) -> dict:
    """
    Тухайн үед хэн аванс авах вэ: 11 → 24 цонхонд БҮТЭН 7 хоногоос ДЭЭШ ажилласан бол
    `advance_amount` (анхдагч 1 000 000₮). Олгосон/хүлээгдэж буй бичлэгтэй нэгтгэнэ.
    """
    rules = advance_rules()
    b = pay_period_bounds(period_key)
    ws, we = b["advance_window"]
    period_rows = {r["employee_id"]: r for r in period_payroll(period_key)["rows"]}
    with connect() as con:
        emps = [dict(r) for r in con.execute(
            "SELECT * FROM employees WHERE active=1 ORDER BY code").fetchall()]
    rows = []
    for e in emps:
        fd = full_work_days(e["id"], ws, we)
        rec = get_advance(e["id"], period_key)
        eligible = rules["enabled"] and fd["full_days"] > rules["min_full_days"]
        st = rec["status"] if rec else ("pending" if eligible else "none")
        pr = period_rows.get(e["id"]) or {}
        earned = window_earnings(e["id"], period_key)
        suggested = rules["amount"] if eligible else 0.0
        capped = False
        if eligible and rules["cap_earned"] and earned < suggested:
            suggested, capped = round(max(0.0, earned), 2), True
        rows.append({
            "employee_id": e["id"], "code": e["code"], "full_name": e["full_name"],
            "position": e["position"] or "", "daily_rate": float(e["daily_rate"] or 0),
            "full_days": fd["full_days"], "partial_days": fd["partial_days"],
            "worked_days": fd["worked_days"], "full_list": fd["full_list"],
            "min_full_days": rules["min_full_days"],
            "threshold_label": f"{rules['min_full_days']} хоногоос дээш "
                               f"({rules['min_full_days'] + 1}+)",
            "eligible": bool(eligible),
            "reason": (f"Бүтэн өдөр {fd['full_days']} > {rules['min_full_days']} — аванс авах эрхтэй"
                       if eligible else
                       f"Бүтэн өдөр {fd['full_days']} ≤ {rules['min_full_days']} — аванс авахгүй"),
            "suggested_amount": suggested,
            "window_earnings": earned,
            "capped": capped,
            "cap_note": (f"11–24-нд ажилласан цалин {fmt_money(earned)}₮ — аванс үүнээс "
                         f"хэтрэхгүй" if capped else ""),
            "amount": float(rec["amount"]) if rec else suggested,
            "status": st, "status_label": ADVANCE_STATUS_LABEL.get(st, "—"),
            "status_color": ADVANCE_STATUS_COLOR.get(st, "gray"),
            "advance_id": rec["id"] if rec else None,
            "paid_on": rec["paid_on"] if rec else None,
            "note": rec["note"] if rec else "",
            "period_gross": pr.get("gross") or 0.0,
            "period_days_worked": pr.get("days_worked") or 0,
            "over_income": bool(rec and rec["status"] == "paid"
                                and float(rec["amount"]) > (pr.get("gross") or 0)),
        })
    eligible_rows = [r for r in rows if r["eligible"]]
    paid = [r for r in rows if r["status"] == "paid"]
    totals = {
        "employees": len(rows), "eligible": len(eligible_rows), "paid": len(paid),
        "paid_total": round(sum(r["amount"] for r in paid), 2),
        "eligible_total": round(sum(r["suggested_amount"] for r in eligible_rows), 2),
        "pending_total": round(sum(r["suggested_amount"] for r in eligible_rows
                                   if r["status"] != "paid"), 2),
    }
    return {"period": period_key, "bounds": b, "rules": rules, "rows": rows, "totals": totals}


def set_advance(employee_id: int, period_key: str, status: str = "paid",
                amount=None, note: str = "", by: str = "admin",
                paid_on: str | None = None) -> dict:
    """Авансыг «олгосон»/«цуцалсан» гэж тэмдэглэнэ (үндсэн цалингаас хасагдана)."""
    emp = get_employee(employee_id)
    if not emp:
        return {"ok": False, "error": "Ажилтан олдсонгүй."}
    if status not in ("paid", "pending", "cancelled"):
        return {"ok": False, "error": "Авансын төлөв буруу байна."}
    rules = advance_rules()
    b = pay_period_bounds(period_key)
    fd = advance_window_full_days(employee_id, period_key)
    if amount is None or amount == "":
        amount = rules["amount"] if fd["full_days"] > rules["min_full_days"] else 0.0
        if rules["cap_earned"]:
            amount = min(amount, window_earnings(employee_id, period_key))
    try:
        amount = round(float(amount), 2)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Авансын дүн буруу байна."}
    if status == "paid" and amount <= 0:
        return {"ok": False, "error": "Авансын дүн 0-ээс их байх ёстой."}
    now = now_local().strftime("%Y-%m-%d %H:%M:%S")
    paid_on = (paid_on or (now_local().date().isoformat() if status == "paid" else None)) \
        if status == "paid" else None
    with _lock, connect() as con:
        con.execute(
            "INSERT INTO advances(employee_id, period_key, window_start, window_end, full_days,"
            " amount, status, paid_on, note, created_by, created_at, updated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(employee_id, period_key) DO UPDATE SET"
            " window_start=excluded.window_start, window_end=excluded.window_end,"
            " full_days=excluded.full_days, amount=excluded.amount, status=excluded.status,"
            " paid_on=excluded.paid_on, note=excluded.note, updated_at=excluded.updated_at",
            (employee_id, period_key, b["advance_window"][0], b["advance_window"][1],
             fd["full_days"], amount, status,
             paid_on or None, note, by, now, now))
        con.commit()
    rec = get_advance(employee_id, period_key)
    audit(by, "advance_" + status,
          f"{emp['code']} {emp['full_name']}: {period_key} үе, {amount:,.0f}₮ "
          f"(бүтэн өдөр {fd['full_days']})")
    if status == "paid" and rec:
        notify(employee_id, "advance_paid", f"Аванс олгогдлоо — {fmt_money(amount)}₮",
               f"{b['advance_window'][0]} → {b['advance_window'][1]} хугацааны аванс. "
               f"Энэ дүн {b['payout_date']}-ны үндсэн цалингаас хасагдана.",
               meta={"period": period_key, "advance_id": rec["id"], "amount": amount},
               dedupe=f"adv_paid_{rec['id']}")
        notify_admins("advance_paid", f"АВАНС ОЛГОГДЛОО — {emp['code']} {emp['full_name']}",
                      f"{fmt_money(amount)}₮ · {b['label']} үе · {b['payout_date']}-ны "
                      f"үндсэн цалингаас хасагдана.",
                      meta={"period": period_key, "employee_id": employee_id},
                      dedupe=f"adv_paid_admin_{rec['id']}")
    msg = (f"{emp['full_name']}: {fmt_money(amount)}₮ аванс олгогдсон гэж бүртгэгдлээ — "
           f"{b['payout_date']}-ны цалингаас хасагдана." if status == "paid" else
           f"{emp['full_name']}: авансын бичлэг «{ADVANCE_STATUS_LABEL[status]}» боллоо.")
    return {"ok": True, "advance": rec, "employee": emp, "message": msg}


def reset_advance(employee_id: int, period_key: str, by: str = "admin") -> dict:
    """
    Авансын бүртгэлийг анхны төлөвт буцаана:
      • эрхтэй бол  → «хүлээгдэж байна» (аванс олгоогүй, 10-ны цалин бүтэн)
      • эрхгүй бол  → бичлэгийг устгана («Олгоогүй», 10-ны цалин бүтэн)
    """
    emp = get_employee(employee_id)
    if not emp:
        return {"ok": False, "error": "Ажилтан олдсонгүй."}
    b = pay_period_bounds(period_key)
    fd = advance_window_full_days(employee_id, period_key)
    eligible = advance_rules()["enabled"] and fd["full_days"] > advance_rules()["min_full_days"]
    if eligible:
        res = set_advance(employee_id, period_key, status="pending",
                          amount=advance_candidates(period_key)["rows"] and
                          next((r["suggested_amount"] for r in advance_candidates(period_key)["rows"]
                                if r["employee_id"] == employee_id), 0.0),
                          note="", by=by)
        if not res.get("ok"):
            return res
        return {"ok": True, "advance": res["advance"], "employee": emp,
                "message": f"{emp['full_name']}: аванс «хүлээгдэж байна» төлөвт буцлаа — "
                           f"{fmt_money(res['advance']['amount'])}₮ {b['advance_pay_date']}-нд олгох боломжтой."}
    with _lock, connect() as con:
        con.execute("DELETE FROM advances WHERE employee_id=? AND period_key=?",
                    (employee_id, period_key))
        con.commit()
    audit(by, "advance_reset",
          f"{emp['code']} {emp['full_name']}: {period_key} үеийн авансын бичлэг устгагдлаа "
          f"(бүтэн өдөр {fd['full_days']} ≤ {advance_rules()['min_full_days']})")
    return {"ok": True, "advance": None, "employee": emp,
            "message": f"{emp['full_name']}: аванс авах эрхгүй (бүтэн өдөр {fd['full_days']} ≤ "
                       f"{advance_rules()['min_full_days']}) — бичлэг устгагдаж, цалин бүтнээр "
                       f"{b['payout_date']}-нд олгогдоно."}


def make_backup_zip(max_photo_mb: int = 250) -> bytes:
    """
    Бүрэн нөөц хуулбар (ZIP, санах ойд): SQLite-ийн тогтвортой хуулбар + бүх зураг.
    Render/VPS дээр shell-гүйгээр татаж авахад зориулав (админ эрхээр).
    """
    info = {"created_at": now_local().strftime("%Y-%m-%d %H:%M:%S"),
            "company": get_setting("company_name"),
            "photos_included": 0, "photos_skipped": 0, "photos_mb": 0.0}
    db_bytes = 0
    snap = os.path.join(tempfile.gettempdir(), f"att_snap_{uuid.uuid4().hex}.db")
    try:
        with connect() as con:
            con.execute("VACUUM INTO ?", (snap,))          # тогтвортой (WAL-гүй) хуулбар
        db_bytes = os.path.getsize(snap)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            z.write(snap, "attendance.db")
            total = 0
            limit = max_photo_mb * 1024 * 1024
            if os.path.isdir(PHOTO_DIR):
                for root, _dirs, files in os.walk(PHOTO_DIR):
                    for fn in sorted(files):
                        p = os.path.join(root, fn)
                        try:
                            sz = os.path.getsize(p)
                        except OSError:
                            continue
                        if total + sz > limit:
                            info["photos_skipped"] += 1
                            continue
                        z.write(p, os.path.relpath(p, DATA_DIR))
                        total += sz
                        info["photos_included"] += 1
            info["photos_mb"] = round(total / 1024 / 1024, 1)
            info["db_mb"] = round(db_bytes / 1024 / 1024, 2)
            z.writestr("BACKUP_INFO.txt",
                       "Цаг бүртгэл ба ирцийн систем — нөөц хуулбар\n"
                       + "=" * 46 + "\n"
                       + "\n".join(f"{k}: {v}" for k, v in info.items())
                       + "\n\nСэргээх: attendance.db-г data/attendance.db болгож хуулна,\n"
                         "photos/ хавтсыг бас data/ доор тавина.\n")
        return buf.getvalue()
    finally:
        try:
            os.remove(snap)
        except OSError:
            pass


def demo_seed_advances(period_key: str | None = None, pending_codes=("EMP011",)) -> dict:
    """
    Демо: 25-ны авансыг эрхтэй ажилтнуудад ОЛГОСОН төлөвт оруулна
    (paid_on = аванс олгох өдөр); `pending_codes` доторх ажилтан хүлээгдэж үлдэнэ.
    """
    key = period_key or period_key_for()
    b = pay_period_bounds(key)
    paid, total = [], 0.0
    for r in advance_candidates(key)["rows"]:
        if not r["eligible"] or r["code"] in pending_codes:
            continue
        res = set_advance(r["employee_id"], key, status="paid",
                          amount=r["suggested_amount"],
                          note="Демо аванс — 25-нд олгосон",
                          paid_on=b["advance_pay_date"], by="system")
        if res.get("ok"):
            paid.append(r["code"])
            total += float(res["advance"]["amount"])
    audit("system", "demo_advances",
          f"{key} үе: {len(paid)} ажилтанд {fmt_money(total)}₮ аванс олгосон "
          f"({', '.join(paid)})")
    return {"ok": True, "period": key, "paid": paid, "count": len(paid),
            "total": round(total, 2), "paid_on": b["advance_pay_date"]}


def cancel_advance(employee_id: int, period_key: str) -> dict:
    rec = get_advance(employee_id, period_key)
    if not rec:
        return {"ok": False, "error": "Авансын бичлэг олдсонгүй."}
    return set_advance(employee_id, period_key, status="cancelled",
                       amount=rec["amount"], note=rec.get("note") or "")


def _absent_days_range(employee_id: int, start: str, end: str) -> list[str]:
    """absent_days() — хугацааны мужид (үе 11 → 10-д тохируулсан)."""
    rows = {r["work_date"]: r for r in _period_rows(employee_id, start, end)}
    covered: set[str] = set()
    for lv in list_leaves(None, employee_id, status="approved"):
        if int(lv["all_day"] or 0) != 1:
            continue
        dd = date.fromisoformat(lv["start_date"])
        ed = date.fromisoformat(lv["end_date"] or lv["start_date"])
        while dd <= ed:
            covered.add(dd.isoformat())
            dd += timedelta(days=1)
    today = today_str()
    workdays = period_workdays(start, end)
    out = []
    for d in workdays:
        if d in covered or d > today:
            continue
        r = rows.get(d)
        if not r:
            out.append(d)
        elif (r.get("day_status") or "") == "absent":
            out.append(d)
        elif (r.get("day_status") or "") == "" and not r.get("clock_in"):
            out.append(d)
    sched = set(workdays)
    for d, r in rows.items():
        if d in sched or d in covered or d > today:
            continue
        if (r.get("day_status") or "") == "absent" and int(r.get("is_workday") or 0) == 1:
            out.append(d)
    return sorted(set(out))


def _max_streak_range(days: list[str], start: str, end: str) -> tuple[int, list[str]]:
    if not days:
        return 0, []
    workdays = period_workdays(start, end)
    index = {d: i for i, d in enumerate(workdays)}
    idxs = sorted(index[d] for d in days if d in index)
    best, best_run, run, prev = 0, [], [], None
    for i in idxs:
        if prev is not None and i == prev + 1:
            run.append(workdays[i])
        else:
            run = [workdays[i]]
        if len(run) > best:
            best, best_run = len(run), list(run)
        prev = i
    return best, best_run


def _paid_leave_hours_range(employee_id: int, start: str, end: str) -> float:
    """Цалинтай чөлөөний цаг — зөвхөн тухайн үе рүү таарсан хэсэг."""
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    total = 0.0
    for lv in list_leaves(None, employee_id, status="approved"):
        if not int(lv.get("paid") or 0):
            continue
        ls = date.fromisoformat(lv["start_date"])
        le = date.fromisoformat(lv["end_date"] or lv["start_date"])
        if le < d0 or ls > d1:
            continue
        if int(lv["all_day"] or 0) == 1:
            dd, days = max(ls, d0), 0
            while dd <= min(le, d1):
                if is_workday(dd):
                    days += 1
                dd += timedelta(days=1)
            total += days * (paid_minutes_per_day(start) / 60.0)
        else:
            total += float(lv["hours"] or 0)
    return round(total, 2)


def period_payroll(period_key: str) -> dict:
    """
    Үндсэн цалингийн үе (11 → 10) — 10-нд олгоно:
      үндсэн цалин + нэмэлт цаг + цалинтай чөлөө − 3 хоног дараалсан тасралтын 10% торгууль
      − 25-нд олгосон АВАНС = 10-нд олгох дүн.
    """
    b = pay_period_bounds(period_key)
    start, end = b["start"], b["end"]
    rules = advance_rules()
    s = get_settings()
    with connect() as con:
        emps = [dict(r) for r in con.execute(
            "SELECT * FROM employees WHERE active=1 ORDER BY code").fetchall()]
        recs = [dict(r) for r in con.execute(
            "SELECT * FROM attendance WHERE work_date BETWEEN ? AND ? ORDER BY work_date",
            (start, end)).fetchall()]
    by_emp: dict[int, list[dict]] = {}
    for r in recs:
        by_emp.setdefault(r["employee_id"], []).append(r)
    adv_map = {a["employee_id"]: a for a in list_advances(period_key)}

    rows = []
    for e in emps:
        rcs = by_emp.get(e["id"], [])
        rate = float(e["daily_rate"] or 0)
        credit = sum(worked_day_credit(r) for r in rcs)
        days_worked = sum(1 for r in rcs if r.get("clock_in"))
        night_days = sum(1 for r in rcs if r.get("clock_in")
                         and (r.get("shift_type") or "day") == "night")
        role_days = {"guard": 0, "worker": 0}
        for r in rcs:
            if r.get("clock_in") and (r.get("shift_type") or "day") == "night":
                role = r.get("night_role") or e["night_role"]
                role_days["guard" if role == "guard" else "worker"] += 1
        pay_base = round(sum(float(r.get("pay_base") or 0) for r in rcs), 2)
        pay_extra = round(sum(float(r.get("pay_extra") or 0) for r in rcs), 2)
        extra_minutes = sum(int(r.get("extra_minutes") or 0) for r in rcs)
        paid_hours = _paid_leave_hours_range(e["id"], start, end)
        leave_pay = round(hourly_rate(rate) * paid_hours, 2)
        absent = _absent_days_range(e["id"], start, end)
        streak, streak_run = _max_streak_range(absent, start, end)
        thr = int(float(s["absence_penalty_days"] or 3))
        pct = float(s["absence_penalty_percent"] or 10)
        penalty = round((pay_base + pay_extra + leave_pay) * pct / 100.0, 2) if streak >= thr else 0.0
        gross = round(pay_base + pay_extra + leave_pay, 2)
        after_penalty = round(gross - penalty, 2)
        adv = adv_map.get(e["id"]) or {}
        # Анхаар: авансын эрх нь ЗӨВХӨН 11 → 24 цонхоор тодорхойлогдоно
        fd_all = advance_window_full_days(e["id"], period_key)
        adv_status = adv.get("status") or (
            "pending" if (rules["enabled"] and fd_all["full_days"] > rules["min_full_days"]) else "none")
        adv_amount = float(adv.get("amount") or 0) if adv else 0.0
        deduct = adv_amount if adv_status == "paid" else 0.0
        payout_raw = round(after_penalty - deduct, 2)
        over = payout_raw < 0
        over_amount = round(-payout_raw, 2) if over else 0.0
        payout = 0.0 if over else payout_raw           # цалин сөрөг олгогдохгүй
        if over:
            pay_status, color = "Аванс цалингаас хэтэрсэн", "darkred"
        elif streak >= thr:
            pay_status, color = "Шийтгэл −10%", "red"
        elif absent:
            pay_status, color = "Тасалсан хоногтой", "orange"
        elif days_worked == 0 and paid_hours:
            pay_status, color = "Чөлөөтэй", "blue"
        elif days_worked == 0:
            pay_status, color = "Бүртгэлгүй", "grey"
        else:
            pay_status, color = "Хэвийн", "green"
        site = employee_site(e) or {}
        rows.append({
            "employee_id": e["id"], "code": e["code"], "full_name": e["full_name"],
            "position": e["position"] or "", "department": e["department"] or "",
            "site_name": site.get("name") or get_setting("geofence_name"),
            "site_id": e["site_id"], "night_role": e["night_role"] or "worker",
            "days_worked": days_worked, "day_credit": round(credit, 3),
            "night_days": night_days, "night_guard_days": role_days["guard"],
            "night_worker_days": role_days["worker"], "daily_rate": rate,
            "pay_base": pay_base, "pay_extra": pay_extra,
            "extra_hours": round(extra_minutes / 60.0, 2),
            "leave_pay": leave_pay, "paid_leave_hours": paid_hours,
            "absent_days": len(absent), "absent_list": absent,
            "absent_streak": streak, "absent_streak_run": streak_run,
            "penalty_percent": pct if penalty else 0, "penalty": penalty,
            "gross": gross, "after_penalty": after_penalty,
            "advance_amount": adv_amount, "advance_status": adv_status,
            "advance_status_label": ADVANCE_STATUS_LABEL.get(adv_status, "—"),
            "advance_color": ADVANCE_STATUS_COLOR.get(adv_status, "gray"),
            "advance_deduct": round(deduct, 2),
            "advance_paid_on": adv.get("paid_on"),
            "total": payout,                              # 10-нд олгох дүн
            "payout_raw": payout_raw,
            "over_advance": bool(over),
            "over_amount": over_amount,                   # хэтэрсэн авансын үлдэгдэл
            "pay_status": pay_status, "color": color,
        })
    totals = {
        "employees": len(rows),
        "days_worked": sum(r["days_worked"] for r in rows),
        "day_credit": round(sum(r["day_credit"] for r in rows), 2),
        "night_days": sum(r["night_days"] for r in rows),
        "extra_hours": round(sum(r["extra_hours"] for r in rows), 2),
        "pay_base": round(sum(r["pay_base"] for r in rows), 2),
        "pay_extra": round(sum(r["pay_extra"] for r in rows), 2),
        "leave_pay": round(sum(r["leave_pay"] for r in rows), 2),
        "penalty": round(sum(r["penalty"] for r in rows), 2),
        "gross": round(sum(r["gross"] for r in rows), 2),
        "advance_total": round(sum(r["advance_deduct"] for r in rows), 2),
        "advance_paid_employees": sum(1 for r in rows if r["advance_deduct"] > 0),
        "total": round(sum(r["total"] for r in rows), 2),
        "penalized_employees": sum(1 for r in rows if r["penalty"]),
        "over_advance_employees": sum(1 for r in rows if r["over_advance"]),
        "over_amount": round(sum(r["over_amount"] for r in rows), 2),
    }
    return {
        "period": period_key, "period_label": b["label"],
        "start": start, "end": end, "payout_date": b["payout_date"],
        "payout_label": b["payout_label"], "advance_label": b["advance_label"],
        "advance_window": b["advance_window"], "advance_pay_date": b["advance_pay_date"],
        "currency": get_setting("currency"),
        "generated_at": now_local().strftime("%Y-%m-%d %H:%M:%S"),
        "company_name": get_setting("company_name"),
        "rules": {**rules,
                  "night_start": get_setting("night_start"),
                  "night_end": get_setting("night_end"),
                  "guard_percent": float(get_setting("guard_percent")),
                  "worker_percent": float(get_setting("worker_percent")),
                  "absence_penalty_days": int(float(get_setting("absence_penalty_days"))),
                  "absence_penalty_percent": float(get_setting("absence_penalty_percent"))},
        "rows": rows, "totals": totals,
    }


def pay_cycle(employee_id: int, period_key: str | None = None) -> dict:
    """Ажилтны цалингийн хуанли: аванс (25) + үндсэн цалин (10) — зөвхөн өөрийн мэдээлэл."""
    key = period_key or period_key_for()
    b = pay_period_bounds(key)
    rules = advance_rules()
    fd = advance_window_full_days(employee_id, key)
    rec = get_advance(employee_id, key)
    eligible = rules["enabled"] and fd["full_days"] > rules["min_full_days"]
    pr = period_payroll(key)
    row = next((r for r in pr["rows"] if r["employee_id"] == employee_id), {})
    adv_status = rec["status"] if rec else ("pending" if eligible else "none")
    if adv_status == "paid":
        adv_msg = "Аванс олгогдсон — үндсэн цалингаас хасагдана."
    elif eligible:
        adv_msg = f"Аванс авах эрхтэй — {b['advance_pay_date']}-нд олгоно."
    else:
        adv_msg = (f"Энэ үед аванс авахгүй (бүтэн өдөр {fd['full_days']} ≤ "
                   f"{rules['min_full_days']}). Цалин бүхэлдээ {b['payout_date']}-нд олгоно.")
    return {
        "period": key, "period_label": b["label"], "start": b["start"], "end": b["end"],
        "payout_date": b["payout_date"], "advance_pay_date": b["advance_pay_date"],
        "advance_window": b["advance_window"], "advance_label": b["advance_label"],
        "rules": rules,
        "advance": {
            "eligible": bool(eligible), "full_days": fd["full_days"],
            "partial_days": fd["partial_days"], "min_full_days": rules["min_full_days"],
            "amount": float(rec["amount"]) if rec else (rules["amount"] if eligible else 0.0),
            "status": adv_status, "status_label": ADVANCE_STATUS_LABEL.get(adv_status, "—"),
            "status_color": ADVANCE_STATUS_COLOR.get(adv_status, "gray"),
            "paid_on": rec["paid_on"] if rec else None, "message": adv_msg,
        },
        "payout": {
            "date": b["payout_date"], "gross": row.get("gross", 0.0),
            "penalty": row.get("penalty", 0.0), "advance_deduct": row.get("advance_deduct", 0.0),
            "total": row.get("total", 0.0), "over_advance": row.get("over_advance", False),
            "over_amount": row.get("over_amount", 0.0),
            "days_worked": row.get("days_worked", 0),
            "day_credit": row.get("day_credit", 0.0),
            "message": f"{b['payout_date']}-нд олгох үндсэн цалин.",
        },
    }


def pay_cycle_table(period_key: str | None = None) -> dict:
    """Хоёр төлбөрийн нэгдсэн хүснэгт (админ): 25-ны аванс + 10-ны үндсэн цалин."""
    key = period_key or period_key_for()
    b = pay_period_bounds(key)
    pr = period_payroll(key)
    adv = advance_candidates(key)
    arows = {r["employee_id"]: r for r in adv["rows"]}
    rows = []
    for r in pr["rows"]:
        a = arows.get(r["employee_id"], {})
        rows.append({
            "employee_id": r["employee_id"], "code": r["code"], "full_name": r["full_name"],
            "position": r["position"], "department": r["department"], "site_name": r["site_name"],
            "daily_rate": r["daily_rate"], "days_worked": r["days_worked"],
            "day_credit": r["day_credit"], "full_days": a.get("full_days", 0),
            "partial_days": a.get("partial_days", 0),
            "eligible": bool(a.get("eligible")),
            "advance_status": a.get("status", "none"),
            "advance_status_label": a.get("status_label", ADVANCE_STATUS_LABEL.get("none", "—")),
            "advance_color": a.get("status_color", "gray"),
            "advance_amount": float(a.get("amount") or 0.0),
            "window_earnings": a.get("window_earnings", 0.0),
            "capped": bool(a.get("capped")),
            "reason": a.get("reason", ""),
            "penalty": r["penalty"], "penalty_percent": r["penalty_percent"],
            "gross": r["gross"], "advance_deduct": r["advance_deduct"],
            "total": r["total"], "over_advance": r["over_advance"],
            "over_amount": r["over_amount"], "payout_raw": r["payout_raw"],
            "paid_on": r["advance_paid_on"], "color": r["color"], "pay_status": r["pay_status"],
        })
    return {
        "period": key, "label": b["label"], "start": b["start"], "end": b["end"],
        "payout_date": b["payout_date"], "payout_label": b["payout_label"],
        "advance_pay_date": b["advance_pay_date"], "advance_label": b["advance_label"],
        "advance_window": b["advance_window"],
        "company_name": get_setting("company_name"), "currency": get_setting("currency"),
        "generated_at": now_local().strftime("%Y-%m-%d %H:%M"),
        "rules": adv["rules"], "rows": rows,
        "totals": {**pr["totals"],
                   "advance_eligible": adv["totals"]["eligible"],
                   "advance_pending": adv["totals"]["pending_total"]},
    }


# --------------------------------------------------------------------------
# Сарын тайлан (monthly payroll report)
# --------------------------------------------------------------------------
def month_report(month: str) -> dict:
    """month = 'YYYY-MM'. Ажилтан тус бүрийн сарын нэгдсэн тайлан."""
    y, m = int(month[:4]), int(month[5:7])
    first = date(y, m, 1)
    nxt = date(y + (m == 12), (m % 12) + 1, 1)
    today = date.fromisoformat(today_str())
    last_day = min(nxt - timedelta(days=1), today)

    # тухайн сард ажиллах ёстой өдрүүд (хүртэл нь)
    expected = []
    d = first
    while d <= last_day:
        if is_workday(d):
            expected.append(d.isoformat())
        d += timedelta(days=1)

    with connect() as con:
        emps = con.execute("SELECT * FROM employees WHERE active=1 ORDER BY code").fetchall()
        rows = con.execute("SELECT * FROM attendance WHERE work_date LIKE ? ORDER BY work_date",
                           (f"{month}-%",)).fetchall()

    by_emp: dict[int, list[dict]] = {}
    for r in rows:
        by_emp.setdefault(r["employee_id"], []).append(dict(r))

    result = []
    for e in emps:
        recs = by_emp.get(e["id"], [])
        agg = aggregate([apply_flags(r) for r in recs])
        pl = payroll_extra(dict(e), recs, month)
        present_dates = {r["work_date"] for r in recs if r.get("clock_in")}
        absent_days = len([d for d in expected if d not in present_dates])
        worked = agg["worked_minutes"]
        result.append({
            "employee_id": e["id"],
            "code": e["code"],
            "full_name": e["full_name"],                       # Ажилтны нэр
            "department": e["department"] or "",
            "position": e["position"] or "",
            "expected_days": len(expected),                    # Ажиллах өдөр
            "present_days": agg["present_days"],               # Ирсэн өдөр
            "absent_days": absent_days,                        # Тасалсан өдөр
            "worked_minutes": worked,                          # Нийт ажилласан цаг
            "worked_hours": round(worked / 60.0, 2),
            "worked_hm": fmt_hhmm(worked),
            "late_days": agg["late_days"],                     # Нийт хоцорсон тоо
            "late_minutes": agg["late_minutes"],
            "early_days": agg["early_days"],                   # Нийт эрт явсан тоо
            "early_minutes": agg["early_minutes"],
            "deduct_minutes": agg["deduct_minutes"],           # Хасагдсан нийт минут
            "payable_minutes": agg["payable_minutes"],
            "payable_hours": round(agg["payable_minutes"] / 60.0, 2),
            "payable_hm": fmt_hhmm(agg["payable_minutes"]),
            # ---- Цалин (v2) ----
            "daily_rate": pl["daily_rate"],
            "day_credit": pl["day_credit"],
            "night_days": pl["night_days"],
            "extra_hours": pl["extra_hours"],
            "pay_base": pl["pay_base"],
            "pay_extra": pl["pay_extra"],
            "leave_pay": pl["leave_pay"],
            "paid_leave_hours": pl["paid_leave_hours"],
            "absent_streak": pl["absent_streak"],
            "penalty": pl["penalty"],
            "penalty_percent": pl["penalty_percent"],
            "pay_total": pl["total"],
            "pay_status": pl["pay_status"],
            "color": pl["color"],
        })

    totals = {
        "employees": len(result),
        "worked_minutes": sum(r["worked_minutes"] for r in result),
        "worked_hm": fmt_hhmm(sum(r["worked_minutes"] for r in result)),
        "worked_hours": round(sum(r["worked_minutes"] for r in result) / 60.0, 2),
        "late_days": sum(r["late_days"] for r in result),
        "late_minutes": sum(r["late_minutes"] for r in result),
        "early_days": sum(r["early_days"] for r in result),
        "early_minutes": sum(r["early_minutes"] for r in result),
        "deduct_minutes": sum(r["deduct_minutes"] for r in result),
        "payable_minutes": sum(r["payable_minutes"] for r in result),
        "payable_hm": fmt_hhmm(sum(r["payable_minutes"] for r in result)),
        "absent_days": sum(r["absent_days"] for r in result),
        "pay_base": round(sum(r["pay_base"] for r in result), 2),
        "pay_extra": round(sum(r["pay_extra"] for r in result), 2),
        "leave_pay": round(sum(r["leave_pay"] for r in result), 2),
        "penalty": round(sum(r["penalty"] for r in result), 2),
        "pay_total": round(sum(r["pay_total"] for r in result), 2),
        "night_days": sum(r["night_days"] for r in result),
        "extra_hours": round(sum(r["extra_hours"] for r in result), 2),
    }
    return {
        "month": month,
        "month_label": f"{y} оны {MONTH_MN[m]}",
        "period": f"{first.isoformat()} — {last_day.isoformat()}",
        "workdays_in_month": len(expected),
        "generated_at": now_local().strftime("%Y-%m-%d %H:%M:%S"),
        "company_name": get_setting("company_name"),
        "currency": get_setting("currency"),
        "schedule": {"start": get_setting("schedule_start"), "end": get_setting("schedule_end")},
        "rows": result,
        "totals": totals,
    }


# --------------------------------------------------------------------------
# Сесс / API түлхүүр / аудит
# --------------------------------------------------------------------------
def create_session(role: str, employee_id: int | None, label: str = "") -> str:
    token = secrets.token_urlsafe(24)
    now = now_local()
    with _lock, connect() as con:
        con.execute("INSERT INTO sessions(token, role, employee_id, label, created_at, expires_at)"
                    " VALUES(?,?,?,?,?,?)",
                    (token, role, employee_id, label, now.strftime("%Y-%m-%d %H:%M:%S"),
                     (now + timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")))
        con.commit()
    return token


def resolve_token(token: str) -> dict | None:
    if not token:
        return None
    with connect() as con:
        r = con.execute("SELECT * FROM sessions WHERE token=?", (token,)).fetchone()
    if not r:
        return None
    if parse_dt(r["expires_at"]) < now_local():
        return None
    return {"role": r["role"], "employee_id": r["employee_id"], "label": r["label"]}


def resolve_api_key(key: str) -> dict | None:
    if not key:
        return None
    with connect() as con:
        r = con.execute("SELECT * FROM api_keys WHERE key=? AND active=1", (key,)).fetchone()
        if r:
            con.execute("UPDATE api_keys SET last_used=? WHERE key=?",
                        (now_local().strftime("%Y-%m-%d %H:%M:%S"), key))
            con.commit()
    return {"role": r["role"], "name": r["name"], "employee_id": None} if r else None


def list_api_keys() -> list[dict]:
    with connect() as con:
        return [dict(r) for r in con.execute("SELECT * FROM api_keys ORDER BY created_at DESC")]


def create_api_key(name: str, role: str = "agent") -> dict:
    key = "att_" + secrets.token_hex(16)
    with _lock, connect() as con:
        con.execute("INSERT INTO api_keys(key, name, role, active, created_at) VALUES(?,?,?,1,?)",
                    (key, name or "AI Agent", role, now_local().strftime("%Y-%m-%d %H:%M:%S")))
        con.commit()
    audit("admin", "api_key_create", f"{name} ({role})")
    return {"key": key, "name": name, "role": role}


def revoke_api_key(key: str) -> None:
    with _lock, connect() as con:
        con.execute("UPDATE api_keys SET active=0 WHERE key=?", (key,))
        con.commit()
    audit("admin", "api_key_revoke", key[:12] + "…")


def audit(actor: str, action: str, detail: str = "") -> None:
    with _lock, connect() as con:
        con.execute("INSERT INTO audit_log(ts, actor, action, detail) VALUES(?,?,?,?)",
                    (now_local().strftime("%Y-%m-%d %H:%M:%S"), actor, action, detail))
        con.commit()


def recent_audit(limit: int = 60) -> list[dict]:
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]


# --------------------------------------------------------------------------
# Демо өгөгдөл (seed)
# --------------------------------------------------------------------------
SEED_GEOFENCE = {
    # v4.3 демо: ажилтан бүр өөрийн гео хаалтын горимтой байж болно
    "EMP011": {"geofence_mode": "off"},                      # жолооч — нэг цэгт баригдахгүй
    "EMP007": {"geofence_mode": "custom", "geo_lat": 47.9128, "geo_lng": 106.9531,
               "geo_radius_m": 500.0},                       # шилжсэн нэмэлт талбай
}

SEED_SITES = [
    # (нэр, хаяг, lat, lng, радиус)
    ("Төв оффис — Сүхбаатарын талбай", "Сүхбаатар дүүрэг, 1-р хороо", 47.9184, 106.9177, 300),
    ("Нисэх онгоцны буудал — шинэ терминал", "Хан-Уул дүүрэг, 12-р хороо", 47.6431, 106.8197, 400),
    ("Зайсан — орон сууцны цогцолбор", "Хан-Уул дүүрэг, 11-р хороо", 47.8859, 106.9207, 250),
    ("Шинэ Яармаг — агуулахын талбай", "Сонгинохайрхан дүүрэг", 47.9793, 106.8556, 500),
]

# (код, нэр, хэлтэс, албан тушаал, өдрийн цалин ₮, шөнийн үүрэг, талбайн дугаар)
SEED_EMPLOYEES = [
    ("EMP001", "Батбаяр Дорж",         "Бригад №1",  "Бригадын ахлагч",      150000, "worker", 2),
    ("EMP002", "Сарангэрэл Бат-Эрдэнэ", "Оффис",      "Нягтлан бодогч",       120000, "worker", 1),
    ("EMP003", "Төмөрбат Энхбаатар",    "Бригад №1",  "Өрлөгчин",             110000, "worker", 2),
    ("EMP004", "Номин-Эрдэнэ Гантулга", "Оффис",      "ХАБЭА мэргэжилтэн",    115000, "worker", 1),
    ("EMP005", "Ганбаатар Лувсан",      "Бригад №2",  "Төмөр бетончин",       115000, "worker", 3),
    ("EMP006", "Оюунчимэг Дашдондог",   "Бригад №2",  "Буддагчин",             95000, "worker", 3),
    ("EMP007", "Эрдэнэбат Цэрэн",       "Бригад №1",  "Гагнуурчин",           130000, "worker", 2),
    ("EMP008", "Хонгорзул Мөнхбат",     "Бригад №2",  "Мужаан",               105000, "worker", 3),
    ("EMP009", "Мөнх-Эрдэнэ Баяр",      "Хамгаалалт", "Шөнийн хамгаалагч",     70000, "guard",  4),
    ("EMP010", "Ануужин Сүхбат",        "Хамгаалалт", "Шөнийн хамгаалагч",     70000, "guard",  4),
    ("EMP011", "Дөлгөөн Алтанхуяг",     "Тээвэр",     "Жолооч",                90000, "worker", 4),
    ("EMP012", "Тэмүүлэн Жаргалсайхан", "Бригад №2",  "Туслах ажилчин",        60000, "worker", 3),
]


def _seed(con: sqlite3.Connection) -> None:
    """Барилгын бригадын демо өгөгдөл: талбай, ажилтан, 8 долоо хоногийн ирц."""
    now = now_local()
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")
    site_ids = []
    for name, addr, lat, lng, radius in SEED_SITES:
        cur = con.execute(
            "INSERT INTO sites(name, address, lat, lng, radius_m, active, created_at)"
            " VALUES(?,?,?,?,?,1,?)", (name, addr, lat, lng, radius, stamp))
        site_ids.append(cur.lastrowid)
    for code, name, dept, pos, rate, role, site_no in SEED_EMPLOYEES:
        sid = site_ids[site_no - 1] if site_no and site_no <= len(site_ids) else None
        con.execute(
            "INSERT INTO employees(code, full_name, department, position, pin, active, "
            "daily_rate, night_role, site_id, created_at) VALUES(?,?,?,?,?,1,?,?,?,?)",
            (code, name, dept, pos, "1234", rate, role, sid, stamp))
    for code, g in SEED_GEOFENCE.items():                    # v4.3
        con.execute("UPDATE employees SET geofence_mode=?, geo_lat=?, geo_lng=?, geo_radius_m=?"
                    " WHERE code=?",
                    (g.get("geofence_mode", "site"), g.get("geo_lat"), g.get("geo_lng"),
                     g.get("geo_radius_m"), code))
    con.execute("INSERT OR IGNORE INTO api_keys(key, name, role, active, created_at)"
                " VALUES('att_demo_agent_key_2026','Демо AI Төлөгч','agent',1,?)", (stamp,))

    # Сүүлийн 8 долоо хоногийн ирц + төлөвлөсөн демо тохиолдлууд
    _seed_demo_data(con)


def _seed_demo_data(con: sqlite3.Connection) -> None:
    """Талбай/ажилтан аль хэдийн байгаа үед ирцийн түүхийг (8 долоо хоног) үүсгэнэ."""
    now = now_local()
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")
    emp_rows = [dict(r) for r in con.execute(
        "SELECT * FROM employees ORDER BY id").fetchall()]
    sites = {r["id"]: dict(r) for r in con.execute("SELECT * FROM sites").fetchall()}
    rng = random.Random(20261004)
    s = dict(DEFAULT_SETTINGS)
    for row in con.execute("SELECT key, value FROM settings").fetchall():
        s[row["key"]] = row["value"]
    workdays = {int(x) for x in s["workdays"].split(",")}
    start_t = parse_hhmm(s["schedule_start"])

    today = now.date()
    begin = today - timedelta(days=56)
    night_pour = {"2026-09-18": "EMP005", "2026-10-02": "EMP005"}   # шөнийн цутгалт (ажилчин, 100%)
    d = begin
    while d <= today:
        if d.isoweekday() not in workdays or d == today:
            d += timedelta(days=1)
            continue
        for e in emp_rows:
            eid, code = e["id"], e["code"]
            site = sites.get(e["site_id"]) or {}
            lat = float(site.get("lat") or s["geofence_lat"])
            lng = float(site.get("lng") or s["geofence_lng"])
            is_guard = (e["night_role"] or "worker") == "guard"
            rec = {
                "id": None, "employee_id": eid, "work_date": d.isoformat(),
                "in_lat": round(lat + rng.uniform(-0.0012, 0.0012), 6),
                "in_lng": round(lng + rng.uniform(-0.0012, 0.0012), 6),
                "in_distance_m": round(rng.uniform(5, 220), 1), "in_accuracy_m": 12.0,
                "out_lat": round(lat + rng.uniform(-0.0012, 0.0012), 6),
                "out_lng": round(lng + rng.uniform(-0.0012, 0.0012), 6),
                "out_distance_m": round(rng.uniform(5, 220), 1), "out_accuracy_m": 12.0,
                "note": "", "edited": 0,
            }
            # ---- Шөнийн ээлж: хамгаалагчид 19:00–03:00 ----
            if is_guard and rng.random() < 0.78:
                cin = datetime.combine(d, parse_hhmm(s["night_start"])) + timedelta(
                    minutes=rng.choice([-10, -8, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3,
                                        5, 8, 12, 18, 30]),
                    seconds=rng.randint(0, 59))
                cout = datetime.combine(d + timedelta(days=1), parse_hhmm(s["night_end"])) + timedelta(
                    minutes=rng.choice([-32, -18, -9, -4, 0, 0, 1, 3, 6, 11, 18, 29]),
                    seconds=rng.randint(0, 59))
                rec.update({"clock_in": cin.strftime("%Y-%m-%d %H:%M:%S"),
                            "clock_out": cout.strftime("%Y-%m-%d %H:%M:%S")})
            # ---- Шөнийн цутгалт (ажилчин, 100%) ----
            elif night_pour.get(d.isoformat()) == code:
                cin = datetime.combine(d, time(19, 2)) + timedelta(minutes=rng.randint(0, 12))
                cout = datetime.combine(d + timedelta(days=1), time(3, 0)) + timedelta(
                    minutes=rng.choice([-8, -3, 0, 4, 12]))
                rec.update({"clock_in": cin.strftime("%Y-%m-%d %H:%M:%S"),
                            "clock_out": cout.strftime("%Y-%m-%d %H:%M:%S"),
                            "note": "Шөнийн цутгалт"})
            # ---- Өдрийн ээлж ----
            else:
                if rng.random() < 0.03:          # тасалсан өдөр
                    continue
                # 82% — цагтаа (хөнгөлөлтийн дотор), 18% — хоцорсон
                r = rng.random()
                if r < 0.55:
                    in_off = rng.choice([-14, -11, -9, -7, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3])
                elif r < 0.85:
                    in_off = rng.choice([4, 5, 6, 7, 8, 9, 10])          # хөнгөлөлтийн дотор
                elif r < 0.95:
                    in_off = rng.choice([12, 15, 18, 22, 27, 33, 38])    # бага зэрэг хоцорсон
                else:
                    in_off = rng.choice([45, 52, 61, 75, 95])            # их хоцорсон
                cin = datetime.combine(d, start_t) + timedelta(minutes=in_off,
                                                               seconds=rng.randint(0, 59))
                # 90% — цагтаа/дараа нь, 10% — эрт явсан
                r2 = rng.random()
                if r2 < 0.62:
                    out_off = rng.choice([0, 2, 4, 6, 9, 12, 16, 21, 27, 35, 44])   # цагтаа/хойш
                elif r2 < 0.92:
                    out_off = rng.choice([0, 0, 1, 2, 3])                           # цагтаа
                elif r2 < 0.97:
                    out_off = rng.choice([-14, -19, -26, -34])                      # бага зэрэг эрт
                else:
                    out_off = rng.choice([-58, -72, -88])                           # их эрт
                cout = datetime.combine(d, parse_hhmm(s["schedule_end"])) + timedelta(
                    minutes=out_off, seconds=rng.randint(0, 59))
                rec.update({"clock_in": cin.strftime("%Y-%m-%d %H:%M:%S"),
                            "clock_out": cout.strftime("%Y-%m-%d %H:%M:%S")})
            rec2 = recalc(rec, d.isoformat(), force_workday=True, employee=e)
            _save_record(rec2, con)
        d += timedelta(days=1)

    # ---- Төлөвлөсөн демо тохиолдлууд ----
    def _lv(code, start, end, all_day, st=None, et=None, note="", paid=0,
            status="approved", by="admin"):
        """v3.1: зөвхөн «чөлөө» төрөл; цалинтай эсэх нь paid=0/1."""
        eid = next(e["id"] for e in emp_rows if e["code"] == code)
        dd = date.fromisoformat(start)
        ed = date.fromisoformat(end or start)
        hours = 0.0
        if all_day:
            cur = dd
            while cur <= ed:
                if is_workday(cur):
                    hours += paid_minutes_per_day(start) / 60.0
                cur += timedelta(days=1)
        else:
            a, b = parse_hhmm(st), parse_hhmm(et)
            hours = round((((b.hour * 60 + b.minute) - (a.hour * 60 + a.minute)) % 1440) / 60.0, 2)
        con.execute(
            "INSERT INTO leaves(employee_id, kind, start_date, end_date, all_day, start_time, "
            "end_time, hours, approved, status, paid, note, requested_by, created_by, created_at, "
            "decided_at, decided_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (eid, "чөлөө", start, end, 1 if all_day else 0,
             None if all_day else st, None if all_day else et, hours,
             1 if status == "approved" else 0, status, 1 if paid else 0, note,
             by, by, stamp, None if status == "pending" else stamp,
             None if status == "pending" else by))

    # 10-р сарын демо тохиолдлууд (дараалан 3 хоног тасарсан → 10% торгууль)
    streak_days = ["2026-09-28", "2026-09-29", "2026-09-30"]
    eid6 = next(e["id"] for e in emp_rows if e["code"] == "EMP006")
    con.execute("DELETE FROM attendance WHERE employee_id=? AND work_date IN (?,?,?)",
                (eid6, *streak_days))
    # 10-р сард: EMP006 нэг хоног тасарсан, EMP012 хоёр хоног (3-т хүрэхэд торгууль)
    eid12 = next(e["id"] for e in emp_rows if e["code"] == "EMP012")
    con.execute("DELETE FROM attendance WHERE employee_id=? AND work_date='2026-10-03'", (eid6,))
    con.execute("DELETE FROM attendance WHERE employee_id=? AND work_date IN ('2026-10-02','2026-10-03')",
                (eid12,))
    # --- v3.1: нэг төрөл «чөлөө», цалинтай эсэхийг paid-аар ------------------
    _lv("EMP004", "2026-09-28", "2026-09-30", True, note="Жилийн ээлжийн чөлөө", paid=1)
    _lv("EMP002", "2026-10-02", None, False, "15:00", "18:00", note="Хувийн ажил", paid=1)
    _lv("EMP008", "2026-10-02", None, False, "10:00", "14:00", note="Эмнэлэгт үзүүлэх",
        paid=0, status="approved")
    _lv("EMP010", "2026-09-25", None, False, "19:00", "23:00", note="Гэр бүлийн ажил", paid=0)
    _lv("EMP011", "2026-10-03", None, True, note="Хувийн хэрэг", paid=1)
    # ХҮСЭЛТИЙН урсгал: ажилтны илгээсэн хүлээгдэж буй хүсэлт + татгалзсан түүх
    _lv("EMP007", "2026-10-06", "2026-10-07", True, note="Гэр бүлийн ажил",
        paid=0, status="pending", by="employee")
    _lv("EMP009", "2026-10-05", None, False, "14:00", "18:00", note="Эмнэлэгт үзүүлэх",
        paid=0, status="rejected", by="employee")
    if con.execute("INSERT INTO audit_log(ts, actor, action, detail) "
                   "VALUES(?,?,?,?)", (stamp, "system", "seed",
                   "Барилгын бригадын демо өгөгдөл үүсгэв (талбай, цалин, ээлж, чөлөө)")).rowcount:
        pass


def _seed_today(con, emp_ids, start_t, today: date, now: datetime) -> None:
    """Өнөөдрийн байдлыг бодит цагтай уялдуулан үүсгэнэ."""
    rng = random.Random(int(today.strftime("%Y%m%d")))
    schedule_start = datetime.combine(today, start_t)
    s = get_settings()
    schedule_end = datetime.combine(today, parse_hhmm(s["schedule_end"]))
    day = today.isoformat()

    def add(eid, cin, cout=None):
        rec = recalc({
            "id": None, "employee_id": eid, "work_date": day,
            "clock_in": cin.strftime("%Y-%m-%d %H:%M:%S") if cin else None,
            "clock_out": cout.strftime("%Y-%m-%d %H:%M:%S") if cout else None,
            "in_lat": 47.9184, "in_lng": 106.9177, "in_distance_m": round(rng.uniform(4, 120), 1),
            "in_accuracy_m": 10.0, "out_lat": 47.9184 if cout else None,
            "out_lng": 106.9177 if cout else None,
            "out_distance_m": round(rng.uniform(4, 120), 1) if cout else None,
            "out_accuracy_m": 10.0 if cout else None, "note": "", "edited": 0,
        }, day)
        _save_record(rec, con)

    if now < schedule_start:                       # ажил эхлэхээс өмнө
        return
    past_end = now >= schedule_end
    for i, eid in enumerate(emp_ids):
        offset = [(-9, 4), (2, 6), (-5, -3), (26, 8), (-3, 30), (-14, -12),
                  (6, 2), (-1, -20), (17, 5), (-7, 11), (0, 9), (-22, 3)][i % 12]
        cin = schedule_start + timedelta(minutes=offset[0], seconds=rng.randint(0, 59))
        if cin > now:
            continue
        if past_end or i % 3 == 0:
            cout = min(schedule_end + timedelta(minutes=offset[1]), now)
            if cout <= cin:
                cout = None
            add(eid, cin, cout)
        elif i in (1, 4, 7, 10):                    # одоо ажиллаж байгаа
            add(eid, cin, None)
        else:
            continue                                # ирээгүй (absent)


if __name__ == "__main__":
    init_db()
    print("DB бэлэн:", DB_PATH)
    print("Ажилтны тоо:", len(list_employees()))
    print("Ажлын өдөр мөн үү (өнөөдөр):", is_workday(today_str()))
