#!/usr/bin/env python3
"""
Барилгын бригадын демо өгөгдлийг дахин үүсгэнэ:
талаб (sites) → ажилтны цалин/ээлж/талбай → 8 долоо хоногийн ирц →
чөлөө (нэг төрөл, хүсэлт → батлах) → нэмэлт цаг → өнөөдрийн самбарын төлөв.

Ажиллагаа: python3 reseed_demo.py [--no-backup]
"""
from __future__ import annotations

import base64
import shutil
import sys
from pathlib import Path
from datetime import date, datetime, time, timedelta

import core

KEEP_TODAY = True


# Жижиг JPEG (демо зураг) — бодит системд утасны камераар авсан зураг орно
DEMO_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAAKAAgBAREA/8QAFAABAAAAAAAA"
    "AAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q==")


def attach_demo_photos(days: int = 8) -> int:
    """Сүүлийн `days` ажлын өдрийн бүртгэлд демо зураг хавсаргана."""
    import os
    from datetime import date as _date, timedelta as _td
    today = core.today_str()
    since = (_date.fromisoformat(today) - _td(days=days)).isoformat()
    out_dir = os.path.join(core.DATA_DIR, "photos", today[:7])
    os.makedirs(out_dir, exist_ok=True)
    n = 0
    with core.connect() as con:
        rows = [dict(r) for r in con.execute(
            "SELECT id, employee_id, work_date, clock_in, clock_out, in_photo, out_photo"
            " FROM attendance WHERE work_date >= ? AND clock_in IS NOT NULL ORDER BY work_date",
            (since,)).fetchall()]
        for r in rows:
            sets, vals = [], []
            for kind, ts in (("in", r["clock_in"]), ("out", r["clock_out"])):
                if not ts:
                    continue
                col = f"{kind}_photo"
                if r.get(col):
                    continue
                name = f"{int(r['employee_id']):03d}_{r['work_date'].replace('-','')}_{kind}.jpg"
                with open(os.path.join(out_dir, name), "wb") as f:
                    f.write(DEMO_JPEG)
                sets += [f"{col}=?", f"{kind}_photo_ts=?"]
                vals += [f"photos/{today[:7]}/{name}", ts]
                n += 1
            sets.append("photo_source=?")
            vals.append("demo")
            vals.append(r["id"])
            con.execute(f"UPDATE attendance SET {', '.join(sets)} WHERE id=?", vals)
        con.commit()
    return n


