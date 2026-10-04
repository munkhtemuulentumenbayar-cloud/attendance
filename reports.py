"""
Ажилд орох/буух бүртгэлийн өдрийн дэлгэрэнгүй түүх.
"""
from __future__ import annotations

from datetime import date, timedelta

from core import (ABSENT_COLOR, LEAVE_COLORS, apply_flags, connect, fmt_hhmm, fmt_money,
                  get_settings, is_workday, leave_summary, list_leaves, monthly_payroll,
                  night_role_label,
                  month_report, today_str, MONTH_MN, WEEKDAY_MN)
from xlsxgen import write_xlsx


def month_bounds(month: str) -> tuple[date, date]:
    y, m = int(month[:4]), int(month[5:7])
    first = date(y, m, 1)
    nxt = date(y + (m == 12), (m % 12) + 1, 1)
    return first, nxt - timedelta(days=1)


def month_daily_matrix(month: str) -> dict:
    """Сар бүрийн өдөр тутмын матриц — хүснэгтэн харагдац (heatmap)."""
    first, last = month_bounds(month)
    today = date.fromisoformat(today_str())
    last = min(last, today)
    days = []
    d = first
    while d <= last:
        days.append({"date": d.isoformat(), "day": d.day,
                     "weekday_short": WEEKDAY_MN[d.isoweekday()][:2],
                     "is_workday": is_workday(d)})
        d += timedelta(days=1)

    with connect() as con:
        emps = [dict(r) for r in con.execute(
            "SELECT * FROM employees WHERE active=1 ORDER BY code").fetchall()]
        rows = [dict(r) for r in con.execute(
            "SELECT * FROM attendance WHERE work_date LIKE ?", (f"{month}-%",)).fetchall()]

    # Чөлөөний өдрүүд: өдөр → ажилтан → чөлөө
    # v4: ЗӨВХӨН БАТЛАГДСАН чөлөө нь тасалдлыг нөхнө; хүлээгдэж буй хүсэлт зөвхөн сануулга
    leave_map: dict[tuple[int, str], dict] = {}
    pending_map: dict[tuple[int, str], dict] = {}
    for lv in list_leaves(month):
        if lv.get("status") not in ("approved", None) and not lv.get("approved"):
            if lv.get("status") == "pending":
                pending_map[(lv["employee_id"], lv["start_date"])] = lv
            continue
        dd = date.fromisoformat(lv["start_date"])
        ed = date.fromisoformat(lv["end_date"] or lv["start_date"])
        while dd <= ed:
            leave_map[(lv["employee_id"], dd.isoformat())] = lv
            dd += timedelta(days=1)

    index = {(r["employee_id"], r["work_date"]): r for r in rows}
    out_rows = []
    for e in emps:
        cells = []
        for day in days:
            lv = leave_map.get((e["id"], day["date"]))
            r = index.get((e["id"], day["date"]))
            if not r or not r.get("clock_in"):
                pend = pending_map.get((e["id"], day["date"]))
                if lv:
                    when = ("бүтэн өдөр" if int(lv["all_day"]) else
                            f"{lv['start_time']}–{lv['end_time']}")
                    pay_txt = "цалинтай" if int(lv.get("paid") or 0) else "цалингүй"
                    cells.append({"status": "leave_" + LEAVE_COLORS.get(lv["kind"], "blue"),
                                  "text": "Ч", "late": 0, "early": 0,
                                  "leave": {"kind": lv["kind"],
                                            "label": f"чөлөө ({when}, {pay_txt})",
                                            "hours": lv["hours"],
                                            "note": lv["note"] or "",
                                            "status_label": lv.get("status_label") or "Батлагдсан"},
                                  "record": None})
                elif day["is_workday"] and day["date"] <= today_str():
                    note = "хүлээгдэж буй чөлөөний хүсэлт (батлагдаагүй — тасалдал хэвээр)" if pend else ""
                    cells.append({"status": "absent", "text": "✕", "late": 0, "early": 0,
                                  "leave": {"kind": lv["kind"] if lv else "чөлөө",
                                            "label": "ирээгүй", "hours": 0, "note": note} if pend
                                  else None,
                                  "record": None})
                else:
                    cells.append({"status": "none", "text": "", "late": 0, "early": 0,
                                  "leave": None, "record": None})
                continue
            r2 = apply_flags(r)
            late, early = int(r["late_minutes"]), int(r["early_minutes"])
            code = "ok"
            if late and early:
                code = "late_early"
            elif late:
                code = "late"
            elif early:
                code = "early"
            elif not r.get("clock_out"):
                code = "working"
            if (r.get("shift_type") or "day") == "night":
                code = "night" if code == "ok" else code + "_night"
            cells.append({"status": code, "text": "Ш" if (r.get("shift_type") or "day") == "night" else "✓",
                          "late": late, "early": early, "leave": None, "record": r2,
                          "night": (r.get("shift_type") or "day") == "night",
                          "night_role": r.get("night_role"),
                          "day_credit": round(float(r.get("day_credit") or 0), 3),
                          "pay": round(float(r.get("pay_amount") or 0), 2)})
        out_rows.append({
            "employee_id": e["id"], "code": e["code"], "full_name": e["full_name"],
            "department": e["department"] or "", "cells": cells,
            "daily_rate": float(e["daily_rate"] or 0), "night_role": e["night_role"] or "worker",
        })
    return {"month": month, "days": days, "rows": out_rows,
            "month_label": f"{month[:4]} оны {MONTH_MN[int(month[5:7])]}"}


