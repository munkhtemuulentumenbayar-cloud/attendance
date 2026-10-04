#!/usr/bin/env python3
"""
Цаг бүртгэл ба ирцийн систем — HTTP сервер
==========================================
Ажиллуулах:  python3 app.py            (default: 0.0.0.0:8000)
             PORT=8080 python3 app.py

Бүх UI монгол хэл дээр. Гадаад сан шаардахгүй (stdlib only).
"""
from __future__ import annotations

import csv
import io
import threading
import time
import json
import os
import re
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import core
import reports
from core import (LEAVE_KINDS, DAY_STATUS_LABEL, LEAVE_STATUS_LABEL, add_leave, approve_segment,
                  cancel_leave, create_site, decide_leave, delete_leave, delete_site,
                  pending_leave_requests, request_leave, parse_geo_text,
                  extra_start, extra_stop, list_notifications, list_segments, live_pay,
                  mark_notifications_read, missed_clockouts, notify, paid_minutes_per_day,
                  photo_path, scheduler_tick, segment_minutes, unread_count,
                  effective_geo, employee_pay, employee_site, fmt_money,
                  leave_summary, list_leaves, list_sites, monthly_payroll,
                  night_role_label, set_extra_hours, update_site,
                  apply_flags, audit, check_geofence, clock_in, clock_out,
                  demo_clear_today, demo_seed_today, recalc_all,
                  create_api_key, create_employee, create_session, daily_records,
                  employee_day_view, employee_history, get_employee, get_record,
                  get_setting, get_settings, init_db, list_api_keys, list_employees,
                  live_board, manual_record, month_report, now_local, recent_audit,
                  resolve_api_key, resolve_token, revoke_api_key, set_settings,
                  make_backup_zip,
                  set_employee_geofence, GEOFENCE_MODES, GEOFENCE_MODE_LABEL,
                  advance_candidates, advance_rules, cancel_advance, get_advance,
                  pay_cycle, pay_cycle_table, pay_period_bounds, period_payroll, period_key_for,
                  recent_periods, reset_advance, set_advance, window_earnings,
                  today_str, update_employee, verify_pin)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
VERSION = "4.5.0"

MIME = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8", ".json": "application/json; charset=utf-8",
        ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
        ".webmanifest": "application/manifest+json", ".txt": "text/plain; charset=utf-8"}


