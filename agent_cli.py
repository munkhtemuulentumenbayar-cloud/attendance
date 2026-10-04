#!/usr/bin/env python3
"""
Цаг бүртгэлийн систем — AI агент / автоматжуулалтын CLI
========================================================
Хамааралгүй (stdlib only) команд мөрийн хэрэгсэл. AI агент, cron job,
эсвэл shell скриптээс шууд дуудахад тохиромжтой.

Жишээ:
  python3 agent_cli.py status
  python3 agent_cli.py vision --date 2026-10-04
  python3 agent_cli.py who --code EMP005
  python3 agent_cli.py clock-in --code EMP005 --lat 47.9184 --lng 106.9177
  python3 agent_cli.py clock-out --code EMP005 --lat 47.9184 --lng 106.9177
  python3 agent_cli.py report --month 2026-09
  python3 agent_cli.py late-check          # цаг тутам cron-д тавихад тохиромжтой
  python3 agent_cli.py export --month 2026-09 --out timesheet.xlsx

Тохиргоо (env):
  ATTENDANCE_URL      default http://localhost:8000
  ATTENDANCE_API_KEY  default att_demo_agent_key_2026
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("ATTENDANCE_URL", "http://localhost:8000").rstrip("/")
KEY = os.environ.get("ATTENDANCE_API_KEY", "att_demo_agent_key_2026")

OK = "\033[92m", "\033[91m", "\033[93m", "\033[0m"


def call(path: str, method: str = "GET", body: dict | None = None, raw: bool = False):
    url = BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-API-Key", KEY)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            payload = res.read()
            return payload if raw else json.loads(payload.decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode("utf-8"))
            print(f"{OK[1]}Алдаа ({e.code}): {err.get('error', e.reason)}{OK[3]}", file=sys.stderr)
        except Exception:
            print(f"{OK[1]}Алдаа ({e.code}): {e.reason}{OK[3]}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{OK[1]}Серверт холбогдож чадсангүй ({url}): {e.reason}{OK[3]}", file=sys.stderr)
        sys.exit(2)


def flag(row: dict) -> str:
    tags = []
    if row.get("late_minutes"):
        tags.append(f"{OK[1]}ХОЦОРСОН +{row['late_minutes']}м{OK[3]}")
    if row.get("early_minutes"):
        tags.append(f"{OK[2]}ЭРТ ЯВСАН −{row['early_minutes']}м{OK[3]}")
    return " ".join(tags)


# ------------------------------------------------------------------ командууд
def cmd_status(a):
    b = call(f"/api/agent/status?date={a.date}" if a.date else "/api/agent/status")
    meta = call("/api/meta")
    s = b["summary"]
    geo = meta["geofence"]
    print(f"\n=== ИРЦИЙН САМБАР — {b['date']} ({b['weekday_mn']}) ===")
    print(f"Байгууллага: {meta['company_name']} | Ажлын хуваарь: "
          f"{b['schedule']['start']}–{b['schedule']['end']} | "
          f"Гео хаалт: {'идэвхтэй — ' + geo['name'] + ' (' + str(int(geo['radius_m'])) + ' м)' if geo['enabled'] else 'идэвхгүй'}")
    print(f"Нийт {s['total']} | Ажиллаж байна {s['working']} | Хоцорсон {s['late']} | "
          f"Ирээгүй {s['absent']} | Эрт явсан {s['early']} | Дууссан {s['done']}\n")
    print(f"{'Код':<9}{'Ажилтны нэр':<26}{'Ирсэн':<8}{'Явсан':<8}{'Ажилласан':<12}{'Төлөв'}")
    print("-" * 96)
    for e in b["employees"]:
        print(f"{e['code']:<9}{e['full_name'][:25]:<26}{e['clock_in_hm']:<8}{e['clock_out_hm']:<8}"
              f"{e['worked_hm']:<12}{e['status_label']}  {flag(e)}")
    return b


def cmd_vision(a):
    r = call(f"/api/agent/vision?date={a.date}" if a.date else "/api/agent/vision")
    print(r["text"])
    return r


def cmd_who(a):
    path = f"/api/agent/employee-status?employee_code={a.code}"
    if a.date:
        path += f"&date={a.date}"
    r = call(path)
    print(r["vision"])
    return r


def cmd_clock_in(a):
    r = call("/api/agent/clock-in", "POST", {
        "employee_code": a.code, "latitude": a.lat, "longitude": a.lng,
        "note": a.note or "", "demo_mode": bool(a.demo)})
    print(f"{OK[0]}✓{OK[3]} {r['message']}")
    print(r["vision"])
    return r


def cmd_clock_out(a):
    r = call("/api/agent/clock-out", "POST", {
        "employee_code": a.code, "latitude": a.lat, "longitude": a.lng,
        "note": a.note or "", "demo_mode": bool(a.demo)})
    print(f"{OK[0]}✓{OK[3]} {r['message']}")
    print(r["vision"])
    return r


def cmd_report(a):
    r = call(f"/api/agent/monthly-report?month={a.month}")
    t = r["totals"]
    print(f"\n=== {r['company_name']} — {r['month_label']}-ын цалингийн тайлан ===")
    print(f"Хугацаа: {r['period']} | Ажлын өдөр: {r['workdays_in_month']} | "
          f"Тайлан үүсгэсэн: {r['generated_at']}\n")
    head = f"{'Ажилтны нэр':<26}{'Ажилласан':>12}{'Хоцорсон тоо':>14}{'Хоцорсон мин':>14}{'Эрт явсан':>11}{'Хасагдсан мин':>15}{'Төлбөртэй':>12}"
    print(head)
    print("-" * len(head))
    for x in r["rows"]:
        print(f"{x['full_name'][:25]:<26}{x['worked_hm']:>12}{x['late_days']:>14}"
              f"{x['late_minutes']:>14}{x['early_days']:>11}{x['deduct_minutes']:>15}{x['payable_hm']:>12}")
    print("-" * len(head))
    print(f"{'НИЙТ':<26}{t['worked_hm']:>12}{t['late_days']:>14}{t['late_minutes']:>14}"
          f"{t['early_days']:>11}{t['deduct_minutes']:>15}{t['payable_hm']:>12}")
    print(f"\nТайлбар: Хасагдсан минут = Хоцролт + Эрт явсан. Төлбөртэй цаг = Ажилласан − Хасагдсан.")
    return r


def cmd_late_check(a):
    """cron-д тохиромжтой: хэт хоцорсон / ирээгүй ажилтнуудыг мэдэгдэнэ."""
    b = call("/api/agent/status")
    if not b["is_workday"]:
        print(f"{b['date']} нь амралтын өдөр ({b['weekday_mn']}). Шалгах шаардлагагүй.")
        return b
    late = [e for e in b["employees"] if e["late_minutes"] > 0]
    absent = [e for e in b["employees"] if e["status_code"] == "absent"]
    early = [e for e in b["employees"] if e["early_minutes"] > 0]
    print(f"[{b['server_time']}] {b['date']} — Хоцорсон {len(late)}, Ирээгүй {len(absent)}, Эрт явсан {len(early)}")
    for e in late:
        print(f"  ⚠ {e['code']} {e['full_name']}: {e['late_minutes']} минут хоцорсон (ирсэн {e['clock_in_hm']})")
    for e in absent:
        print(f"  🚫 {e['code']} {e['full_name']}: ирээгүй (бүртгэл байхгүй)")
    for e in early:
        print(f"  ⏱ {e['code']} {e['full_name']}: {e['early_minutes']} минутаар эрт явсан (явсан {e['clock_out_hm']})")
    if not (late or absent or early):
        print("  ✓ Зөрчил байхгүй — бүх ажилтан хуваарьт нийцсэн.")
    return b


def cmd_employees(a):
    r = call("/api/agent/directory")
    print(f"{'ID':<5}{'Код':<9}{'Ажилтны нэр':<28}{'Хэлтэс':<24}{'Албан тушаал'}")
    print("-" * 100)
    for e in r["employees"]:
        print(f"{e['id']:<5}{e['code']:<9}{e['full_name'][:27]:<28}{(e['department'] or '')[:23]:<24}{e['position']}")
    return r


def cmd_export(a):
    data = call(f"/api/agent/export/monthly.xlsx?month={a.month}", raw=True)
    out = a.out or f"timesheet_{a.month}.xlsx"
    with open(out, "wb") as f:
        f.write(data)
    print(f"{OK[0]}✓{OK[3]} Excel тайлан хадгалагдлаа: {out} ({len(data)} байт)")
    return out


def cmd_geofence(a):
    r = call("/api/agent/geofence-check", "POST", {"latitude": a.lat, "longitude": a.lng})
    if r["ok"]:
        print(f"{OK[0]}✓{OK[3]} Ажлын байрандаа байна ({r['distance_m']} м / зөвшөөрөгдөх {r['radius_m']} м)")
    else:
        print(f"{OK[1]}✗{OK[3]} {r['message']} (зай: {r['distance_m']} м)")
    return r


def main():
    p = argparse.ArgumentParser(description="Цаг бүртгэлийн системийн AI агентын CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status", help="Ирцийн шууд самбар")
    s.add_argument("--date"); s.set_defaults(func=cmd_status)

    s = sub.add_parser("vision", help="Агентад зориулсан текстэн төлөв")
    s.add_argument("--date"); s.set_defaults(func=cmd_vision)

    s = sub.add_parser("who", help="Нэг ажилтны төлөв")
    s.add_argument("--code", required=True); s.add_argument("--date"); s.set_defaults(func=cmd_who)

    s = sub.add_parser("clock-in", help="Ажилд орох бүртгэл")
    s.add_argument("--code", required=True); s.add_argument("--lat", type=float, required=True)
    s.add_argument("--lng", type=float, required=True); s.add_argument("--note", default="")
    s.add_argument("--demo", action="store_true", help="GPS-гүй туршилтын горим")
    s.set_defaults(func=cmd_clock_in)

    s = sub.add_parser("clock-out", help="Ажлаас буух бүртгэл")
    s.add_argument("--code", required=True); s.add_argument("--lat", type=float, required=True)
    s.add_argument("--lng", type=float, required=True); s.add_argument("--note", default="")
    s.add_argument("--demo", action="store_true")
    s.set_defaults(func=cmd_clock_out)

    s = sub.add_parser("report", help="Сарын цалингийн тайлан")
    s.add_argument("--month", required=True); s.set_defaults(func=cmd_report)

    s = sub.add_parser("late-check", help="Хоцролт/ирээгүй/эрт явсан шалгалт (cron)")
    s.set_defaults(func=cmd_late_check)

    s = sub.add_parser("employees", help="Ажилтны жагсаалт")
    s.set_defaults(func=cmd_employees)

    s = sub.add_parser("export", help="Excel тайлан татах")
    s.add_argument("--month", required=True); s.add_argument("--out"); s.set_defaults(func=cmd_export)

    s = sub.add_parser("geofence", help="Байршлыг гео хаалттай шалгах")
    s.add_argument("--lat", type=float, required=True); s.add_argument("--lng", type=float, required=True)
    s.set_defaults(func=cmd_geofence)

    a = p.parse_args()
    if getattr(a, "month", None) is None and a.cmd in ("report", "export"):
        from datetime import datetime
        a.month = datetime.now().strftime("%Y-%m")
    a.func(a)


if __name__ == "__main__":
    main()