def _esc(v) -> str:
    return (str(v if v is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def build_month_xlsx(month: str) -> bytes:
    """Сарын цалингийн тайлан (Payroll) — Нэгдсэн хуудас + Өдрийн дэлгэрэнгүй."""
    rep = month_report(month)
    s = get_settings()
    rows = []
    rows.append([(f"{s['company_name']} — Цаг бүртгэлийн сарын тайлан", 1)])
    rows.append([(f"Хугацаа: {rep['period']}     Ажлын хуваарь: {s['schedule_start']}-{s['schedule_end']}     "
                  f"Ажиллах өдөр: {rep['workdays_in_month']}     Тайлан үүсгэсэн: {rep['generated_at']}", 2)])
    rows.append([])

    header = ["№", "Код", "Ажилтны нэр", "Хэлтэс", "Албан тушаал", "Ажиллах өдөр",
              "Ирсэн өдөр", "Тасалсан өдөр", "Нийт ажилласан цаг (ц:мм)",
              "Ажилласан цаг (тоо)", "Нийт хоцорсон тоо", "Хоцорсон минут",
              "Нийт эрт явсан тоо", "Эрт явсан минут", "Хасагдсан нийт минут",
              "Хасагдсан цаг (ц:мм)", "Төлбөртэй цаг (ц:мм)",
              "Өдрийн цалин (₮)", "Хөдөлмөрийн өдөр", "Шөнийн ээлж",
              "Нэмэлт цаг (ц)", "Үндсэн цалин (₮)", "Нэмэлт цагийн цалин (₮)",
              "Цалинтай чөлөө (₮)", "Торгууль (₮)", "ОЛГОХ ЦАЛИН (₮)"]
    rows.append([(h, 3) for h in header])

    for i, r in enumerate(rep["rows"], start=1):
        base = 4
        rows.append([
            (i, base),                                  # №
            (r["code"], base),                          # Код
            (r["full_name"], base),                     # АЖИЛТНЫ НЭР
            (r["department"], base),
            (r["position"], base),
            (r["expected_days"], base),
            (r["present_days"], base),
            (r["absent_days"], base),
            (r["worked_hm"], base),                     # НИЙТ АЖИЛЛСАН ЦАГ (ц:мм)
            (r["worked_hours"], 5),                     # тоо (тооцоололд)
            (r["late_days"], 6 if r["late_days"] else base),        # НИЙТ ХОЦОРСОН ТОО
            (r["late_minutes"], 6 if r["late_minutes"] else base),
            (r["early_days"], 6 if r["early_days"] else base),
            (r["early_minutes"], 6 if r["early_minutes"] else base),
            (r["deduct_minutes"], 6 if r["deduct_minutes"] else base),  # ХАСАГДСАН НИЙТ МИНУТ
            (fmt_hhmm(r["deduct_minutes"]), base),
            (r["payable_hm"], 4),
            (r["daily_rate"], 4),
            (r["day_credit"], 5),
            (r["night_days"], 5),
            (r["extra_hours"], 5),
            (r["pay_base"], 4),
            (r["pay_extra"], 4),
            (r["leave_pay"], 4),
            (r["penalty"], 6 if r["penalty"] else 4),
            (r["pay_total"], 9 if r["penalty"] else 4),
        ])

    t = rep["totals"]
    rows.append([
        ("НИЙТ", 7), ("", 7), (f"{t['employees']} ажилтан", 7), ("", 7), ("", 7), ("", 7),
        ("", 7), (t["absent_days"], 7), (t["worked_hm"], 7), (t["worked_hours"], 8),
        (t["late_days"], 7), (t["late_minutes"], 7), (t["early_days"], 7),
        (t["early_minutes"], 7), (t["deduct_minutes"], 7), ("", 7), (t["payable_hm"], 7),
        ("", 7), ("", 7), (t["night_days"], 7), (t["extra_hours"], 7),
        (t["pay_base"], 7), (t["pay_extra"], 7), (t["leave_pay"], 7), (t["penalty"], 6),
        (t["pay_total"], 7),
    ])
    rows.append([])
    rows.append([("Тайлбар: Хасагдсан минут = Хоцролт + Эрт явсан минут. "
                  "Төлбөртэй цаг = Нийт ажилласан цаг − Хасагдсан минут.", 2)])
    rows.append([("Цалин: Хөдөлмөрийн өдөр × Өдрийн цалин (шөнийн ээлж хамгаалалт 50%, "
                  "ажилчин 100%) + Нэмэлт цаг + Цалинтай чөлөө − 3 хоног дараалан "
                  "тасарсан бол 10% торгууль.", 2)])

    widths = [5, 10, 26, 22, 24, 12, 11, 12, 13, 12, 12, 12, 13, 12, 13, 12, 13,
              14, 16, 12, 13, 15, 18, 16, 13, 16]

    # 2-р хуудас: өдрийн дэлгэрэнгүй
    detail_rows = [[("Ажилтны нэр", 3), ("Огноо", 3), ("Гараг", 3), ("Ирсэн цаг", 3),
                    ("Явсан цаг", 3), ("Ажилласан (ц:мм)", 3), ("Хоцролт (мин)", 3),
                    ("Эрт явсан (мин)", 3), ("Хасагдсан (мин)", 3), ("Төлбөртэй (ц:мм)", 3),
                    ("Гео зай (м)", 3), ("Ээлж", 3), ("Шөнийн үүрэг", 3),
                    ("Хөдөлмөрийн өдөр", 3), ("Нэмэлт цаг (мин)", 3),
                    ("Цалин (₮)", 3), ("Чөлөө (мин)", 3), ("Тэмдэглэл", 3), ("Төлөв", 3)]]
    with connect() as con:
        recs = con.execute(
            "SELECT a.*, e.full_name, e.code FROM attendance a JOIN employees e ON e.id=a.employee_id "
            "WHERE a.work_date LIKE ? ORDER BY e.code, a.work_date", (f"{month}-%",)).fetchall()
    for r in recs:
        r2 = apply_flags(dict(r))
        flag = []
        if r2["late_minutes"]:
            flag.append("ХОЦОРСОН")
        if r2["early_minutes"]:
            flag.append("ЭРТ ЯВСАН")
        detail_rows.append([
            (r["code"] + " " + r["full_name"], 4),
            (r["work_date"], 4),
            (WEEKDAY_MN[date.fromisoformat(r["work_date"]).isoweekday()], 4),
            (r2["clock_in_hm"], 4),
            (r2["clock_out_hm"], 4),
            (fmt_hhmm(r["worked_minutes"]), 4),
            (r["late_minutes"], 6 if r["late_minutes"] else 4),
            (r["early_minutes"], 6 if r["early_minutes"] else 4),
            (r["deduct_minutes"], 6 if r["deduct_minutes"] else 4),
            (fmt_hhmm(r["payable_minutes"]), 4),
            (r["in_distance_m"], 4),
            ("Шөнийн" if (r["shift_type"] or "day") == "night" else "Өдрийн", 4),
            (night_role_label(r["night_role"]) if (r["shift_type"] or "day") == "night" else "—", 4),
            (round(float(r["day_credit"] or 0), 3), 5),
            (r["extra_minutes"], 4),
            (r["pay_amount"], 4),
            (r["excused_minutes"], 4),
            (r["note"] or "", 4),
            (" • ".join(flag) if flag else ("Дууссан" if r["clock_out"] else "Ажиллаж байна"), 4),
        ])

    return write_xlsx([
        {"name": "Сарын тайлан", "cols": widths, "rows": rows, "freeze": "A4"},
        {"name": "Өдрийн дэлгэрэнгүй",
         "cols": [30, 12, 10, 11, 11, 15, 14, 15, 15, 15, 12, 11, 14, 15, 14, 12, 12, 24, 18],
         "rows": detail_rows, "freeze": "A1"},
    ])


def build_payroll_xlsx(month: str) -> bytes:
    """Цалингийн тооцооны Excel — Цалин / Чөлөө / Ажлын байр гэсэн 3 хуудастай."""
    pr = monthly_payroll(month)
    s = get_settings()
    t = pr["totals"]
    C = pr["currency"]
    rows = [
        [(f"{pr['company_name']} — Цалингийн тооцоо ({pr['month_label']})", 1)],
        [(f"Үүсгэсэн: {pr['generated_at']}     Шөнийн ээлж: {pr['rules']['night_start']}-"
          f"{pr['rules']['night_end']} (хамгаалалт {pr['rules']['guard_percent']:.0f}%, "
          f"ажилчин {pr['rules']['worker_percent']:.0f}%)     "
          f"Тасралтын торгууль: дараалан {pr['rules']['absence_penalty_days']} хоног → "
          f"−{pr['rules']['absence_penalty_percent']:.0f}%", 2)],
        [],
    ]
    header = ["№", "Код", "Ажилтны нэр", "Албан тушаал", "Ажлын байр", "Өдрийн цалин (₮)",
              "Ирсэн өдөр", "Хөдөлмөрийн өдөр", "Шөнийн ээлж", "Нэмэлт цаг (ц)",
              "Үндсэн цалин (₮)", "Нэмэлт цагийн цалин (₮)", "Цалинтай чөлөө (₮)",
              "Тасарсан өдөр", "Дараалал", f"Торгууль (₮, −{t and pr['rules']['absence_penalty_percent']:.0f}%)",
              f"ОЛГОХ ЦАЛИН ({C})", "Төлөв"]
    rows.append([(h, 3) for h in header])
    for i, r in enumerate(pr["rows"], start=1):
        base = 4
        rows.append([
            (i, base), (r["code"], base), (r["full_name"], base), (r["position"], base),
            (r["site_name"], base),
            (r["daily_rate"], 4), (r["days_worked"], base), (r["day_credit"], 5),
            (r["night_days"], 5), (r["extra_hours"], 5),
            (r["pay_base"], 4), (r["pay_extra"], 4), (r["leave_pay"], 4),
            (r["absent_days"], 6 if r["absent_days"] else base),
            (r["absent_streak"], 6 if r["absent_streak"] >= pr["rules"]["absence_penalty_days"] else base),
            (r["penalty"], 6 if r["penalty"] else base),
            (r["total"], 10 if r["penalty"] else 9),
            (r["pay_status"], 6 if r["penalty"] else base),
        ])
    rows.append([
        ("НИЙТ", 7), ("", 7), (f"{t['employees']} ажилтан", 7), ("", 7), ("", 7), ("", 7),
        (t["days_worked"], 7), (t["day_credit"], 8), (t["night_days"], 7), (t["extra_hours"], 7),
        (t["pay_base"], 7), (t["pay_extra"], 7), (t["leave_pay"], 7), ("", 7), ("", 7),
        (t["penalty"], 6), (t["total"], 7), ("", 7),
    ])
    rows.append([])
    rows.append([("Тайлбар: Шөнийн ээлж (19:00–03:00) нэг бүтэн ажлын өдөрт тооцогдоно — "
                  "хамгаалалт 50%, ажилчин 100% цалинтай. Чөлөө нь админаар батлагдсан "
                  "хүсэлтээр олгогдоно; хүлээгдэж буй хүсэлт нь тасалдлыг нөхөхгүй.", 2)])

    # --- Хуудас 2: чөлөө (нэг төрөл, хүсэлт → батлах урсгал) ---
    lv_rows = [[("Ажилтны нэр", 3), ("Төрөл", 3), ("Төлөв", 3), ("Эхлэх", 3), ("Дуусах", 3),
                ("Бүтэн өдөр", 3), ("Эхлэх цаг", 3), ("Дуусах цаг", 3), ("Цаг", 3),
                ("Цалинтай", 3), ("Хүсэлт илгээсэн", 3), ("Тэмдэглэл", 3)]]
    for lv in list_leaves(month):
        lv_rows.append([
            (f"{lv['code']} {lv['full_name']}", 4), (lv["kind"], 4),
            (lv.get("status_label") or "Батлагдсан", 4),
            (lv["start_date"], 4), (lv["end_date"] or lv["start_date"], 4),
            ("Тийм" if int(lv["all_day"]) else "Үгүй", 5 if int(lv["all_day"]) else 4),
            (lv["start_time"] or "", 4), (lv["end_time"] or "", 4), (lv["hours"], 6),
            ("Тийм" if int(lv.get("paid") or 0) else "Үгүй", 4),
            ("Ажилтан" if str(lv.get("requested_by") or "") == "employee" else "Админ", 4),
            (lv["note"] or "", 4),
        ])

    # --- Хуудас 3: ажлын байр (талбай) ---
    site_rows = [[("Ажлын байр", 3), ("Хаяг", 3), ("Өргөрөг", 3), ("Уртраг", 3),
                  ("Радиус (м)", 3), ("Ажилтны тоо", 3)]]
    with connect() as con:
        sites = con.execute("SELECT * FROM sites ORDER BY id").fetchall()
        counts = {r["site_id"]: r["n"] for r in con.execute(
            "SELECT site_id, COUNT(*) n FROM employees WHERE active=1 GROUP BY site_id").fetchall()}
    for st in sites:
        site_rows.append([(st["name"], 4), (st["address"] or "", 4), (st["lat"], 4),
                          (st["lng"], 4), (st["radius_m"], 6), (counts.get(st["id"], 0), 4)])

    return write_xlsx([
        {"name": "Цалин", "cols": [5, 10, 26, 22, 26, 15, 12, 16, 12, 13, 16, 20, 18, 13, 11, 16, 18, 20],
         "rows": rows, "freeze": "A4"},
        {"name": "Чөлөө", "cols": [30, 10, 14, 12, 12, 12, 12, 12, 10, 11, 16, 28],
         "rows": lv_rows, "freeze": "A1"},
        {"name": "Ажлын байр", "cols": [34, 30, 13, 13, 12, 12],
         "rows": site_rows, "freeze": "A1"},
    ])