class ApiError(Exception):
    def __init__(self, status: int, message: str, extra: dict | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.extra = extra or {}


# --------------------------------------------------------------------------
# Identity / эрх шалгах
# --------------------------------------------------------------------------
def identity(handler: "Handler") -> dict | None:
    """Бүртгэлээс хэрэглэгчийн эрхийг тодорхойлно."""
    headers = {k.lower(): v for k, v in handler.headers.items()}
    key = headers.get("x-api-key") or ""
    if key:
        ident = resolve_api_key(key)
        if ident:
            ident["kind"] = "api_key"
            return ident
    # X-Auth-Token header (зарим proxy Authorization-ыг устгадаг)
    xt = headers.get("x-auth-token", "")
    if xt:
        ident = resolve_token(xt)
        if ident:
            ident["kind"] = "session"
            return ident
    # ?token=... (preview proxy-д хамгийн найдвартай — URL-д явдаг)
    try:
        qtok = (handler.query.get("token") or [""])[0]
    except Exception:
        qtok = ""
    if qtok:
        ident = resolve_token(qtok)
        if ident:
            ident["kind"] = "session"
            return ident
    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token.startswith("att_"):
            ident = resolve_api_key(token)
            if ident:
                ident["kind"] = "api_key"
                return ident
        ident = resolve_token(token)
        if ident:
            ident["kind"] = "session"
            return ident
    # Cookie
    cookie = headers.get("cookie", "")
    m = re.search(r"att_session=([^;]+)", cookie)
    if m:
        ident = resolve_token(unquote(m.group(1)))
        if ident:
            ident["kind"] = "session"
            return ident
    # X-Emp-Code + X-Emp-Pin (AI агент ажилтны өмнөөс)
    code = headers.get("x-employee-code")
    pin = headers.get("x-employee-pin")
    if code and pin:
        emp = verify_pin(code, pin)
        if emp:
            return {"role": "employee", "employee_id": emp["id"], "label": emp["full_name"],
                    "kind": "emp_headers", "employee": emp}
    return None


def require(handler: "Handler", role: str | None = None) -> dict:
    ident = identity(handler)
    if not ident:
        raise ApiError(401, "Нэвтрэх шаардлагатай. Та эхлээд нэвтэрнэ үү.")
    if role == "admin" and ident["role"] not in ("admin",):
        raise ApiError(403, "Танд энэ үйлдлийг хийх эрх байхгүй.")
    if role == "employee" and ident["role"] not in ("employee", "admin"):
        raise ApiError(403, "Танд энэ үйлдлийг хийх эрх байхгүй.")
    if role in ("admin_or_agent",) and ident["role"] not in ("admin", "agent"):
        raise ApiError(403, "Танд энэ үйлдлийг хийх эрх байхгүй.")
    return ident


def target_employee(handler: "Handler", ident: dict, body: dict) -> dict:
    """Ажилтныг тодорхойлох: сесс → өөрөө, агент/админ → кодоор."""
    if ident.get("employee_id"):
        emp = get_employee(ident["employee_id"])
        if not emp:
            raise ApiError(404, "Ажилтан олдсонгүй.")
        return emp
    code = (body or {}).get("employee_code") or handler.query.get("employee_code", [""])[0]
    if not code:
        raise ApiError(400, "employee_code талбар шаардлагатай.")
    emp = core.get_employee_by_code(code)
    if not emp:
        raise ApiError(404, f"«{code}» кодтой ажилтан олдсонгүй.")
    return emp


# --------------------------------------------------------------------------
# Route бүртгэл
# --------------------------------------------------------------------------
ROUTES: list[tuple[str, re.Pattern, callable]] = []


def route(method: str, pattern: str):
    """{нэр} хэлбэрийн параметрийг regex бүлэг болгон хөрвүүлнэ."""
    def deco(fn):
        regex = "^" + re.sub(r"\{(\w+)\}", r"([^/]+)", pattern) + "$"
        ROUTES.append((method.upper(), re.compile(regex), fn))
        return fn
    return deco


# ---------------------------- Нээлттэй ----------------------------
@route("GET", "/api/health")
def r_health(h, ident):
    return {"ok": True, "service": "Цаг бүртгэлийн систем", "version": VERSION,
            "server_time": now_local().strftime("%Y-%m-%d %H:%M:%S")}


@route("GET", "/api/meta")
def r_meta(h, ident):
    s = get_settings()
    return {
        "company_name": s["company_name"], "timezone": s["timezone"],
        "schedule": {"start": s["schedule_start"], "end": s["schedule_end"],
                     "grace_minutes": int(float(s["grace_minutes"] or 0)),
                     "lunch_start": s.get("lunch_start"), "lunch_end": s.get("lunch_end"),
                     "lunch_paid": s.get("lunch_paid") == "1",
                     "paid_minutes_per_day": paid_minutes_per_day(),
                     "paid_hours_per_day": round(paid_minutes_per_day() / 60.0, 2),
                     "night_start": s["night_start"], "night_end": s["night_end"],
                     "night_minutes": core.shift_minutes(today_str(), "night"),
                     "night_hours": round(core.shift_minutes(today_str(), "night") / 60.0, 2)},
        "require_photo": s.get("require_photo") == "1",
        "notify": {"start": s.get("notify_start") == "1", "end": s.get("notify_end") == "1",
                   "auto_absent": s.get("auto_absent") == "1"},
        "workdays": core.workday_list(),
        "workdays_label": ", ".join(core.WEEKDAY_MN[d] for d in core.workday_list()),
        "geofence": {"enabled": s["geofence_enabled"] == "1", "name": s["geofence_name"],
                     "radius_m": float(s["geofence_radius_m"])},
        "demo_mode": s["demo_mode"] == "1",
        "server_time": now_local().strftime("%Y-%m-%d %H:%M:%S"),
        "weekday_mn": core.WEEKDAY_MN[core.now_local().isoweekday()],
        "status_labels": core.STATUS_MN,
    }


@route("POST", "/api/auth/employee-login")
def r_emp_login(h, ident):
    code = (h.body.get("code") or "").strip()
    pin = (h.body.get("pin") or "").strip()
    if not code or not pin:
        raise ApiError(400, "Ажилтны код болон ПИН кодоо оруулна уу.")
    emp = verify_pin(code, pin)
    if not emp:
        audit("system", "employee_login_failed", code)
        raise ApiError(401, "Ажилтны код эсвэл ПИН код буруу байна.")
    token = create_session("employee", emp["id"], emp["full_name"])
    h.set_session_cookie(token)
    audit(f"employee:{emp['id']}", "login", emp["full_name"])
    return {"ok": True, "role": "employee", "token": token, "employee": emp,
            "today": employee_day_view(emp["id"])}


@route("POST", "/api/auth/admin-login")
def r_admin_login(h, ident):
    user = (h.body.get("username") or "").strip()
    pwd = (h.body.get("password") or "").strip()
    s = get_settings()
    if user == s["admin_user"] and pwd == s["admin_password"]:
        token = create_session("admin", None, user)
        h.set_session_cookie(token)
        audit("admin", "login", user)
        return {"ok": True, "role": "admin", "token": token,
                "name": user, "company_name": s["company_name"]}
    audit("system", "admin_login_failed", user)
    raise ApiError(401, "Хэрэглэгчийн нэр эсвэл нууц үг буруу байна.")


@route("POST", "/api/auth/logout")
def r_logout(h, ident):
    h.clear_session_cookie()
    return {"ok": True, "message": "Системээс гарлаа."}


@route("GET", "/api/auth/me")
def r_me(h, ident):
    ident = require(h)
    out = {"role": ident["role"], "kind": ident.get("kind"), "label": ident.get("label", "")}
    if ident.get("employee_id"):
        out["employee"] = get_employee(ident["employee_id"])
        out["today"] = employee_day_view(ident["employee_id"])
    return out


# ---------------------------- Ажилтны API ----------------------------
@route("GET", "/api/employee/today")
def r_emp_today(h, ident):
    ident = require(h, "employee")
    emp = target_employee(h, ident, {})
    day = h.query.get("date", [None])[0]
    return {**employee_day_view(emp["id"], day), "employee": emp, "vision": build_vision(emp, day)}


@route("GET", "/api/employee/history")
def r_emp_history(h, ident):
    ident = require(h, "employee")
    emp = target_employee(h, ident, {})
    month = h.query.get("month", [today_str()[:7]])[0]
    if not re.match(r"^\d{4}-\d{2}$", month or ""):
        raise ApiError(400, "Сар буруу форматтай байна (YYYY-MM).")
    return {**employee_history(emp["id"], month), "employee": emp}


@route("POST", "/api/employee/clock-in")
def r_emp_ci(h, ident):
    ident = require(h, "employee")
    emp = target_employee(h, ident, h.body)
    res = clock_in(emp["id"], h.body.get("latitude"), h.body.get("longitude"),
                   h.body.get("accuracy"), h.body.get("note", ""),
                   demo=bool(h.body.get("demo_mode")),
                   photo=h.body.get("photo"), photo_source=h.body.get("photo_source", "camera"))
    if not res["ok"]:
        raise ApiError(422, res["error"], extra={"need_photo": res.get("need_photo", False)},
                       )
    day = res["record"]["work_date"]
    return {**res, "message": f"Ажилд орох бүртгэл амжилттай. {res['record']['clock_in_hm']}",
            "employee": emp, "today": employee_day_view(emp["id"], day),
            "vision": build_vision(emp, day, res["record"])}


@route("POST", "/api/employee/clock-out")
def r_emp_co(h, ident):
    ident = require(h, "employee")
    emp = target_employee(h, ident, h.body)
    res = clock_out(emp["id"], h.body.get("latitude"), h.body.get("longitude"),
                    h.body.get("accuracy"), h.body.get("note", ""),
                    demo=bool(h.body.get("demo_mode")),
                    photo=h.body.get("photo"), photo_source=h.body.get("photo_source", "camera"))
    if not res["ok"]:
        raise ApiError(422, res["error"], extra={"need_photo": res.get("need_photo", False)})
    day = res["record"]["work_date"]
    return {**res, "message": f"Ажлаас буух бүртгэл амжилттай. {res['record']['clock_out_hm']}",
            "employee": emp, "today": employee_day_view(emp["id"], day),
            "vision": build_vision(emp, day, res["record"])}


# ---------------------------- Удирдлагын API ----------------------------
@route("GET", "/api/admin/board")
def r_board(h, ident):
    require(h, "admin")
    return live_board(h.query.get("date", [today_str()])[0])


@route("GET", "/api/admin/daily")
def r_daily(h, ident):
    require(h, "admin")
    return daily_records(h.query.get("date", [today_str()])[0])


@route("GET", "/api/admin/monthly")
def r_monthly(h, ident):
    require(h, "admin")
    month = h.query.get("month", [today_str()[:7]])[0]
    if not re.match(r"^\d{4}-\d{2}$", month or ""):
        raise ApiError(400, "Сар буруу форматтай байна (YYYY-MM).")
    return month_report(month)


@route("GET", "/api/admin/matrix")
def r_matrix(h, ident):
    require(h, "admin")
    month = h.query.get("month", [today_str()[:7]])[0]
    return reports.month_daily_matrix(month)


@route("GET", "/api/admin/employees")
def r_emps(h, ident):
    require(h, "admin")
    emps = list_employees()
    for e in emps:                                  # v4.3: ажилтан бүрийн үйлчлэх гео хязгаар
        e["geofence"] = effective_geo(e)
    return {"employees": emps, "settings": safe_settings(),
            "geofence_modes": [{"value": m, "label": GEOFENCE_MODE_LABEL[m]}
                               for m in GEOFENCE_MODES],
            "geofence_default": effective_geo(None)}


@route("POST", "/api/admin/employees")
def r_emp_create(h, ident):
    require(h, "admin")
    b = h.body
    if not b.get("code") or not b.get("full_name") or not b.get("pin"):
        raise ApiError(400, "Код, нэр, ПИН код заавал бөглөнө үү.")
    if core.get_employee_by_code(b["code"]):
        raise ApiError(409, "Энэ кодтой ажилтан бүртгэгдсэн байна.")
    emp = create_employee(b["code"], b["full_name"], b.get("department", ""),
                          b.get("position", ""), b["pin"])
    return {"ok": True, "employee": emp, "message": f"{emp['full_name']} амжилттай бүртгэгдлээ."}


@route("PUT", "/api/admin/employees/{eid}")
def r_emp_update(h, ident, eid):
    require(h, "admin")
    emp = update_employee(int(eid), h.body)
    if not emp:
        raise ApiError(404, "Ажилтан олдсонгүй.")
    return {"ok": True, "employee": emp, "message": "Ажилтны мэдээлэл шинэчлэгдлээ."}


@route("PUT", "/api/admin/employees/{eid}/geofence")
def r_emp_geofence(h, ident, eid):
    """Ажилтан бүрийн гео хаалт: горим (талбай/өөрийн/идэвхгүй) + байршил, радиус."""
    require(h, "admin")
    b = h.body
    mode = b.get("mode") or b.get("geofence_mode") or "site"
    try:
        emp, geo = set_employee_geofence(int(eid), mode, b.get("lat", b.get("latitude")),
                                         b.get("lng", b.get("longitude")),
                                         b.get("radius_m", b.get("radius")))
    except ValueError as ex:
        raise ApiError(400, str(ex))
    if not emp:
        raise ApiError(404, "Ажилтан олдсонгүй.")
    audit("admin", "employee_geofence_api", f"{emp['code']} → {mode}")
    if mode == "off":
        msg = f"{emp['full_name']}: гео хаалт идэвхгүй боллоо (байршил хязгаарлагдахгүй)."
    elif mode == "custom":
        msg = (f"{emp['full_name']}: өөрийн байршил {float(geo['radius_m'] or 300):.0f} м "
               f"радиустай гео хаалт тохируулагдлаа.")
    else:
        msg = f"{emp['full_name']}: талбайгаа дагах горимд буцлаа."
    return {"ok": True, "employee": emp, "geo": geo, "mode": mode, "message": msg}


@route("GET", "/api/admin/settings")
def r_settings_get(h, ident):
    require(h, "admin")
    return {"settings": safe_settings()}


@route("PUT", "/api/admin/settings")
def r_settings_put(h, ident):
    require(h, "admin")
    before = get_settings()
    new = set_settings({k: v for k, v in h.body.items() if k in core.DEFAULT_SETTINGS})
    audit("admin", "settings_update", " | ".join(
        f"{k}: {before.get(k)} → {new.get(k)}" for k in h.body if k in core.DEFAULT_SETTINGS))
    return {"ok": True, "settings": safe_settings(), "message": "Тохиргоо хадгалагдлаа."}


@route("POST", "/api/admin/records")
def r_manual(h, ident):
    require(h, "admin")
    b = h.body
    if not b.get("employee_id") or not b.get("date"):
        raise ApiError(400, "Ажилтан болон огноо шаардлагатай.")
    rec = manual_record(int(b["employee_id"]), b["date"],
                        b.get("clock_in"), b.get("clock_out"), b.get("note", ""))
    return {"ok": True, "record": rec, "message": "Бүртгэл хадгалагдлаа."}


@route("GET", "/api/geo/check")
def r_geo_any(h, ident):
    ident = require(h)
    lat = h.query.get("lat", [None])[0]
    lng = h.query.get("lng", [None])[0]
    # Ажилтан өөрийн ажлын байрны хүрээг шалгана (талбай оноосон бол түүнийг)
    emp = get_employee(ident["employee_id"]) if ident.get("employee_id") else None
    return check_geofence(lat, lng, emp=emp)


@route("GET", "/api/admin/geofence-check")
def r_geo_check(h, ident):
    require(h, "admin")
    lat = h.query.get("lat", [None])[0]
    lng = h.query.get("lng", [None])[0]
    eid = h.query.get("employee_id", [None])[0]
    emp = get_employee(int(eid)) if eid else None
    return check_geofence(lat, lng, emp=emp)


@route("POST", "/api/admin/demo/seed")
def r_demo_seed(h, ident):
    require(h, "admin")
    res = demo_seed_today(force_workday=bool(h.body.get("force_workday", True)))
    if not res.get("ok"):
        raise ApiError(409, res["message"])
    return {**res, "board": live_board(today_str())}


@route("DELETE", "/api/admin/demo/today")
def r_demo_clear(h, ident):
    require(h, "admin")
    res = demo_clear_today()
    return {**res, "board": live_board(today_str())}


@route("POST", "/api/admin/recalc")
def r_recalc(h, ident):
    require(h, "admin")
    n = recalc_all(h.body.get("month"))
    return {"ok": True, "recalculated": n,
            "message": f"{n} бүртгэл одоогийн ажлын хуваарийн дагуу дахин тооцоологдлоо."}


@route("GET", "/api/admin/geofence-log")
def r_geo_log(h, ident):
    require(h, "admin")
    logs = [l for l in recent_audit(300) if "blocked" in l["action"]]
    return {"violations": logs[:100],
            "message": "Та ажлын байрандаа байхгүй байна. Бүртгэл амжилтгүй."}


@route("GET", "/api/admin/backup.zip")
def r_backup_zip(h, ident):
    """Бүх өгөгдөл (сан + зураг) — ZIP нөөц хуулбар (зөвхөн админ)."""
    ident = require(h, "admin")
    data = make_backup_zip()
    audit(ident.get("username") or "admin", "backup_download",
          f"Нөөц хуулбар татав ({len(data) / 1024 / 1024:.1f} MB)")
    h.send_bytes(data, "application/zip",
                 f"attendance_backup_{now_local().strftime('%Y%m%d_%H%M')}.zip")


@route("GET", "/api/admin/audit")
def r_audit(h, ident):
    require(h, "admin")
    return {"log": recent_audit(120)}


@route("GET", "/api/admin/api-keys")
def r_keys(h, ident):
    require(h, "admin")
    return {"keys": list_api_keys()}


@route("POST", "/api/admin/api-keys")
def r_key_create(h, ident):
    require(h, "admin")
    k = create_api_key(h.body.get("name", "AI Төлөөлөгч"), h.body.get("role", "agent"))
    return {"ok": True, "key": k, "message": "API түлхүүр үүсгэгдлээ. Хуулж хадгалаарай!"}


@route("DELETE", "/api/admin/api-keys/{key}")
def r_key_revoke(h, ident, key):
    require(h, "admin")
    revoke_api_key(unquote(key))
    return {"ok": True, "message": "API түлхүүр идэвхгүй боллоо."}


# ---------------------------- AI Agent API ----------------------------
@route("GET", "/api/agent/directory")
def a_directory(h, ident):
    require(h, "admin_or_agent")
    return {"employees": list_employees(active_only=True),
            "schedule": get_settings()["schedule_start"] + "-" + get_settings()["schedule_end"]}


@route("GET", "/api/agent/status")
def a_status(h, ident):
    require(h, "admin_or_agent")
    board = live_board(h.query.get("date", [today_str()])[0])
    return {**board, "vision": "Ирцийн шууд самбар. Хоцорсон / эрт явсан / ирээгүй ажилтнууд."}


@route("GET", "/api/agent/employee-status")
def a_emp_status(h, ident):
    require(h, "admin_or_agent")
    emp = target_employee(h, ident, {})
    day = h.query.get("date", [None])[0]
    return {**employee_day_view(emp["id"], day), "employee": emp,
            "vision": build_vision(emp, day)}


@route("POST", "/api/agent/clock-in")
def a_ci(h, ident):
    require(h, "admin_or_agent")
    emp = target_employee(h, ident, h.body)
    b = h.body
    res = clock_in(emp["id"], b.get("latitude"), b.get("longitude"), b.get("accuracy"),
                   b.get("note", ""), force=bool(b.get("force")), demo=bool(b.get("demo_mode")))
    if not res["ok"]:
        raise ApiError(422, res["error"])
    return {**res, "employee": emp,
            "message": f"{emp['full_name']} ажилд орох бүртгэл амжилттай.",
            "vision": build_vision(emp, res["record"]["work_date"], res["record"])}


@route("POST", "/api/agent/clock-out")
def a_co(h, ident):
    require(h, "admin_or_agent")
    emp = target_employee(h, ident, h.body)
    b = h.body
    res = clock_out(emp["id"], b.get("latitude"), b.get("longitude"), b.get("accuracy"),
                    b.get("note", ""), force=bool(b.get("force")), demo=bool(b.get("demo_mode")))
    if not res["ok"]:
        raise ApiError(422, res["error"])
    return {**res, "employee": emp,
            "message": f"{emp['full_name']} ажлаас буух бүртгэл амжилттай.",
            "vision": build_vision(emp, res["record"]["work_date"], res["record"])}


@route("POST", "/api/agent/geofence-check")
def a_geo(h, ident):
    require(h, "admin_or_agent")
    b = h.body
    emp = None
    if b.get("employee_id"):
        emp = get_employee(int(b["employee_id"]))
    elif b.get("code"):
        emp = core.get_employee_by_code(b["code"])
    return check_geofence(b.get("latitude"), b.get("longitude"), emp=emp)


@route("GET", "/api/agent/monthly-report")
def a_report(h, ident):
    require(h, "admin_or_agent")
    month = h.query.get("month", [today_str()[:7]])[0]
    rep = month_report(month)
    rep["vision"] = (
        f"{rep['month_label']} сарын цалингийн тайлан. {rep['totals']['employees']} ажилтан, "
        f"нийт ажилласан {rep['totals']['worked_hm']}, хоцорсон {rep['totals']['late_days']} тоо "
        f"({rep['totals']['late_minutes']} мин), хасагдсан нийт {rep['totals']['deduct_minutes']} мин.")
    return rep


@route("GET", "/api/agent/vision")
def a_vision(h, ident):
    """AI агентад зориулсан нэгдсэн төлөв — нэг дуудалтаар бүх контекст."""
    require(h, "admin_or_agent")
    day = h.query.get("date", [today_str()])[0]
    month = day[:7]
    board = live_board(day)
    rep = month_report(month)
    lines = [
        f"# Ирцийн төлөв — {day} ({board['weekday_mn']})",
        f"Ажлын хуваарь: {board['schedule']['start']}–{board['schedule']['end']}",
        f"Одоо байгаа ажилтнууд: {board['summary']['working']} / Нийт: {board['summary']['total']}",
        f"Хоцорсон: {board['summary']['late']} | Ирээгүй: {board['summary']['absent']} | "
        f"Эрт явсан: {board['summary']['early']}",
        "",
        "## Ажилтнууд",
    ]
    for e in board["employees"]:
        lines.append(f"- {e['code']} {e['full_name']}: {e['status_label']} | "
                     f"Ирсэн {e['clock_in_hm']} | Явсан {e['clock_out_hm']} | "
                     f"Ажилласан {e['worked_hm']} | Хасагдсан {e['deduct_minutes']} мин")
    lines += ["", f"## {rep['month_label']} сарын дүн",
              f"Нийт ажилласан: {rep['totals']['worked_hm']} | Хоцорсон: {rep['totals']['late_days']} удаа "
              f"({rep['totals']['late_minutes']} мин) | Хасагдсан: {rep['totals']['deduct_minutes']} мин"]
    return {"date": day, "month": month, "text": "\n".join(lines),
            "board": board, "month_report": rep}


def build_vision(emp: dict, day: str | None = None, record: dict | None = None) -> str:
    """Ажилтны төлөвийг хүн/агент уншихад тохиромжтой текстээр."""
    v = employee_day_view(emp["id"], day)
    r = record or v.get("record")
    lines = [
        f"Ажилтан: {emp['full_name']} ({emp['code']}) — {emp.get('position','')}",
        f"Огноо: {v['date']} ({v['weekday_mn']}) | Ажлын хуваарь: {v['schedule']['start']}–{v['schedule']['end']}",
        f"Төлөв: {v['status_label']}",
    ]
    if r:
        if v["status_code"] == "working" and r.get("clock_in"):
            from core import fmt_hhmm, parse_dt
            live = max(0, int((now_local() - parse_dt(r["clock_in"])).total_seconds() // 60))
            worked_txt = f"{fmt_hhmm(live)} (ажиллаж байна, тооцоолж байна)"
        else:
            worked_txt = r.get("worked_hm", "—")
        lines += [f"Ирсэн цаг: {r.get('clock_in_hm','—')} | Явсан цаг: {r.get('clock_out_hm','—')}",
                  f"Ажилласан: {worked_txt} | Төлбөртэй: {r.get('payable_hm','—')}"]
        if r.get("late_minutes"):
            lines.append(f"⚠ Хоцорсон: +{r['late_minutes']} минут")
        if r.get("early_minutes"):
            lines.append(f"⚠ Эрт явсан: −{r['early_minutes']} минут")
        if not r.get("late_minutes") and not r.get("early_minutes"):
            lines.append("✓ Хуваарьт нийцсэн")
    else:
        lines.append("Өнөөдөр бүртгэл байхгүй.")
    return "\n".join(lines)


# ---------------------------- Экспорт ----------------------------
def _csv_bytes(header: list[str], rows: list[list]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return "\ufeff".encode("utf-8") + buf.getvalue().encode("utf-8")   # BOM → Excel-friendly


@route("GET", "/api/admin/export/monthly.xlsx")
def e_month_xlsx(h, ident):
    require(h, "admin")
    month = h.query.get("month", [today_str()[:7]])[0]
    data = reports.build_month_xlsx(month)
    h.send_bytes(data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                 f"timesheet_{month}.xlsx")
    return None


@route("GET", "/api/agent/export/monthly.xlsx")
def e_month_xlsx_agent(h, ident):
    require(h, "admin_or_agent")
    month = h.query.get("month", [today_str()[:7]])[0]
    h.send_bytes(reports.build_month_xlsx(month),
                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                 f"timesheet_{month}.xlsx")
    return None


@route("GET", "/api/admin/export/monthly.csv")
def e_month_csv(h, ident):
    require(h, "admin")
    month = h.query.get("month", [today_str()[:7]])[0]
    rep = month_report(month)
    rows = [[r["code"], r["full_name"], r["department"], r["position"], r["expected_days"],
             r["present_days"], r["absent_days"], r["worked_hm"], r["worked_hours"],
             r["late_days"], r["late_minutes"], r["early_days"], r["early_minutes"],
             r["deduct_minutes"], r["payable_hm"]] for r in rep["rows"]]
    t = rep["totals"]
    rows.append([])
    rows.append(["НИЙТ", f"{t['employees']} ажилтан", "", "", "", "", t["absent_days"],
                 t["worked_hm"], t["worked_hours"], t["late_days"], t["late_minutes"],
                 t["early_days"], t["early_minutes"], t["deduct_minutes"], t["payable_hm"]])
    header = ["Ажилтны код", "Ажилтны нэр", "Хэлтэс", "Албан тушаал", "Ажиллах өдөр",
              "Ирсэн өдөр", "Тасалсан өдөр", "Нийт ажилласан цаг", "Ажилласан цаг (тоо)",
              "Нийт хоцорсон тоо", "Хоцорсон минут", "Нийт эрт явсан тоо", "Эрт явсан минут",
              "Хасагдсан нийт минут", "Төлбөртэй цаг"]
    h.send_bytes(_csv_bytes(header, rows), "text/csv; charset=utf-8", f"timesheet_{month}.csv")
    return None


# ==========================================================================
# Барилгын бригадын нэмэлт API — ажлын байр, чөлөө, цалин
# ==========================================================================
def _month_param(h) -> str:
    month = h.query.get("month", [today_str()[:7]])[0]
    if not re.match(r"^\d{4}-\d{2}$", month or ""):
        raise ApiError(400, "Сар буруу форматтай байна (YYYY-MM).")
    return month


def _valid_period(period: str) -> bool:
    """«YYYY-MM» ба сар нь 01–12 хооронд эсэх."""
    if not re.match(r"^\d{4}-\d{2}$", period or ""):
        return False
    return 1 <= int(period[5:7]) <= 12


def _period_param(h) -> str:
    """`period=YYYY-MM` — тухайн сарын 10-ны үндсэн цалингийн үе (анхдагч: одоогийн үе)."""
    period = h.query.get("period", [None])[0] or period_key_for()
    if not _valid_period(period):
        raise ApiError(400, "Үе буруу форматтай байна (YYYY-MM, сар 01–12).")
    return period


def _emp_ref(b: dict) -> int:
    """employee_id эсвэл code-оор ажилтныг олно."""
    if b.get("employee_id") not in (None, ""):
        return int(b["employee_id"])
    code = (b.get("code") or b.get("employee_code") or "").strip()
    if code:
        emp = next((e for e in list_employees() if e["code"] == code), None)
        if emp:
            return int(emp["id"])
    raise ApiError(400, "Ажилтан (employee_id эсвэл code) шаардлагатай.")


def _num(v, name: str, required: bool = True):
    if v in (None, ""):
        if required:
            raise ApiError(400, f"{name} талбар шаардлагатай.")
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        raise ApiError(400, f"{name} тоо байх ёстой.")


# ---------------------------- Ажлын байр (талбай) ----------------------------
@route("GET", "/api/admin/sites")
def r_sites(h, ident):
    require(h, "admin")
    sites = list_sites()
    with core.connect() as con:
        counts = {r["site_id"]: r["n"] for r in con.execute(
            "SELECT site_id, COUNT(*) n FROM employees WHERE active=1 GROUP BY site_id").fetchall()}
    for st in sites:
        st["employee_count"] = counts.get(st["id"], 0)
    st = get_settings()
    return {"sites": sites,
            "geofence_default": effective_geo(None),
            "maps": {"provider": "google",
                     "api_key": st.get("google_maps_api_key") or "",
                     "has_key": bool(st.get("google_maps_api_key")),
                     "embed": "https://maps.google.com/maps?q={lat},{lng}&z={z}&output=embed"},
            "message": ""}


@route("POST", "/api/admin/geo/parse")
def r_geo_parse(h, ident):
    """Google Maps холбоос/координатыг (lat, lng) болгон задлана (v4.2)."""
    require(h, "admin")
    text = h.body.get("text") or h.body.get("link") or ""
    res = parse_geo_text(text)
    if not res.get("ok"):
        raise ApiError(400, res.get("error", "Координат олдсонгүй."),
                       extra={"short_link": bool(res.get("short_link"))})
    return {**res, "message": f"Координат олдлоо: {res['lat']:.5f}, {res['lng']:.5f}"}


@route("POST", "/api/admin/sites")
def r_site_create(h, ident):
    require(h, "admin")
    b = h.body
    if not b.get("name"):
        raise ApiError(400, "Ажлын байрны нэр шаардлагатай.")
    st = create_site(b["name"], _num(b.get("latitude"), "Өргөрөг", False),
                     _num(b.get("longitude"), "Уртраг", False),
                     _num(b.get("radius_m"), "Радиус", False) or 300,
                     b.get("address", ""))
    return {"ok": True, "site": st, "message": f"«{st['name']}» ажлын байр нэмэгдлээ."}


@route("PUT", "/api/admin/sites/{sid}")
def r_site_update(h, ident, sid):
    require(h, "admin")
    b = dict(h.body)
    for k in ("latitude", "longitude"):
        if k in b:
            b["lat" if k == "latitude" else "lng"] = b.pop(k)
    st = update_site(int(sid), b)
    if not st:
        raise ApiError(404, "Ажлын байр олдсонгүй.")
    return {"ok": True, "site": st, "message": "Ажлын байр шинэчлэгдлээ."}


@route("DELETE", "/api/admin/sites/{sid}")
def r_site_delete(h, ident, sid):
    require(h, "admin")
    delete_site(int(sid))
    return {"ok": True, "message": "Ажлын байр идэвхгүй боллоо."}


# ---------------------------- Чөлөө (v4: нэг төрөл, хүсэлт → батлах) ----------------------------
@route("GET", "/api/admin/leaves")
def r_leaves(h, ident):
    require(h, "admin")
    month = _month_param(h)
    status = h.query.get("status", ["all"])[0]
    return {"month": month, "leaves": list_leaves(month, status=status),
            "pending_requests": pending_leave_requests(),
            "kinds": LEAVE_KINDS,
            "statuses": {k: v for k, v in LEAVE_STATUS_LABEL.items()},
            "paid_kinds": [x.strip() for x in get_setting("paid_leave_kinds").split(",") if x.strip()]}


@route("POST", "/api/admin/leaves")
def r_leave_add(h, ident):
    require(h, "admin")
    b = h.body
    if not b.get("employee_id"):
        raise ApiError(400, "Ажилтан сонгоно уу.")
    res = add_leave(int(b["employee_id"]), b.get("kind", "чөлөө"), b.get("start_date", ""),
                    b.get("end_date"), bool(b.get("all_day", True)),
                    b.get("start_time"), b.get("end_time"), b.get("note", ""),
                    created_by="admin", status=b.get("status", "approved"),
                    paid=(1 if b.get("paid") else 0))      # v3.1: анхдагч = цалингүй
    if not res.get("ok"):
        raise ApiError(400, res.get("error", "Чөлөө бүртгэх боломжгүй."))
    return res


# --- v3.1: ажилтны хүсэлт → админ мэдэгдлээр батална ------------------------
@route("GET", "/api/admin/leave-requests")
def r_leave_requests(h, ident):
    require(h, "admin")
    month = _month_param(h)
    status = h.query.get("status", ["pending"])[0]
    rows = list_leaves(month, status=status)
    return {"month": month, "status": status, "requests": rows,
            "pending_count": len(pending_leave_requests()),
            "statuses": LEAVE_STATUS_LABEL, "private": False}


@route("POST", "/api/admin/leave-requests/{lid}/decide")
def r_leave_decide(h, ident, lid):
    require(h, "admin")
    b = h.body or {}
    approve = b.get("approve", True)
    if isinstance(approve, str):
        approve = approve.lower() in ("1", "true", "yes", "approved")
    res = decide_leave(int(lid), bool(approve), paid=b.get("paid"), by="admin")
    if not res.get("ok"):
        raise ApiError(404 if "олдсонгүй" in res.get("error", "") else 400,
                       res.get("error", "Хүсэлт олдсонгүй."))
    return res


@route("DELETE", "/api/admin/leaves/{lid}")
def r_leave_delete(h, ident, lid):
    require(h, "admin")
    return delete_leave(int(lid))


@route("GET", "/api/admin/leaves/{eid}/summary")
def r_leave_summary(h, ident, eid):
    require(h, "admin")
    month = _month_param(h)
    emp = get_employee(int(eid))
    if not emp:
        raise ApiError(404, "Ажилтан олдсонгүй.")
    return {"employee": emp, "month": month, "summary": leave_summary(int(eid), month)}


# ---------------------------- Цалин ----------------------------
@route("GET", "/api/admin/payroll")
def r_payroll(h, ident):
    require(h, "admin")
    month = _month_param(h)
    data = monthly_payroll(month)
    data["currency_label"] = get_setting("currency")
    return data


@route("GET", "/api/admin/payroll-rules")
def r_pay_rules(h, ident):
    require(h, "admin")
    s = get_settings()
    return {"rules": {
        "currency": s["currency"],
        "default_daily_rate": float(s["default_daily_rate"]),
        "night_start": s["night_start"], "night_end": s["night_end"],
        "guard_percent": float(s["guard_percent"]),
        "worker_percent": float(s["worker_percent"]),
        "overtime_multiplier": float(s["overtime_multiplier"]),
        "absence_penalty_days": int(float(s["absence_penalty_days"])),
        "absence_penalty_percent": float(s["absence_penalty_percent"]),
        "paid_leave_kinds": [x.strip() for x in s["paid_leave_kinds"].split(",") if x.strip()],
        "show_pay_to_employee": s["show_pay_to_employee"] == "1",
        "absent_minutes_grace": int(float(s.get("absent_minutes_grace") or 10)),
        "leave_request_notify": s.get("leave_request_notify") == "1",
        "leave_reminder_minutes": int(float(s.get("leave_reminder_minutes") or 30)),
        "day_statuses": DAY_STATUS_LABEL,
    }}


@route("PUT", "/api/admin/payroll-rules")
def r_pay_rules_put(h, ident):
    require(h, "admin")
    allowed = {"currency", "default_daily_rate", "night_start", "night_end",
               "guard_percent", "worker_percent", "overtime_multiplier",
               "absence_penalty_days", "absence_penalty_percent", "paid_leave_kinds",
               "show_pay_to_employee", "absent_minutes_grace", "leave_request_notify",
               "leave_reminder_minutes"}
    vals = {}
    for k, v in h.body.items():
        if k not in allowed:
            continue
        if k == "paid_leave_kinds" and isinstance(v, list):
            v = ",".join(str(x).strip() for x in v if str(x).strip())
        if k in ("show_pay_to_employee", "leave_request_notify"):
            v = "1" if v in (True, 1, "1", "true", "yes") else "0"
        vals[k] = v
    before = get_settings()
    new = set_settings(vals)
    n = recalc_all()      # шөнийн цаг/коэффициент өөрчлөгдвөл дахин тооцоолно
    audit("admin", "payroll_rules_update",
          " | ".join(f"{k}: {before.get(k)} → {new.get(k)}" for k in vals))
    return {"ok": True, "rules": r_pay_rules(h, ident)["rules"],
            "recalculated": n,
            "message": f"Цалингийн дүрэм хадгалагдаж, {n} бүртгэл дахин тооцоологдлоо."}


@route("POST", "/api/admin/employees/{eid}/extra-hours")
def r_extra_hours(h, ident, eid):
    require(h, "admin")
    b = h.body
    if not b.get("date"):
        raise ApiError(400, "Огноо шаардлагатай.")
    res = set_extra_hours(int(eid), b["date"], _num(b.get("hours"), "Нэмэлт цаг"), b.get("note", ""))
    if not res.get("ok"):
        raise ApiError(400, res.get("error", "Хадгалах боломжгүй."))
    return res


@route("GET", "/api/admin/employees/{eid}/pay")
def r_emp_pay(h, ident, eid):
    require(h, "admin")
    month = _month_param(h)
    emp = get_employee(int(eid))
    if not emp:
        raise ApiError(404, "Ажилтан олдсонгүй.")
    data = monthly_payroll(month)
    row = next((r for r in data["rows"] if r["employee_id"] == int(eid)), None)
    return {"employee": emp, "month": month, "pay": employee_pay(int(eid)), "row": row,
            "rules": data["rules"], "currency": data["currency"], "site": employee_site(emp)}


@route("GET", "/api/admin/employees/{eid}/days")
def r_emp_days(h, ident, eid):
    require(h, "admin")
    month = _month_param(h)
    emp = get_employee(int(eid))
    if not emp:
        raise ApiError(404, "Ажилтан олдсонгүй.")
    with core.connect() as con:
        rows = [dict(r) for r in con.execute(
            "SELECT * FROM attendance WHERE employee_id=? AND work_date LIKE ? ORDER BY work_date",
            (int(eid), f"{month}-%")).fetchall()]
    days = [apply_flags(r) for r in rows]
    return {"employee": emp, "month": month, "days": days,
            "total_pay": round(sum(float(r["pay_amount"] or 0) for r in rows), 2),
            "total_extra": sum(int(r["extra_minutes"] or 0) for r in rows)}


@route("GET", "/api/admin/employees/{eid}/geo")
def r_emp_geo(h, ident, eid):
    require(h, "admin")
    emp = get_employee(int(eid))
    if not emp:
        raise ApiError(404, "Ажилтан олдсонгүй.")
    return {"employee": emp, "geo": effective_geo(emp), "site": employee_site(emp)}


# ---------------------------- Ажилтны өөрийн цалин (зөвхөн өөрт нь) ----------------------------
@route("GET", "/api/employee/my-pay")
def r_emp_my_pay(h, ident):
    ident = require(h, "employee")
    if not ident.get("employee_id"):
        raise ApiError(403, "Энэ хэсэг зөвхөн ажилтанд зориулагдсан.")
    month = _month_param(h)
    eid = int(ident["employee_id"])
    if get_setting("show_pay_to_employee") != "1":
        return {"month": month, "hidden": True,
                "message": "Цалингийн мэдээлэл харуулахгүй байхаар тохируулсан байна."}
    emp = get_employee(eid)
    data = monthly_payroll(month)
    row = next((r for r in data["rows"] if r["employee_id"] == eid), None)
    return {"month": month, "employee": emp, "row": row, "currency": data["currency"],
            "rules": data["rules"], "pay": employee_pay(eid),
            "site": employee_site(emp), "leaves": list_leaves(month, eid),
            "leave_summary": leave_summary(eid, month), "private": True}


@route("GET", "/api/employee/my-leaves")
def r_emp_my_leaves(h, ident):
    ident = require(h, "employee")
    if not ident.get("employee_id"):
        raise ApiError(403, "Энэ хэсэг зөвхөн ажилтанд зориулагдсан.")
    month = _month_param(h)
    eid = int(ident["employee_id"])
    pend = pending_leave_requests(eid)
    return {"month": month, "leaves": list_leaves(month, eid),
            "leave_summary": leave_summary(eid, month), "private": True,
            "pending": len(pend), "statuses": LEAVE_STATUS_LABEL}


@route("POST", "/api/employee/leave-request")
def r_emp_leave_request(h, ident):
    """Ажилтан аппаас чөлөө хүсэлт илгээнэ (хэдэн цаг / өдөр / хэдэн өдөр)."""
    ident = require(h, "employee")
    eid = ident.get("employee_id")
    if not eid:
        raise ApiError(403, "Энэ хэсэг зөвхөн ажилтанд зориулагдсан.")
    b = h.body or {}
    res = request_leave(int(eid), b.get("start_date", ""), b.get("end_date"),
                        bool(b.get("all_day", True)), b.get("start_time"), b.get("end_time"),
                        b.get("note", ""))
    if not res.get("ok"):
        raise ApiError(400, res.get("error", "Хүсэлт илгээх боломжгүй."))
    res["pending"] = len(pending_leave_requests(int(eid)))
    res["unread_notifications"] = unread_count(int(eid))
    return res


@route("POST", "/api/employee/leave-requests/{lid}/cancel")
def r_emp_leave_cancel(h, ident, lid):
    """Ажилтан өөрийн ХҮЛЭЭГДЭЖ БУЙ хүсэлтийг цуцална."""
    ident = require(h, "employee")
    eid = ident.get("employee_id")
    if not eid:
        raise ApiError(403, "Энэ хэсэг зөвхөн ажилтанд зориулагдсан.")
    res = cancel_leave(int(lid), employee_id=int(eid))
    if not res.get("ok"):
        raise ApiError(400, res.get("error", "Цуцлах боломжгүй."))
    return res


# ---------------------------- Экспорт: цалин ----------------------------
@route("GET", "/api/admin/export/payroll.xlsx")
def e_payroll_xlsx(h, ident):
    require(h, "admin")
    month = _month_param(h)
    h.send_bytes(reports.build_payroll_xlsx(month),
                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                 f"payroll_{month}.xlsx")
    return None


@route("GET", "/api/admin/export/payroll.csv")
def e_payroll_csv(h, ident):
    require(h, "admin")
    month = _month_param(h)
    pr = monthly_payroll(month)
    header = ["Код", "Ажилтны нэр", "Албан тушаал", "Ажлын байр", "Өдрийн цалин",
              "Ирсэн өдөр", "Хөдөлмөрийн өдөр", "Шөнийн ээлж", "Нэмэлт цаг",
              "Үндсэн цалин", "Нэмэлт цагийн цалин", "Цалинтай чөлөө", "Тасарсан өдөр",
              "Дараалал", "Торгууль", "ОЛГОХ ЦАЛИН", "Төлөв"]
    rows = [[r["code"], r["full_name"], r["position"], r["site_name"], round(r["daily_rate"]),
             r["days_worked"], r["day_credit"], r["night_days"], r["extra_hours"],
             round(r["pay_base"]), round(r["pay_extra"]), round(r["leave_pay"]),
             r["absent_days"], r["absent_streak"], round(r["penalty"]), round(r["total"]),
             r["pay_status"]] for r in pr["rows"]]
    t = pr["totals"]
    rows.append([])
    rows.append(["НИЙТ", f"{t['employees']} ажилтан", "", "", "", t["days_worked"],
                 t["day_credit"], t["night_days"], t["extra_hours"], round(t["pay_base"]),
                 round(t["pay_extra"]), round(t["leave_pay"]), "", "", round(t["penalty"]),
                 round(t["total"]), ""])
    h.send_bytes(_csv_bytes(header, rows), "text/csv; charset=utf-8", f"payroll_{month}.csv")
    return None



@route("GET", "/api/admin/export/daily.csv")
def e_daily_csv(h, ident):
    require(h, "admin")
    day = h.query.get("date", [today_str()])[0]
    data = daily_records(day)
    rows = []
    for r in data["records"]:
        rows.append([r["code"], r["full_name"], r["department"], r["clock_in_hm"],
                     r["clock_out_hm"], core.fmt_hhmm(r["worked_minutes"]), r["late_minutes"],
                     r["early_minutes"], r["deduct_minutes"], core.fmt_hhmm(r["payable_minutes"]),
                     r["in_distance_m"], r["out_distance_m"], r["note"] or ""])
    for e in data["absent"]:
        rows.append([e["code"], e["full_name"], e["department"], "—", "—", "00:00", 0, 0, 0,
                     "00:00", "", "", "Ирээгүй"])
    header = ["Код", "Ажилтны нэр", "Хэлтэс", "Ирсэн цаг", "Явсан цаг", "Ажилласан (ц:мм)",
              "Хоцролт (мин)", "Эрт явсан (мин)", "Хасагдсан (мин)", "Төлбөртэй (ц:мм)",
              "Ирэх гео зай (м)", "Явах гео зай (м)", "Тэмдэглэл"]
    h.send_bytes(_csv_bytes(header, rows), "text/csv; charset=utf-8", f"daily_{day}.csv")
    return None


def safe_settings() -> dict:
    s = get_settings()
    return s


# --------------------------------------------------------------------------
# HTTP handler
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "AttendanceSystem/" + VERSION
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # ---------- helpers ----------
    def set_session_cookie(self, token: str):
        self._extra_headers = getattr(self, "_extra_headers", [])
        self._extra_headers.append(
            ("Set-Cookie", f"att_session={token}; Path=/; Max-Age=43200; SameSite=Lax; HttpOnly"))

    def clear_session_cookie(self):
        self._extra_headers = getattr(self, "_extra_headers", [])
        self._extra_headers.append(("Set-Cookie", "att_session=; Path=/; Max-Age=0; SameSite=Lax"))

    def send_json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        for k, v in getattr(self, "_extra_headers", []):
            self.send_header(k, v)
        self._extra_headers = []
        self.end_headers()
        self.wfile.write(data)

    def send_bytes(self, data: bytes, content_type: str, filename: str | None = None):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if filename:
            self.send_header("Content-Disposition",
                             f'attachment; filename="{filename}"; '
                             f"filename*=UTF-8''{unquote(filename)}")
        for k, v in getattr(self, "_extra_headers", []):
            self.send_header(k, v)
        self._extra_headers = []
        self.end_headers()
        self.wfile.write(data)

    def read_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {"data": data}
        except Exception:
            raise ApiError(400, "Хүсэлтийн өгөгдөл буруу (JSON биш).")

    # ---------- dispatch ----------
    def handle_any(self, method: str):
        self._extra_headers = []
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        self.query = parse_qs(parsed.query)
        try:
            self.body = self.read_body() if method in ("POST", "PUT", "DELETE") else {}
        except ApiError as e:
            return self.send_json({"ok": False, "error": e.message, **e.extra}, e.status)

        if method == "OPTIONS":
            return self.send_json({"ok": True})

        for m, pattern, fn in ROUTES:
            if m != method:
                continue
            match = pattern.match(path)
            if not match:
                continue
            try:
                ident = identity(self)
                result = fn(self, ident, *match.groups())
                if result is not None:
                    self.send_json(result)
            except ApiError as e:
                self.send_json({"ok": False, "error": e.message, **e.extra}, e.status)
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                self.send_json({"ok": False, "error": f"Серверийн алдаа: {e}"}, 500)
            return

        if path in ("/openapi.json", "/api/openapi.json"):
            return self.serve_file(os.path.join(BASE_DIR, "openapi.json"),
                                   "application/json; charset=utf-8")
        if path == "/docs":
            return self.send_json({
                "service": "Цаг бүртгэл ба ирцийн систем",
                "openapi": "/openapi.json",
                "ui": "/",
                "agent_cli": "python3 agent_cli.py --help",
                "health": "/api/health"})

        if path.startswith("/api/"):
            return self.send_json({"ok": False, "error": "Ийм API зам олдсонгүй."}, 404)

        # статик файл
        if method == "GET":
            return self.serve_static(path)
        self.send_json({"ok": False, "error": "Дэмжигдэхгүй хүсэлт."}, 405)

    def do_GET(self): self.handle_any("GET")
    def do_POST(self): self.handle_any("POST")
    def do_PUT(self): self.handle_any("PUT")
    def do_DELETE(self): self.handle_any("DELETE")
    def do_OPTIONS(self): self.handle_any("OPTIONS")

    def serve_file(self, full: str, ctype: str):
        if not os.path.isfile(full):
            return self.send_json({"ok": False, "error": "Файл олдсонгүй."}, 404)
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def serve_static(self, path: str):
        rel = path.lstrip("/")
        if rel.startswith("static/"):
            rel = rel[len("static/"):]
        if rel in ("", "index.html"):
            rel = "index.html"
        # SPA: өргөтгөлгүй зам → index.html
        if "." not in os.path.basename(rel):
            rel = "index.html"
        full = os.path.normpath(os.path.join(STATIC_DIR, rel))
        if not full.startswith(STATIC_DIR) or not os.path.isfile(full):
            return self.send_json({"ok": False, "error": "Файл олдсонгүй."}, 404)
        with open(full, "rb") as f:
            data = f.read()
        ctype = MIME.get(os.path.splitext(full)[1].lower(), "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)


# ==========================================================================
# v3: Фото, нэмэлт ажлын сегмент, мэдэгдэл, бодит цагийн цалин
# ==========================================================================
@route("GET", "/api/photos")
def r_photo(h, ident):
    """Зураг үзэх: админ бүгдийг, ажилтан ЗӨВХӨН өөрийнхийг."""
    ident = require(h)
    rel = (h.query.get("path") or [""])[0]
    if not rel:
        raise ApiError(400, "Зургийн зам шаардлагатай.")
    if ident["role"] != "admin":
        eid = ident.get("employee_id")
        if not eid or not rel.split("/")[-1].startswith(f"{int(eid):03d}_"):
            raise ApiError(403, "Зөвхөн өөрийн зургийг харах боломжтой.")
    fp = photo_path(rel)
    if not fp or not os.path.isfile(fp):
        raise ApiError(404, "Зураг олдсонгүй.")
    ext = os.path.splitext(fp)[1].lower()
    ctype = {"jpg": "image/jpeg", ".jpg": "image/jpeg"}.get(ext, "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png")
    with open(fp, "rb") as f:
        data = f.read()
    h.send_response(200)
    h.send_header("Content-Type", ctype)
    h.send_header("Content-Length", str(len(data)))
    h.send_header("Cache-Control", "private, max-age=600")
    h.end_headers()
    h.wfile.write(data)


@route("GET", "/api/employee/live")
def r_emp_live(h, ident):
    """Ажилтны бодит цагийн цалин (өөрийнх нь)."""
    ident = require(h, "employee")
    if not ident.get("employee_id"):
        raise ApiError(403, "Энэ хэсэг зөвхөн ажилтанд зориулагдсан.")
    month = _month_param(h)
    return live_pay(int(ident["employee_id"]), month)


@route("GET", "/api/employee/notifications")
def r_emp_notif(h, ident):
    ident = require(h, "employee")
    eid = int(ident["employee_id"]) if ident.get("employee_id") else None
    if not eid:
        raise ApiError(403, "Энэ хэсэг зөвхөн ажилтанд зориулагдсан.")
    return {"notifications": list_notifications(eid, limit=int((h.query.get("limit") or ["30"])[0])),
            "unread": unread_count(eid)}


@route("POST", "/api/employee/notifications/read")
def r_emp_notif_read(h, ident):
    ident = require(h, "employee")
    eid = int(ident["employee_id"]) if ident.get("employee_id") else None
    ids = h.body.get("ids")
    n = mark_notifications_read(ids, eid if not ids else None)
    return {"ok": True, "marked": n, "unread": unread_count(eid)}


@route("POST", "/api/employee/extra/start")
def r_extra_start(h, ident):
    ident = require(h, "employee")
    emp = target_employee(h, ident, h.body)
    res = extra_start(emp["id"], h.body.get("photo"),
                      kind=h.body.get("kind", "extra"), note=h.body.get("note", ""),
                      source=h.body.get("photo_source", "camera"))
    if not res.get("ok"):
        raise ApiError(422, res.get("error", "Эхлүүлэх боломжгүй."))
    return {**res, "employee": emp, "today": employee_day_view(emp["id"]), "live": live_pay(emp["id"])}


@route("POST", "/api/employee/extra/stop")
def r_extra_stop(h, ident):
    ident = require(h, "employee")
    emp = target_employee(h, ident, h.body)
    res = extra_stop(emp["id"], h.body.get("photo"), note=h.body.get("note", ""),
                     source=h.body.get("photo_source", "camera"))
    if not res.get("ok"):
        raise ApiError(422, res.get("error", "Дуусгах боломжгүй."))
    return {**res, "employee": emp, "today": employee_day_view(emp["id"]), "live": live_pay(emp["id"])}


@route("GET", "/api/employee/extra")
def r_extra_get(h, ident):
    ident = require(h, "employee")
    eid = int(ident["employee_id"]) if ident.get("employee_id") else None
    month = _month_param(h)
    seg = segment_minutes(eid, month)
    return {"open": seg.get("open"), "minutes": seg,
            "segments": list_segments(eid, month)}


@route("GET", "/api/admin/notifications")
def r_admin_notif(h, ident):
    require(h, "admin")
    limit = int((h.query.get("limit") or ["50"])[0])
    return {"notifications": list_notifications(None, limit=limit, admin_view=True),
            "unread": unread_count(None)}


@route("POST", "/api/admin/notifications/read")
def r_admin_notif_read(h, ident):
    require(h, "admin")
    ids = (h.body or {}).get("ids")
    n = mark_notifications_read(ids, None)
    return {"ok": True, "marked": n, "unread": unread_count(None)}


@route("POST", "/api/admin/notifications/tick")
def r_admin_tick(h, ident):
    """Цаг хугацааны сануулгыг гараар ажиллуулна (cron/preview-д)."""
    require(h, "admin")
    return scheduler_tick(force=bool(h.body.get("force")))


@route("GET", "/api/admin/segments")
def r_admin_segments(h, ident):
    require(h, "admin")
    month = _month_param(h)
    status = (h.query.get("status") or [None])[0]
    segs = list_segments(None, month, status)
    return {"segments": segs, "pending": sum(1 for s_ in segs if s_["status"] == "closed"),
            "missing_clockouts": missed_clockouts()}


@route("POST", "/api/admin/segments/{sid}/approve")
def r_admin_seg_approve(h, ident, sid):
    require(h, "admin")
    approve = bool(h.body.get("approve", True))
    return approve_segment(int(sid), approve, by=ident.get("label") or "admin")


@route("GET", "/api/admin/photos")
def r_admin_photos(h, ident):
    """Сар/ажилтнаар зурагт хяналт (админ)."""
    require(h, "admin")
    month = _month_param(h)
    eid = (h.query.get("employee_id") or [None])[0]
    rows = []
    with core.connect() as con:
        q = ("SELECT a.work_date, a.employee_id, e.code, e.full_name, a.in_photo, a.out_photo,"
             " a.in_photo_ts, a.out_photo_ts, a.clock_in, a.clock_out FROM attendance a"
             " JOIN employees e ON e.id=a.employee_id WHERE a.work_date LIKE ?")
        args = [f"{month}-%"]
        if eid:
            q += " AND a.employee_id=?"; args.append(int(eid))
        q += " ORDER BY a.work_date DESC, e.code"
        rows = [dict(r) for r in con.execute(q, args).fetchall()]
    segs = list_segments(int(eid) if eid else None, month)
    return {
        "month": month,
        "pending": sum(1 for s_ in segs if s_["status"] == "closed"),
        "open_segments": [s_ for s_ in segs if s_["status"] == "open"],
        "days": [r for r in rows if r["in_photo"] or r["out_photo"]],
        "missing_photo": [r for r in rows
                          if (r["clock_in"] and not r["in_photo"]) or (r["clock_out"] and not r["out_photo"])],
        "segments": [s_ for s_ in segs if s_["start_photo"] or s_["end_photo"]],
        "missing_segment_photo": [s_ for s_ in segs
                                  if (s_["start_ts"] and not s_["start_photo"])
                                  or (s_["end_ts"] and not s_["end_photo"])],
    }


@route("POST", "/api/admin/extra-hours")
def r_admin_extra_v2(h, ident):
    """Админ ажилтанд нэмэлт цаг гараар нэмнэ (фото шаардлагагүй — админы бүртгэл)."""
    require(h, "admin")
    b = h.body
    if not b.get("employee_id") or not b.get("date"):
        raise ApiError(400, "Ажилтан ба огноо шаардлагатай.")
    res = set_extra_hours(int(b["employee_id"]), b["date"], _num(b.get("hours"), "Нэмэлт цаг"),
                          b.get("note", ""))
    if not res.get("ok"):
        raise ApiError(400, res.get("error", "Хадгалах боломжгүй."))
    return res


# --------------------- Хоёр төлбөр (v4.5) ---------------------
@route("GET", "/api/admin/periods")
def r_periods(h, ident):
    """Сүүлийн үеүүд (10-ны цалингийн хугацаанууд)."""
    require(h, "admin")
    n = int((h.query.get("n", ["6"])[0] or 6))
    keys = recent_periods(max(1, min(36, n)))
    return {"ok": True, "current": period_key_for(), "periods": [
        {"period": k, **pay_period_bounds(k)} for k in keys], "rules": advance_rules()}


@route("GET", "/api/admin/pay-cycle")
def r_pay_cycle(h, ident):
    """Хоёр төлбөрийн хуанли: 25-ны аванс + 10-ны үндсэн цалин."""
    require(h, "admin")
    period = _period_param(h)
    data = pay_cycle_table(period)
    data["currency_label"] = get_setting("currency")
    return data


@route("GET", "/api/admin/period-payroll")
def r_period_payroll(h, ident):
    """11 → 10 үеийн үндсэн цалин (25-ны авансыг хассан дүнтэй)."""
    require(h, "admin")
    period = _period_param(h)
    data = period_payroll(period)
    data["currency_label"] = get_setting("currency")
    return data


@route("GET", "/api/admin/advances")
def r_advances(h, ident):
    """Авансын жагсаалт: хэн эрхтэй, хэн авсан, хэдэн төгрөг."""
    require(h, "admin")
    period = _period_param(h)
    data = advance_candidates(period)
    data["currency_label"] = get_setting("currency")
    return data


@route("GET", "/api/admin/advances/{eid}")
def r_advance_one(h, ident, eid):
    require(h, "admin")
    period = _period_param(h)
    rec = get_advance(int(eid), period)
    return {"ok": True, "period": period, "employee_id": int(eid),
            "advance": rec, "bounds": pay_period_bounds(period),
            "window_earnings": window_earnings(int(eid), period)}


@route("POST", "/api/admin/advances/pay")
def r_advance_pay(h, ident):
    """25-ны авансыг олгосон гэж бүртгэнэ (10-ны цалингаас хасагдана)."""
    ident = require(h, "admin")
    b = h.body or {}
    period = (b.get("period") or period_key_for()).strip()
    if not _valid_period(period):
        raise ApiError(400, "Үе буруу форматтай байна (YYYY-MM, сар 01–12).")
    eid = _emp_ref(b)
    res = set_advance(eid, period, status="paid", amount=b.get("amount"),
                      note=b.get("note", ""), by=ident.get("username") or "admin",
                      paid_on=b.get("paid_on"))
    if not res.get("ok"):
        raise ApiError(400, res.get("error", "Аванс бүртгэх боломжгүй."))
    return res


@route("POST", "/api/admin/advances/cancel")
def r_advance_cancel(h, ident):
    """Авансын бүртгэлийг цуцална (10-ны цалин бүтнээр олгогдоно)."""
    ident = require(h, "admin")
    b = h.body or {}
    period = (b.get("period") or period_key_for()).strip()
    if not _valid_period(period):
        raise ApiError(400, "Үе буруу форматтай байна (YYYY-MM, сар 01–12).")
    eid = _emp_ref(b)
    res = cancel_advance(eid, period)
    if not res.get("ok"):
        raise ApiError(400, res.get("error", "Цуцлах боломжгүй."))
    return res


@route("POST", "/api/admin/advances/reset")
def r_advance_reset(h, ident):
    """Авансын бичлэгийг анхны төлөвт буцаана (эрхтэй → хүлээгдэж байна, эрхгүй → устгана)."""
    ident = require(h, "admin")
    b = h.body or {}
    period = (b.get("period") or period_key_for()).strip()
    if not _valid_period(period):
        raise ApiError(400, "Үе буруу форматтай байна (YYYY-MM, сар 01–12).")
    eid = _emp_ref(b)
    res = reset_advance(eid, period, by=ident.get("username") or "admin")
    if not res.get("ok"):
        raise ApiError(400, res.get("error", "Буцаах боломжгүй."))
    return res


@route("GET", "/api/employee/my-pay-cycle")
def r_emp_my_pay_cycle(h, ident):
    """Ажилтны цалингийн хуанли — зөвхөн өөрийн мэдээлэл."""
    ident = require(h, "employee")
    if not ident.get("employee_id"):
        raise ApiError(403, "Энэ хэсэг зөвхөн ажилтанд зориулагдсан.")
    eid = int(ident["employee_id"])
    period = _period_param(h)
    data = pay_cycle(eid, period)
    data["currency_label"] = get_setting("currency")
    return data


def start_scheduler(interval: int = 60) -> threading.Thread:
    """Ажлын цагийн сануулгыг минутанд нэг шалгах background thread."""
    def loop():
        while True:
            try:
                scheduler_tick()
            except Exception as e:                        # noqa
                print("scheduler алдаа:", e)
            time.sleep(interval)

    t = threading.Thread(target=loop, name="attendance-scheduler", daemon=True)
    t.start()
    return t


def main():
    init_db()
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.daemon_threads = True
    s = get_settings()
    print("=" * 68)
    print("  ЦАГ БҮРТГЭЛ БА ИРЦИЙН СИСТЕМ")
    print("=" * 68)
    print(f"  Сервер:        http://{host}:{port}")
    print(f"  Ажлын хуваарь: {s['schedule_start']} - {s['schedule_end']}  "
          f"(хөнгөлөлт {s['grace_minutes']} мин)")
    print(f"  Гео хаалт:     {'Идэвхтэй' if s['geofence_enabled']=='1' else 'Идэвхгүй'} "
          f"({s['geofence_radius_m']} м радиус)")
    print(f"  Админ:         {s['admin_user']} / {s['admin_password']}")
    print(f"  Демо ажилтан:  EMP001 … EMP012  (ПИН: 1234)")
    print(f"  DB файл:       {core.DB_PATH}")
    print(f"  Мэдэгдэл:      {'Асаалттай' if s.get('notify_start') == '1' else 'Унтраалттай'}"
          f" (эхлэх {s['schedule_start']} / дуусах {s['schedule_end']},"
          f" үдийн завсарлага {s.get('lunch_start')}–{s.get('lunch_end')})")
    print(f"  Фото:          {'ЗААВАЛ' if s.get('require_photo') == '1' else 'сонголтоор'}"
          f"  ·  өдрийн цаг: {paid_minutes_per_day()/60:.1f}ц (цагийн тариф = өдрийн цалин ÷ "
          f"{paid_minutes_per_day()/60:.0f}ц, шөнө ÷ {core.shift_minutes(today_str(), 'night')/60:.0f}ц)")
    print("=" * 68)
    start_scheduler()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nСервер зогслоо.")
        srv.shutdown()


if __name__ == "__main__":
    main()