def main() -> None:
    db = Path(core.DB_PATH)
    backup = None
    if "--no-backup" not in sys.argv and db.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = db.with_name(f"attendance_backup_{stamp}.db")
        shutil.copy2(db, backup)
        print(f"Нөөц хуулбар: {backup.name}")

    core.init_db(seed=False)
    # Тохиргоог эхлээд тогтооно (ажлын өдрүүд seed-д нөлөөлнө)
    core.set_settings({
        "workdays": "1,2,3,4,5,6",
        "company_name": "Барилгын Бригад ХХК",
        "absence_penalty_days": "3",
        "absence_penalty_percent": "10",
        "guard_percent": "50",
        "worker_percent": "100",
        "overtime_multiplier": "1.0",
        "paid_leave_kinds": "",           # v3.1: нэг төрөл «чөлөө», цалинтай эсэх нь paid=0/1
        "leave_request_notify": "1",      # ажилтны хүсэлт → админд мэдэгдэл
        "absent_minutes_grace": "10",     # 10 мин-ээс дээш зөвшөөрөлгүй тасалдал → «ирээгүй»
        "grace_minutes": "10",           # 10 минутын хөнгөлөлт
    })

    with core._lock, core.connect() as con:
        con.execute("DELETE FROM attendance")
        con.execute("DELETE FROM leaves")
        con.execute("DELETE FROM work_segments")     # v3: нэмэлт ажлын сегмент
        con.execute("DELETE FROM advances")         # v4.5: авансын бүртгэл
        con.execute("DELETE FROM notifications")    # v3: мэдэгдэл
        con.execute("UPDATE employees SET site_id=NULL")
        con.execute("DELETE FROM sites")
        stamp = core.now_local().strftime("%Y-%m-%d %H:%M:%S")

        site_ids = []
        for name, addr, lat, lng, radius in core.SEED_SITES:
            cur = con.execute(
                "INSERT INTO sites(name, address, lat, lng, radius_m, active, created_at)"
                " VALUES(?,?,?,?,?,1,?)", (name, addr, lat, lng, radius, stamp))
            site_ids.append(cur.lastrowid)

        for code, name, dept, pos, rate, role, site_no in core.SEED_EMPLOYEES:
            sid = site_ids[site_no - 1] if site_no else None
            con.execute(
                "UPDATE employees SET full_name=?, department=?, position=?, daily_rate=?,"
                " night_role=?, site_id=?, active=1 WHERE code=?",
                (name, dept, pos, rate, role, sid, code))
        # v4.3: гео хаалтын горимыг анхдагч (талбайгаа дагах) болгож, демо тохиолдлуудыг онооно
        con.execute("UPDATE employees SET geofence_mode='site', geo_lat=NULL, geo_lng=NULL,"
                    " geo_radius_m=NULL")
        for code, g in core.SEED_GEOFENCE.items():
            con.execute("UPDATE employees SET geofence_mode=?, geo_lat=?, geo_lng=?,"
                        " geo_radius_m=? WHERE code=?",
                        (g.get("geofence_mode", "site"), g.get("geo_lat"), g.get("geo_lng"),
                         g.get("geo_radius_m"), code))
        con.commit()

        # 8 долоо хоногийн ирц + төлөвлөсөн демо тохиолдлууд
        core._seed_demo_data(con)
        con.commit()

    # --- v4.5: авансын демо ---
    # 1) EMP012 (туслах ажилчин): 11–24 цонхонд зөвхөн 7 БҮТЭН өдөртэй болгож,
    #    «7 хоногоос дээш ажиллаагүй → 25-нд аванс авахгүй» жишээг бий болгоно.
    pkey = core.period_key_for()
    w_start, w_end = core.pay_period_bounds(pkey)["advance_window"]
    with core._lock, core.connect() as con:
        emp12 = con.execute("SELECT id FROM employees WHERE code='EMP012'").fetchone()
        if emp12:
            rows = [dict(r) for r in con.execute(
                "SELECT work_date, clock_in, day_credit FROM attendance"
                " WHERE employee_id=? AND work_date BETWEEN ? AND ? AND clock_in IS NOT NULL"
                " ORDER BY work_date", (emp12["id"], w_start, w_end)).fetchall()]
            wd = core.period_workdays(w_start, w_end)
            idx = {d: i for i, d in enumerate(wd)}
            picked, last = [], -9            # зэрэгцээ өдрүүдийг алгасна (тасралтын цуваа үүсэхгүй)
            for r in rows:
                if float(r["day_credit"] or 0) < core.full_day_credit_min():
                    continue
                i = idx.get(r["work_date"], -99)
                if i - last < 2:
                    continue
                picked.append(r["work_date"])
                last = i
                if len(picked) == 4:
                    break
            for d in picked:                  # 4 бүтэн өдрийг «4 цаг ажиллаад явсан» болгоно
                con.execute("UPDATE attendance SET clock_out=? || ' 13:05:00'"
                            " WHERE employee_id=? AND work_date=?",
                            (d, emp12["id"], d))
            print("Демо: EMP012-ын богиносгосон өдрүүд —", ", ".join(picked))
            con.commit()
    core.recalc_all()          # богиносгосон өдрүүд тооцоологдсоны дараа эрхийг шалгана
    # 2) 25-нд олгосон авансууд (EMP011 — хараахан олгоогүй, хүлээгдэж байна)
    adv_seed = core.demo_seed_advances(pkey)
    print(f"Демо аванс: {adv_seed['count']} ажилтанд {core.fmt_money(adv_seed['total'])}₮ "
          f"({adv_seed['paid_on']}-нд олгосон) · EMP011 хүлээгдэж байна")

    # Нэмэлт цаг (админ гараар нэмсэн) — ЭРДЭНЭБАТ +3ц, ГАНБААТАР +2.5ц
    core.set_extra_hours(core.get_employee_by_code("EMP003")["id"], "2026-10-02", 3.0,
                         note="Шөнийн цемент ачилт")
    core.set_extra_hours(core.get_employee_by_code("EMP005")["id"], "2026-10-03", 2.5,
                         note="Нэмэлт ажил")

    # Өнөөдрийн самбар (демо төлөвүүд)
    if KEEP_TODAY:
        core.demo_seed_today(force_workday=True)

    # v3.1: хүлээгдэж буй хүсэлтүүдэд мэдэгдэл үүсгэнэ (админ батлах ёстой)
    for p in core.pending_leave_requests():
        core.notify_admins("leave_request",
                           f"ЧӨЛӨӨНИЙ ХҮСЭЛТ — {p['code']} {p['full_name']}",
                           f"{p['start_date']}→{p.get('end_date') or p['start_date']} "
                           f"({p['hours']}ц). Хүсэлтийг батлах эсвэл татгалзана уу."
                           + (f" Тэмдэглэл: {p['note']}" if p.get("note") else ""),
                           meta={"leave_id": p["id"], "employee_id": p["employee_id"],
                                 "code": p["code"]},
                           dedupe=f"leave_req_{p['id']}")
        core.notify(p["employee_id"], "leave_request", "Чөлөөний хүсэлт илгээгдлээ",
                    f"{p['start_date']}→{p.get('end_date') or p['start_date']} ({p['hours']}ц). "
                    "Админ баталсны дараа хүчинтэй болно — батлагдах хүртэл тухайн цаг/өдөр "
                    "«ирээгүй» хэвээр тооцогдоно.",
                    meta={"leave_id": p["id"], "status": "pending"},
                    dedupe=f"leave_sent_{p['id']}")

    # Демо зураг: сүүлийн хэдэн өдрийн бүртгэлд зураг хавсаргана (v3)
    demo_photos = attach_demo_photos()
    print(f"Демо зураг хавсаргасан бүртгэл: {demo_photos}")

    n = core.recalc_all()
    print(f"Дахин тооцоолсон бүртгэл: {n}")

    # --- Шалгалт ---
    print("\n== Талбай ==")
    for s in core.list_sites():
        print(f"  #{s['id']} {s['name']} r={s['radius_m']:.0f}м ({s['lat']}, {s['lng']})")
    print("\n== Ажилтан ба цалин ==")
    for e in core.list_employees():
        site = core.employee_site(e) or {}
        print(f"  {e['code']} {e['full_name']:<24} {e['position']:<22} "
              f"{int(e['daily_rate']):>7,}₮ {e['night_role']:<6} {site.get('name','—')}")
    print("\n== Чөлөө (нэг төрөл) ==")
    for lv in core.list_leaves():
        span = lv["start_date"] if lv["start_date"] == lv["end_date"] else f"{lv['start_date']}→{lv['end_date']}"
        when = "бүтэн өдөр" if int(lv["all_day"]) else f"{lv['start_time']}–{lv['end_time']}"
        print(f"  {lv['code']} {span:<24} {when:<16} {lv['hours']:>5.1f}ц  "
              f"[{lv['status']:<9}] цалинтай={lv['paid']}  {lv['note']}")
    print("\n== Хүлээгдэж буй хүсэлт ==")
    for p in core.pending_leave_requests():
        print(f"  {p['code']} {p['start_date']}→{p.get('end_date') or p['start_date']} "
              f"{p['hours']}ц — админ батлах шаардлагатай")
    for month in ("2026-09", "2026-10"):
        pr = core.monthly_payroll(month)
        t = pr["totals"]
        print(f"\n== Цалин {month} ({t['employees']} ажилтан) ==")
        print(f"  Үндсэн {core.fmt_money(t['pay_base'])}₮ + Нэмэлт {core.fmt_money(t['pay_extra'])}₮ "
              f"+ Чөлөө {core.fmt_money(t['leave_pay'])}₮ − Торгууль {core.fmt_money(t['penalty'])}₮ "
              f"= НИЙТ {core.fmt_money(t['total'])}₮")
        for r in pr["rows"]:
            print(f"  {r['code']:<7} {r['day_credit']:>5.2f} өдөр  шөнө:{r['night_days']} "
                  f"нэмэлт:{r['extra_hours']:>4.1f}ц  чөлөө:{r['leave_hours']:>5.1f}ц  "
                  f"ирээгүй:{r['absent_days']} өдөр/{r['absent_hours']:>4.1f}ц "
                  f"(дараалал {r['absent_streak']})  −{core.fmt_money(r['penalty']):>7}₮  "
                  f"= {core.fmt_money(r['total']):>9}₮  [{r['pay_status']}]")


if __name__ == "__main__":
    main()
