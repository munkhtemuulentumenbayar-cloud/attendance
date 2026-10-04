#!/usr/bin/env python3
"""
OpenAPI 3.0 тодорхойлолт үүсгэгч (openapi.json).
Ажиллуулах: python3 make_openapi.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def op(tags, summary, params=None, body=None, responses=None, security=None, desc=None):
    o = {"tags": tags, "summary": summary}
    if desc:
        o["description"] = desc
    if security is not None:
        o["security"] = security
    if params:
        o["parameters"] = params
    if body is not None:
        o["requestBody"] = {"required": True, "content": {"application/json": {"schema": body}}}
    o["responses"] = responses or {"200": {"description": "Амжилттай"}}
    return o


def q(name, typ="string", required=False, fmt=None, example=None):
    s = {"type": typ}
    if fmt:
        s["format"] = fmt
    if example is not None:
        s["example"] = example
    return {"name": name, "in": "query", "required": required, "schema": s}


def p(name, typ="string"):
    return {"name": name, "in": "path", "required": True, "schema": {"type": typ}}


def objschema(**props):
    return {"type": "object", "properties": props}


def json200(desc, schema=None, example=None):
    """200 хариултын тодорхойлолт — гүнзгий curly хаалт хэрэглэхгүй."""
    inner = {"schema": schema} if schema is not None else {"example": example}
    return {"200": {"description": desc, "content": {"application/json": inner}}}


ERR = {"$ref": "#/components/schemas/Error"}
AGENT = [{"ApiKeyAuth": []}]
REC = {"$ref": "#/components/schemas/AttendanceRecord"}
EMP = {"$ref": "#/components/schemas/Employee"}

GEOFENCE_ERR_RESP = {
    "200": {"description": "Бүртгэл амжилттай"},
    "422": {
        "description": "Гео хаалтад хаагдлаа: «Та ажлын байрандаа байхгүй байна. Бүртгэл амжилтгүй.»",
        "content": {"application/json": {"schema": ERR,
                                         "example": {"ok": False,
                                                     "error": "Та ажлын байрандаа байхгүй байна. Бүртгэл амжилтгүй."}}}},
}

BOARD_SCHEMA = objschema(
    date={"type": "string"}, weekday_mn={"type": "string"}, is_workday={"type": "boolean"},
    is_today={"type": "boolean"}, demo_data={"type": "boolean"}, last_workday={"type": "string"},
    server_time={"type": "string"}, schedule={"type": "object"},
    summary=objschema(total={"type": "integer"}, working={"type": "integer"}, late={"type": "integer"},
                      absent={"type": "integer"}, early={"type": "integer"}, done={"type": "integer"}),
    employees={"type": "array", "items": {"$ref": "#/components/schemas/BoardRow"}})

MONTHLY_ROW = objschema(
    code={"type": "string"},
    full_name={"type": "string", "description": "Ажилтны нэр"},
    department={"type": "string"},
    worked_hours={"type": "number", "description": "Нийт ажилласан цаг (тоо)"},
    worked_hm={"type": "string", "description": "Нийт ажилласан цаг (ц:мм)", "example": "168:58"},
    late_days={"type": "integer", "description": "Нийт хоцорсон тоо"},
    late_minutes={"type": "integer", "description": "Нийт хоцорсон минут"},
    early_days={"type": "integer", "description": "Нийт эрт явсан тоо"},
    early_minutes={"type": "integer"}, deduct_minutes={"type": "integer", "description": "Хасагдсан нийт минут"},
    payable_hm={"type": "string", "description": "Төлбөртэй цаг", "example": "155:50"},
    absent_days={"type": "integer"})

MONTHLY_SCHEMA = objschema(
    month_label={"type": "string"}, period={"type": "string"}, workdays_in_month={"type": "integer"},
    rows={"type": "array", "items": MONTHLY_ROW}, totals={"type": "object"})

PATHS = {
    "/api/health": {"get": op(["Нээлттэй"], "Системийн төлөв", security=[],
                              responses={"200": {"description": "Сервер ажиллаж байна"}})},
    "/api/meta": {"get": op(["Нээлттэй"], "Ажлын хуваарь, гео хаалт, байгууллагын тохиргоо",
                            security=[],
                            responses={"200": {"description": "Тохиргооны хураангуй",
                                               "content": {"application/json": {"example": {
                                                   "company_name": "Жишээ ХХК",
                                                   "timezone": "Asia/Ulaanbaatar",
                                                   "schedule": {"start": "09:00", "end": "19:00", "grace_minutes": 10, "lunch_start": "13:00", "lunch_end": "14:00", "lunch_paid": True, "paid_minutes_per_day": 600, "paid_hours_per_day": 10.0, "night_start": "19:00", "night_end": "03:00", "night_minutes": 480, "night_hours": 8.0},
                                                   "workdays": [1, 2, 3, 4, 5],
                                                   "workdays_label": "Даваа, Мягмар, Лхагва, Пүрэв, Баасан",
                                                   "geofence": {"enabled": True, "name": "Төв оффис", "radius_m": 300},
                                                   "demo_mode": True,
                                                   "status_labels": {"not_checked_in": "Бүртгүүлээгүй",
                                                                     "working": "Ажиллаж байна",
                                                                     "done": "Ажил дууссан"}}}}}})},
    "/api/auth/employee-login": {"post": op(
        ["Нээлттэй"], "Ажилтны нэвтрэлт (ажилтны код + ПИН)", security=[],
        body=objschema(code={"type": "string", "example": "EMP001"},
                       pin={"type": "string", "example": "1234"}),
        responses={"200": {"description": "Сесс үүслээ (att_session cookie + token)"},
                   "401": {"description": "Ажилтны код эсвэл ПИН буруу"}})},
    "/api/auth/admin-login": {"post": op(
        ["Нээлттэй"], "Удирдлагын нэвтрэлт", security=[],
        body=objschema(username={"type": "string", "example": "admin"},
                       password={"type": "string", "example": "admin123"}),
        responses={"200": {"description": "Сесс үүслээ"}, "401": {"description": "Нэр эсвэл нууц үг буруу"}})},
    "/api/auth/logout": {"post": op(["Нээлттэй"], "Системээс гарах", security=[])},
    "/api/auth/me": {"get": op(["Ажилтан", "Удирдлага"], "Одоогийн хэрэглэгчийн мэдээлэл",
                               responses={"200": {"description": "Хэрэглэгч"},
                                          "401": {"description": "Нэвтрээгүй"}})},
    "/api/employee/today": {"get": op(
        ["Ажилтан"], "Өнөөдрийн төлөв — ирсэн/явсан цаг, ажилласан хугацаа, хоцролт",
        params=[q("date", fmt="date")],
        responses={"200": {"description": "Ажилтны өдрийн самбар", "content": {"application/json": {"example": {
            "status_code": "working", "status_label": "Ажиллаж байна",
            "schedule": {"start": "09:00", "end": "19:00", "grace_minutes": 10, "lunch_start": "13:00", "lunch_end": "14:00", "lunch_paid": True, "paid_minutes_per_day": 600, "paid_hours_per_day": 10.0, "night_start": "19:00", "night_end": "03:00", "night_minutes": 480, "night_hours": 8.0},
            "record": {"clock_in_hm": "09:12", "clock_out_hm": "—", "late_minutes": 12,
                       "worked_hm": "0ц 00м", "payable_hm": "0ц 00м", "deduct_minutes": 12},
            "vision": "Ажилтан: Батбаяр Дорж (EMP001)…"}}}},
            "401": {"description": "Нэвтрэх шаардлагатай"}})},
    "/api/employee/clock-in": {"post": op(
        ["Ажилтан"], "Ажилд орох бүртгэл (Ирсэн цаг) — гео хаалт шалгана",
        body=objschema(latitude={"type": "number", "example": 47.9184},
                       longitude={"type": "number", "example": 106.9177},
                       accuracy={"type": "number", "description": "GPS нарийвчлал (м)"},
                       note={"type": "string"},
                       demo_mode={"type": "boolean",
                                  "description": "GPS байхгүй үед туршилтын горим (зөвхөн demo_mode=1 тохиргоотой үед)"}),
        responses=GEOFENCE_ERR_RESP)},
    "/api/employee/clock-out": {"post": op(
        ["Ажилтан"], "Ажлаас буух бүртгэл (Явсан цаг) — эрт явалтыг тооцно",
        body=objschema(latitude={"type": "number"}, longitude={"type": "number"},
                       accuracy={"type": "number"}, note={"type": "string"},
                       demo_mode={"type": "boolean"}),
        responses=GEOFENCE_ERR_RESP)},
    "/api/employee/history": {"get": op(
        ["Ажилтан"], "Сарын бүртгэлийн түүх ба нэгдсэн дүн",
        params=[q("month", required=True, example="2026-09")],
        responses={"200": {"description": "Бүртгэлүүд, нийт ажилласан цаг, хоцролт, хасагдсан минут"}})},
    "/api/geo/check": {"get": op(
        ["Ажилтан", "Удирдлага"], "Байршлыг ажлын байрны хүрээтэй харьцуулах",
        params=[q("lat", "number", True), q("lng", "number", True)],
        responses={"200": {"description": "ok=true → хүрээнд; ok=false → «Та ажлын байрандаа байхгүй байна…»",
                           "content": {"application/json": {"example": {
                               "ok": True, "enabled": True, "distance_m": 42.7, "radius_m": 300.0,
                               "message": ""}}}}})},
    "/api/admin/board": {"get": op(
        ["Удирдлага", "AI Agent"], "Ирцийн шууд самбар — хэн ажиллаж байна, хэн хоцорсон, хэн ирээгүй",
        params=[q("date", fmt="date")],
        responses=json200("Самбар", BOARD_SCHEMA))},
    "/api/admin/daily": {"get": op(
        ["Удирдлага"], "Тухайн өдрийн дэлгэрэнгүй бүртгэл + ирээгүй ажилтнууд",
        params=[q("date", fmt="date")])},
    "/api/admin/monthly": {"get": op(
        ["Удирдлага", "AI Agent"],
        "Сарын цалингийн тайлан — Ажилтны нэр, Нийт ажилласан цаг, Нийт хоцорсон тоо, Хасагдсан нийт минут",
        params=[q("month", required=True, example="2026-09")],
        responses=json200("Тайлан", MONTHLY_SCHEMA))},
    "/api/admin/matrix": {"get": op(
        ["Удирдлага"], "Сар бүрийн өдөр тутмын ирцийн матриц (heatmap)",
        params=[q("month", required=True, example="2026-09")])},
    "/api/admin/employees": {
        "get": op(["Удирдлага"],
                  "Ажилтны жагсаалт + тохиргоо + ажилтан бүрийн гео хаалтын горим (v4.3)"),
        "post": op(["Удирдлага"], "Шинэ ажилтан бүртгэх",
                   body=objschema(code={"type": "string"}, full_name={"type": "string"},
                                  department={"type": "string"}, position={"type": "string"},
                                  pin={"type": "string"}),
                   responses={"200": {"description": "Бүртгэгдлээ"},
                              "409": {"description": "Энэ кодтой ажилтан байна"}})},
    "/api/admin/employees/{eid}": {"put": op(
        ["Удирдлага"], "Ажилтны мэдээлэл засах (нэр, албан тушаал, өдрийн цалин, талбай, рампа…)",
        params=[p("eid", "integer")],
        body=objschema(full_name={"type": "string"}, department={"type": "string"},
                       position={"type": "string"}, pin={"type": "string"},
                       active={"type": "integer", "enum": [0, 1]},
                       geofence_mode={"type": "string", "enum": ["site", "custom", "off"],
                                      "description": "v4.3 — ажилтны гео хаалтын горим"}))},
    "/api/admin/employees/{eid}/geofence": {"put": op(
        ["Ажлын байр"],
        "Ажилтан бүрийн гео хаалтыг тохируулах (v4.3) — талбайгаа дагах | өөрийн байршил | идэвхгүй",
        params=[p("eid", "integer")],
        body=objschema(mode={"type": "string", "enum": ["site", "custom", "off"],
                             "example": "custom",
                             "description": "site — оноосон талбай/үндсэн; custom — өөрийн lat/lng + радиус; "
                                            "off — хаалт хүчингүй (жолооч, хээрийн ажилтан)"},
                       lat={"type": "number", "example": 47.9184},
                       lng={"type": "number", "example": 106.9177},
                       radius_m={"type": "number", "example": 500,
                                 "description": "20–20 000 м (анхдагч 300 м)"}),
        responses={"200": {"description": "Хадгалагдлаа", "content": {"application/json": {"example": {
            "ok": True, "mode": "custom",
            "employee": {"id": 11, "code": "EMP011", "geofence_mode": "custom",
                         "geo_lat": 47.9184, "geo_lng": 106.9177, "geo_radius_m": 500},
            "geo": {"source": "custom", "mode": "custom", "radius_m": 500, "enabled": True},
            "message": "Дөлгөөн Алтанхуяг: өөрийн байршил 500 м радиустай гео хаалт тохируулагдлаа."}}}},
            "400": {"description": "Горим/координат/радиус буруу"},
            "404": {"description": "Ажилтан олдсонгүй"}})},
    "/api/admin/records": {"post": op(
        ["Удирдлага"], "Бүртгэлийг гараар засах/нэмэх (хоцролт, эрт явалт дахин тооцоологдоно)",
        body=objschema(employee_id={"type": "integer"}, date={"type": "string", "format": "date"},
                       clock_in={"type": "string", "example": "09:05"},
                       clock_out={"type": "string", "example": "17:50"},
                       note={"type": "string"}))},
    "/api/admin/settings": {
        "get": op(["Удирдлага"], "Тохиргоо (ажлын цаг, гео хаалт, үдийн завсарлага, админ)"),
        "put": op(["Удирдлага"],
                  "Тохиргоо хадгалах — хуваарьт нөлөөлөх утга өөрчлөгдвөл бүх бүртгэл дахин тооцоологдоно",
                  body=objschema(company_name={"type": "string"}, timezone={"type": "string", "example": "Asia/Ulaanbaatar"},
                                 schedule_start={"type": "string", "example": "09:00"},
                                 schedule_end={"type": "string", "example": "19:00"},
                                 lunch_paid={"type": "string", "example": "1",
                                             "description": "Үдийн завсарлага цалинтай эсэх (1/0)"},
                                 grace_minutes={"type": "string", "description": "Хөнгөлөх хугацаа (мин)"},
                                 lunch_deduct_minutes={"type": "string", "description": "Үдийн завсарлага (мин)"},
                                 workdays={"type": "string", "example": "1,2,3,4,5"},
                                 geofence_enabled={"type": "string", "enum": ["0", "1"]},
                                 geofence_name={"type": "string"}, geofence_lat={"type": "string"},
                                 geofence_lng={"type": "string"}, geofence_radius_m={"type": "string"},
                                 demo_mode={"type": "string", "enum": ["0", "1"]},
                                 admin_user={"type": "string"}, admin_password={"type": "string"},
                                 google_maps_api_key={"type": "string", "example": "AIza…",
                                                      "description": "Google Maps JS API түлхүүр (v4.2 — байршлыг зурагнаас сонгох)"}))},
    "/api/admin/recalc": {"post": op(
        ["Удирдлага"], "Бүх бүртгэлийг одоогийн ажлын хуваарийн дагуу дахин тооцоолох",
        body=objschema(month={"type": "string", "nullable": True}))},
    "/api/admin/geofence-check": {"get": op(
        ["Удирдлага"], "Гео хаалтын шалгалт (админ)",
        params=[q("lat", "number"), q("lng", "number")])},
    "/api/admin/geofence-log": {"get": op(
        ["Удирдлага"], "Гео хаалтаас болж амжилтгүй болсон оролдлогууд",
        responses={"200": {"description": "Зөрчлийн жагсаалт",
                           "content": {"application/json": {"example": {
                               "violations": [{"ts": "2026-10-04 19:13:23", "actor": "employee:1",
                                               "action": "clock_in_blocked",
                                               "detail": "Та ажлын байрандаа байхгүй байна. Бүртгэл амжилтгүй."}],
                               "message": "Та ажлын байрандаа байхгүй байна. Бүртгэл амжилтгүй."}}}}})},
    # ---------------- Цалин / чөлөө / ажлын байр (барилгын бригад) ----------------
    "/api/admin/payroll": {"get": op(
        ["Цалин"], "Сарын цалингийн тооцоо (ажилтан бүрээр)",
        params=[q("month", "string", example="2026-09")],
        desc="Өдрийн цалин × хөдөлмөрийн өдөр (шөнийн ээлж: хамгаалалт 50%, ажилчин 100%) "
             "+ нэмэлт цаг + цалинтай чөлөө − 3 хоног дараалан тасарсан бол 10% торгууль.")},
    "/api/admin/periods": {"get": op(
        ["Хоёр төлбөр"], "Үеүүдийн жагсаалт (10-ны цалингийн хугацаанууд) + авансын дүрэм",
        params=[q("n", "integer", example=6)],
        desc="Үе = «YYYY-MM» — тухайн сарын 10-нд олгогдох үндсэн цалин. "
             "Хугацаа: өмнөх сарын 11 → тухайн сарын 10. Авансын цонх: 11 → 24.")},
    "/api/admin/pay-cycle": {"get": op(
        ["Хоёр төлбөр"], "Хоёр төлбөрийн нэгдсэн хүснэгт (25-ны аванс + 10-ны үндсэн цалин)",
        params=[q("period", "string", example="2026-10")],
        desc="Ажилтан бүрээр: 11–24 цонхны бүтэн өдөр, авансын эрх ба төлөв, "
             "авансын дүн, 10-нд олгох үлдэгдэл (аванс хасагдсан).")},
    "/api/admin/period-payroll": {"get": op(
        ["Хоёр төлбөр"], "Үеийн үндсэн цалингийн тооцоо (11 → 10)",
        params=[q("period", "string", example="2026-10")],
        desc="Өдрийн цалин × бүтэн өдөр + нэмэлт цаг + цалинтай чөлөө − 10% торгууль "
             "− 25-нд олгосон аванс = 10-нд олгох дүн.")},
    "/api/admin/advances": {"get": op(
        ["Хоёр төлбөр"], "Авансын жагсаалт: хэн эрхтэй, хэн авсан, хэдэн төгрөг",
        params=[q("period", "string", example="2026-10")])},
    "/api/admin/advances/{eid}": {"get": op(
        ["Хоёр төлбөр"], "Нэг ажилтны авансын мэдээлэл",
        params=[p("eid", "integer"), q("period", "string", example="2026-10")])},
    "/api/admin/advances/pay": {"post": op(
        ["Хоёр төлбөр"], "25-ны авансыг «олгосон» гэж бүртгэх (10-ны цалингаас хасагдана)",
        body=objschema(employee_id={"type": "integer", "example": 1},
                       code={"type": "string", "example": "EMP001"},
                       period={"type": "string", "example": "2026-10"},
                       amount={"type": "number", "example": 1000000,
                               "description": "Хоосон бол дүрмийн дүн (11–24-нд ажилласан цалингаас хэтрэхгүй)"},
                       paid_on={"type": "string", "example": "2026-09-25"},
                       note={"type": "string"}),
        desc="Ажилтанд «Аванс олгогдлоо» мэдэгдэл очно; админууд мэдэгдэл авна; аудит бичлэг үүснэ.")},
    "/api/admin/advances/cancel": {"post": op(
        ["Хоёр төлбөр"], "Авансын бүртгэлийг цуцлах (10-ны цалин бүтнээр олгогдоно)",
        body=objschema(employee_id={"type": "integer"}, code={"type": "string"},
                       period={"type": "string", "example": "2026-10"}))},
    "/api/admin/advances/reset": {"post": op(
        ["Хоёр төлбөр"], "Авансын бичлэгийг анхны төлөвт буцаах (эрхтэй → «хүлээгдэж байна», эрхгүй → устгах)",
        body=objschema(employee_id={"type": "integer"}, code={"type": "string"},
                       period={"type": "string", "example": "2026-10"}))},
    "/api/employee/my-pay-cycle": {"get": op(
        ["Ажилтан"], "Өөрийн цалингийн хуанли: 25-ны аванс + 10-ны үндсэн цалин "
                     "(ЗӨВХӨН өөрийн мэдээлэл)",
        params=[q("period", "string", example="2026-10")],
        desc="Ажилтанд: аванс авах эрхтэй эсэх (11–24-нд хэдэн бүтэн өдөр ажилласан), "
             "аванс олгогдсон эсэх ба дүн, 10-нд олгох үлдэгдэл.")},
    "/api/admin/payroll-rules": {
        "get": op(["Цалин"], "Цалингийн дүрэм (шөнийн ээлж, хувь, торгууль, тасалдлын босго, мэдэгдэл)"),
        "put": op(["Цалин"], "Цалингийн дүрэм хадгалах ба бүх бүртгэлийг дахин тооцоолох",
                  body=objschema(night_start={"type": "string", "example": "19:00"},
                                 night_end={"type": "string", "example": "03:00"},
                                 guard_percent={"type": "number", "example": 50},
                                 worker_percent={"type": "number", "example": 100},
                                 absence_penalty_days={"type": "integer", "example": 3},
                                 absence_penalty_percent={"type": "number", "example": 10},
                                 show_pay_to_employee={"type": "string", "enum": ["0", "1"]},
                                 absent_minutes_grace={"type": "string", "example": "10",
                                                       "description": "Зөвшөөрөлгүй тасалдал «ирээгүй» болох босго минут"},
                                 leave_request_notify={"type": "string", "enum": ["0", "1"],
                                                       "description": "Чөлөөний хүсэлтийг админд мэдэгдэх"},
                                 notify_start={"type": "string", "enum": ["0", "1"]},
                                 notify_end={"type": "string", "enum": ["0", "1"]},
                                 notify_missed_minutes={"type": "string", "example": "15"},
                                 auto_absent={"type": "string", "enum": ["0", "1"]}))},
    "/api/admin/employees/{eid}/pay": {"get": op(
        ["Цалин"], "Нэг ажилтны сарын цалингийн дэлгэрэнгүй",
        params=[p("eid", "integer"), q("month", "string", example="2026-09")])},
    "/api/admin/employees/{eid}/days": {"get": op(
        ["Цалин"], "Нэг ажилтны сарын өдрийн бүртгэл (цалин бүрээр)",
        params=[p("eid", "integer"), q("month", "string")])},
    "/api/admin/employees/{eid}/geo": {"get": op(
        ["Ажлын байр"], "Ажилтанд үйлчлэх гео хүрээ (талбай эсвэл үндсэн)",
        params=[p("eid", "integer")])},
    "/api/admin/employees/{eid}/extra-hours": {"post": op(
        ["Цалин"], "Ажилтанд нэмэлт ажлын цаг гараар нэмэх (0 болгож хасна)",
        params=[p("eid", "integer")],
        body=objschema(date={"type": "string", "format": "date", "example": "2026-10-02"},
                       hours={"type": "number", "example": 3},
                       note={"type": "string", "example": "Шөнийн цемент ачилт"}))},
    "/api/admin/geo/parse": {
        "post": op(["Ажлын байр"], "Google Maps холбоос/координатыг (lat, lng) болгон задлах (v4.2)",
                   body=objschema(text={"type": "string",
                                        "example": "https://www.google.com/maps/@47.9184,106.9177,16z"}),
                   responses={"200": {"description": "Координат", "content": {"application/json": {"example": {
                       "ok": True, "lat": 47.9184, "lng": 106.9177, "zoom": 16,
                       "source": "google_link", "message": "Координат олдлоо: 47.91840, 106.91770"}}}},
                       "400": {"description": "Координат олдсонгүй (эсвэл богино холбоос)"}})},
    "/api/admin/sites": {
        "get": op(["Ажлын байр"], "Ажлын байруудын жагсаалт + ажилтны тоо + Google Maps тохиргоо",
                  responses={"200": {"description": "Жагсаалт", "content": {"application/json": {"example": {
                      "sites": [{"id": 1, "name": "Төв оффис", "lat": 47.9184, "lng": 106.9177,
                                 "radius_m": 300, "active": 1, "employee_count": 5}],
                      "geofence_default": {"enabled": True, "name": "Төв оффис", "lat": 47.9184,
                                           "lng": 106.9177, "radius_m": 300},
                      "maps": {"provider": "google", "api_key": "AIza…", "has_key": True,
                               "embed": "https://maps.google.com/maps?q={lat},{lng}&z={z}&output=embed"},
                      "message": ""}}}}}),
        "post": op(["Ажлын байр"], "Шинэ ажлын байр (талбай) нэмэх",
                   body=objschema(name={"type": "string", "example": "Зайсан — орон сууцны цогцолбор"},
                                  address={"type": "string"}, latitude={"type": "number", "example": 47.8859},
                                  longitude={"type": "number", "example": 106.9207},
                                  radius_m={"type": "number", "example": 250}))},
    "/api/admin/sites/{sid}": {
        "put": op(["Ажлын байр"], "Ажлын байр засах (нэр, координат, радиус)",
                  params=[p("sid", "integer")],
                  body=objschema(name={"type": "string"}, latitude={"type": "number"},
                                 longitude={"type": "number"}, radius_m={"type": "number"},
                                 active={"type": "integer", "enum": [0, 1]})),
        "delete": op(["Ажлын байр"], "Ажлын байрыг идэвхгүй болгох",
                     params=[p("sid", "integer")])},
    "/api/admin/leaves": {
        "get": op(["Чөлөө"], "Чөлөөний бүртгэл + хүлээгдэж буй хүсэлтүүд",
                  params=[q("month", "string", example="2026-10")]),
        "post": op(["Чөлөө"], "Чөлөө олгох (админ) — бүтэн өдөр эсвэл цагаар, цалинтай/цалингүй",
                   body=objschema(employee_id={"type": "integer", "example": 5},
                                  kind={"type": "string", "enum": ["чөлөө"], "example": "чөлөө"},
                                  start_date={"type": "string", "format": "date"},
                                  end_date={"type": "string", "format": "date", "nullable": True},
                                  all_day={"type": "boolean", "example": False},
                                  start_time={"type": "string", "example": "14:00", "nullable": True},
                                  end_time={"type": "string", "example": "19:00", "nullable": True},
                                  paid={"type": "boolean", "example": False},
                                  status={"type": "string", "enum": ["approved", "pending", "rejected"],
                                          "example": "approved"},
                                  note={"type": "string"}))},
    "/api/admin/leaves/{lid}": {"delete": op(
        ["Чөлөө"], "Чөлөөний бүртгэл устгах", params=[p("lid", "integer")])},
    "/api/admin/leaves/{eid}/summary": {"get": op(
        ["Чөлөө"], "Ажилтны сарын чөлөөний хураангуй (нийт цаг, цалинтай цаг, статус тус бүрээр)",
        params=[p("eid", "integer"), q("month", "string")])},
    "/api/admin/export/payroll.xlsx": {"get": op(
        ["Экспорт"], "Цалингийн Excel (Цалин / Чөлөө / Ажлын байр гэсэн 3 хуудас)",
        params=[q("month", "string")])},
    "/api/admin/export/payroll.csv": {"get": op(
        ["Экспорт"], "Цалингийн CSV (UTF-8 BOM)", params=[q("month", "string")])},
    "/api/employee/my-pay": {"get": op(
        ["Ажилтан"], "Өөрийн сарын цалин — ЗӨВХӨН өөрийн бүртгэл (cross-visibility хориотой)",
        params=[q("month", "string")])},
    "/api/employee/my-leaves": {"get": op(
        ["Ажилтан"], "Өөрийн чөлөөний бүртгэл", params=[q("month", "string")])},
    "/api/admin/audit": {"get": op(["Удирдлага"], "Аудитын бүртгэл (сүүлийн 120)")},
    "/api/admin/backup.zip": {"get": op(
        ["Удирдлага"], "Бүрэн нөөц хуулбар (ZIP): өгөгдлийн сан + бүх зураг",
        desc="Админ эрхээр татана. Render/VPS дээр shell-гүйгээр нөөц авах. "
             "Дотор: attendance.db (VACUUM INTO хуулбар), photos/**, BACKUP_INFO.txt.")},
    "/api/admin/api-keys": {
        "get": op(["Удирдлага"], "API түлхүүрүүд"),
        "post": op(["Удирдлага"], "AI агентын API түлхүүр үүсгэх",
                   body=objschema(name={"type": "string", "example": "ChatGPT Agent"},
                                  role={"type": "string", "enum": ["agent", "admin"]}))},
    "/api/admin/api-keys/{key}": {"delete": op(
        ["Удирдлага"], "API түлхүүр идэвхгүй болгох", params=[p("key")])},
    "/api/admin/demo/seed": {"post": op(
        ["Удирдлага"], "Туршилтын (демо) өдрийн бүртгэл үүсгэх — самбарын бүх төлөв харагдана",
        body=objschema(force_workday={"type": "boolean"}),
        responses={"200": {"description": "Үүсгэгдлээ"},
                   "409": {"description": "Ажлын цаг эхлээгүй байна"}})},
    "/api/admin/demo/today": {"delete": op(["Удирдлага"], "Туршилтын бүртгэлийг устгах")},
    "/api/agent/directory": {"get": op(["AI Agent"], "Ажилтны жагсаалт (агент)", security=AGENT)},
    "/api/agent/status": {"get": op(
        ["AI Agent"], "Ирцийн шууд самбар (агент)", security=AGENT,
        params=[q("date", fmt="date")],
        responses={"200": {"description": "Самбар + vision текстэн тайлбар"}})},
    "/api/agent/vision": {"get": op(
        ["AI Agent"], "Нэгдсэн текстэн төлөв — LLM-д шууд өгөхөд тохиромжтой", security=AGENT,
        params=[q("date", fmt="date")],
        responses={"200": {"description": "Текст + бүтэцлэгдсэн өгөгдөл",
                           "content": {"application/json": {"example": {
                               "text": "# Ирцийн төлөв — 2026-10-04 (Ням)\nАжлын хуваарь: 09:00–19:00 (10ц)\n"
                                       "Одоо байгаа ажилтнууд: 5 / Нийт: 12\nХоцорсон: 4 | Ирээгүй: 1 | Эрт явсан: 4"}}}}})},
    "/api/agent/employee-status": {"get": op(
        ["AI Agent"], "Нэг ажилтны төлөв", security=AGENT,
        params=[q("employee_code", required=True), q("date", fmt="date")])},
    "/api/agent/clock-in": {"post": op(
        ["AI Agent"], "Ажилтны өмнөөс ажилд орох бүртгэл (гео хаалт шалгана)", security=AGENT,
        body=objschema(employee_code={"type": "string"},
                       latitude={"type": "number"}, longitude={"type": "number"},
                       accuracy={"type": "number"}, note={"type": "string"},
                       demo_mode={"type": "boolean"}),
        responses=GEOFENCE_ERR_RESP)},
    "/api/agent/clock-out": {"post": op(
        ["AI Agent"], "Ажилтны өмнөөс ажлаас буух бүртгэл", security=AGENT,
        body=objschema(employee_code={"type": "string"}, latitude={"type": "number"},
                       longitude={"type": "number"}, note={"type": "string"},
                       demo_mode={"type": "boolean"}),
        responses=GEOFENCE_ERR_RESP)},
    "/api/agent/geofence-check": {"post": op(
        ["AI Agent"], "Байршлын шалгалт (ажилтныг зааж өгвөл түүний гео хаалтын горимоор, v4.3)",
        security=AGENT,
        body=objschema(latitude={"type": "number"}, longitude={"type": "number"},
                       employee_id={"type": "integer", "example": 11},
                       code={"type": "string", "example": "EMP011"}))},
    "/api/agent/monthly-report": {"get": op(
        ["AI Agent"], "Сарын цалингийн тайлан", security=AGENT,
        params=[q("month", required=True, example="2026-09")])},
    "/api/agent/export/monthly.xlsx": {"get": op(
        ["AI Agent"], "Excel (.xlsx) тайлан татах", security=AGENT,
        params=[q("month", required=True, example="2026-09")],
        responses={"200": {"description": "Excel файл", "content": {
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}}}})},
    "/api/admin/export/monthly.xlsx": {"get": op(
        ["Удирдлага"], "Сарын Excel тайлан (Сарын тайлан + Өдрийн дэлгэрэнгүй гэсэн 2 хуудас)",
        params=[q("month", required=True, example="2026-09")],
        responses={"200": {"description": "Excel файл"}})},
    "/api/admin/export/monthly.csv": {"get": op(
        ["Удирдлага"], "Сарын CSV тайлан", params=[q("month", required=True, example="2026-09")],
        responses={"200": {"description": "CSV (Excel-д нийцэх BOM-той)"}})},
    "/api/admin/export/daily.csv": {"get": op(
        ["Удирдлага"], "Өдрийн CSV тайлан", params=[q("date", required=True, fmt="date")],
        responses={"200": {"description": "CSV файл"}})},
    "/api/employee/leave-request": {"post": op(
        ["Ажилтан"], "Ажилтан аппаас чөлөө хүсэх (хэдэн цаг / нэг өдөр / хэдэн өдөр)",
        desc=("Хүсэлт нь pending статустай үүсч админд мэдэгдэл («ХҮСЭЛТ») очно. "
              "Админ БАТАЛСНЫ дараа л тухайн цаг/өдөр «чөлөө» болж, тасалдал нөхөгдөнө."),
        body=objschema(start_date={"type": "string", "format": "date", "example": "2026-10-06"},
                       end_date={"type": "string", "format": "date", "nullable": True,
                                 "example": "2026-10-07"},
                       all_day={"type": "boolean", "example": True},
                       start_time={"type": "string", "example": "13:00", "nullable": True},
                       end_time={"type": "string", "example": "16:00", "nullable": True},
                       note={"type": "string", "example": "Эмнэлэгт үзүүлэх"}),
        responses={"200": {"description": "pending хүсэлт + админы мэдэгдэл"},
                   "400": {"description": "Давхардсан хүсэлт / аль хэдийн батлагдсан чөлөө / буруу огноо",
                           "content": {"application/json": {"schema": ERR}}}})},
    "/api/employee/leave-requests/{lid}/cancel": {"post": op(
        ["Ажилтан"], "Ажилтан өөрийн ХҮЛЭЭГДЭЖ БУЙ хүсэлтээ цуцлах",
        params=[p("lid", "integer")],
        responses={"200": {"description": "status=cancelled + админд мэдэгдэл"},
                   "400": {"description": "Зөвхөн хүлээгдэж буй хүсэлтийг цуцална",
                           "content": {"application/json": {"schema": ERR}}}})},
    "/api/admin/leave-requests": {"get": op(
        ["Чөлөө"], "Чөлөөний хүсэлтүүд (анхдагч: зөвхөн хүлээгдэж буй)",
        params=[q("month", "string", example="2026-10"),
                q("status", "string", example="pending")])},
    "/api/admin/leave-requests/{lid}/decide": {"post": op(
        ["Чөлөө"], "Хүсэлтийг БАТАЛНА эсвэл ТАТГАЛЗНА (мэдэгдлээс шууд)",
        desc=("Батлах үед тухайн өдөр/цаг «чөлөө» төлөвт шилжиж, тасалдал нөхөгдөнө; "
              "ажилтанд «Чөлөөний хүсэлт батлагдлаа/татгалзагдлаа» мэдэгдэл очно. "
              "Зөвхөн хүлээгдэж буй хүсэлтийг шийдэж болно (эс бөгөөс 400)."),
        params=[p("lid", "integer")],
        body=objschema(approve={"type": "boolean", "example": True},
                       paid={"type": "boolean", "example": False,
                             "description": "Цалинтай эсэх (батлах үед шийднэ)"}),
        responses={"200": {"description": "leave{status:'approved'|'rejected'}, message"},
                   "400": {"description": "Аль хэдийн шийдэгдсэн/цуцлагдсан хүсэлт",
                           "content": {"application/json": {"schema": ERR}}}})},
    "/api/admin/notifications/read": {"post": op(
        ["Удирдлага"], "Админы мэдэгдлийг уншсан гэж тэмдэглэх",
        responses={"200": {"description": "ok:true, marked, unread:0"}})},
    "/api/admin/notifications": {"get": op(
        ["Удирдлага"], "Админы мэдэгдлүүд (хүсэлт, тасалдал, хаагдаагүй бүртгэл)",
        params=[q("limit", "integer", example=50)])},
    "/api/admin/notifications/tick": {"post": op(
        ["Удирдлага"], "Цагийн сануулгыг гараар ажиллуулах (cron/preview)",
        body=objschema(force={"type": "boolean", "example": True}))},
    "/api/admin/extra-hours": {"post": op(
        ["Цалин"], "Ажилтанд нэмэлт ажлын цаг гараар нэмэх (фото шаардлагагүй)",
        body=objschema(employee_id={"type": "integer", "example": 5},
                       date={"type": "string", "format": "date", "example": "2026-10-02"},
                       hours={"type": "number", "example": 2.5},
                       note={"type": "string", "example": "Шөнийн цемент ачилт"}))},
    "/api/admin/photos": {"get": op(
        ["Удирдлага"], "Зурагт хяналт — сар/ажилтнаар (ирсэн, явсан, нэмэлт ажлын зураг)",
        params=[q("month", "string", example="2026-10"), q("employee_id", "integer")])},
    "/api/admin/segments": {"get": op(
        ["Удирдлага"], "Ажлын хэсгүүд (нэмэлт ажил/шөнийн ээлж) + хаагдаагүй бүртгэлүүд",
        params=[q("month", "string", example="2026-10"), q("status", "string", example="closed")])},
    "/api/admin/segments/{sid}/approve": {"post": op(
        ["Удирдлага"], "Ажлын хэсгийг батлах/татгалзах (нэмэлт цаг, шөнийн ээлж)",
        params=[p("sid", "integer")],
        body=objschema(approve={"type": "boolean", "example": True}))},
    "/api/employee/live": {"get": op(
        ["Ажилтан"], "Өөрийн бодит цагийн цалин (30 сек тутам шинэчлэгдэнэ)",
        params=[q("month", "string", example="2026-10")])},
    "/api/employee/extra": {"get": op(
        ["Ажилтан"], "Өөрийн нэмэлт ажил / шөнийн ээлжийн хэсгүүд (нээлттэй эсэх)",
        params=[q("month", "string", example="2026-10")])},
    "/api/employee/extra/start": {"post": op(
        ["Ажилтан"], "Нэмэлт ажил / шөнийн ээлж ЭХЛЭХ — ЗУРАГ заавал",
        body=objschema(photo={"type": "string", "description": "data:image/jpeg;base64,…"},
                       kind={"type": "string", "enum": ["extra", "night"], "example": "extra"},
                       note={"type": "string"}, photo_source={"type": "string", "enum": ["camera", "file"]}),
        responses={"200": {"description": "segment{start}, live, today"},
                   "422": {"description": "ФОТОГҮЙ / гео хаалт / буруу төлөв",
                           "content": {"application/json": {"schema": ERR}}}})},
    "/api/employee/extra/stop": {"post": op(
        ["Ажилтан"], "Нэмэлт ажил / шөнийн ээлж ДУУСГАХ — ЗУРАГ заавал",
        body=objschema(photo={"type": "string"}, note={"type": "string"},
                       photo_source={"type": "string", "enum": ["camera", "file"]}),
        responses={"200": {"description": "segment{end, minutes}, live, today"},
                   "422": {"description": "ФОТОГҮЙ / нээлттэй хэсэг байхгүй",
                           "content": {"application/json": {"schema": ERR}}}})},
    "/api/employee/notifications": {"get": op(
        ["Ажилтан"], "Өөрийн мэдэгдлүүд (чөлөөний шийдвэр, сануулга)",
        params=[q("limit", "integer", example=30)])},
    "/api/employee/notifications/read": {"post": op(
        ["Ажилтан"], "Өөрийн мэдэгдлийг уншсан гэж тэмдэглэх",
        body=objschema(ids={"type": "array", "items": {"type": "integer"}}))},
    "/api/photos": {"get": op(
        ["Нээлттэй"], "Зураг үзүүлэх — админ бүгдийг, ажилтан ЗӨВХӨН өөрийнхийг (файлын нэр {код}_…)",
        params=[q("path", "string", required=True, example="2026-10/003_20261001_180201_out.jpg")],
        responses={"200": {"description": "image/jpeg"},
                   "403": {"description": "Зөвхөн өөрийн зургийг харах боломжтой"},
                   "404": {"description": "Зураг олдсонгүй"}})},
}

SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "Цаг бүртгэл ба ирцийн систем — API",
        "version": "4.5.0",
        "description": (
            "Ажилтны ирсэн/явсан цагийг бүртгэж, ажлын хуваарьтай (09:00–19:00, үдийн "
            "завсарлага 13:00–14:00 цалинтай) харьцуулан Хоцролт ба Эрт явалтыг минутаар "
            "тооцоолно. Нэг ажлын өдөр = 10 цаг (600 мин, үдийн завсарлага орсон); "
            "цагийн тариф = өдрийн цалин ÷ 10ц (150 000₮ → 15 000₮/ц), шөнийн 19:00–03:00 "
            "нэмэлт цаг = өдрийн цалин ÷ 8ц (150 000₮ → 18 750₮/ц). GPS гео хаалт нь ажлын "
            "байрнаас гадуур бүртгэлийг хориглоно. "
            "ЗӨВХӨН ГУРВАН ТӨЛӨВ: чөлөө / ирээгүй / хэвийн (+ ажиллаж байна, амралтын өдөр). "
            "Чөлөөг ажилтан аппаас ХҮСЭЛТ болгон илгээж, админ МЭДЭГДЛЭЭР батална; "
            "батлагдаагүй (хүлээгдэж буй) хүсэлт нь тасалдлыг НӨХӨХГҮЙ. "
            "Ажилд ирээгүй, эсвэл ажлаас мэдэгдэлгүй явсан цаг/өдөр нь «ирээгүй» болно. "
            "Мэдэгдэл урсгалын хэсэг бүрд очно: хүсэлт → админ, шийдвэр → ажилтан, "
            "тасалдал / хаагдаагүй бүртгэл → хоёр тал. "
            "Барилгын бригадын цалин: ажилтан тус бүрийн өдрийн цалин, талбай (site) оноолт, "
            "шөнийн ээлж (19:00–03:00 бүтэн өдөр; хамгаалалт 50%, ажилчин 100%), нэмэлт цаг, "
            "чөлөө (цагаар/өдрөөр), 3 хоног дараалан тасалбал сарын цалин −10%. "
            "Ажилтан зөвхөн өөрийн бүртгэл/цаг/цалинг харна (нууцлал). "
            "Бүх интерфэйс монгол хэл дээр. AI агентад зориулсан REST API."
        ),
    },
    "servers": [{"url": "http://localhost:8000", "description": "Локал сервер"}],
    "tags": [{"name": "Нээлттэй"}, {"name": "Ажилтан"}, {"name": "Удирдлага"},
             {"name": "Чөлөө", "description": "Хүсэлт → мэдэгдэл → шийдвэр → тасалдал нөхөгдөх"},
             {"name": "Цалин"}, {"name": "Ажлын байр"}, {"name": "Экспорт"}, {"name": "AI Agent"}],
    "components": {
        "securitySchemes": {
            "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key",
                           "description": "AI агентын API түлхүүр (Удирдлага → AI агент). Демо: att_demo_agent_key_2026"},
            "SessionCookie": {"type": "apiKey", "in": "cookie", "name": "att_session",
                              "description": "Ажилтан / админ сесс"},
            "EmpHeaders": {"type": "apiKey", "in": "header", "name": "X-Employee-Code",
                           "description": "X-Employee-Pin хамт (агент ажилтны өмнөөс)"},
        },
        "schemas": {
            "Error": objschema(ok={"type": "boolean", "example": False},
                               error={"type": "string", "example": "Та ажлын байрандаа байхгүй байна. Бүртгэл амжилтгүй."}),
            "Employee": objschema(
                id={"type": "integer"}, code={"type": "string", "example": "EMP001"},
                full_name={"type": "string", "example": "Батбаяр Дорж"},
                department={"type": "string"}, position={"type": "string"},
                daily_rate={"type": "number", "description": "Өдрийн цалин (₮)"},
                night_role={"type": "string", "enum": ["guard", "worker"]},
                site_id={"type": "integer", "nullable": True},
                active={"type": "integer", "enum": [0, 1]}),
            "AttendanceRecord": objschema(
                id={"type": "integer"}, employee_id={"type": "integer"},
                work_date={"type": "string", "format": "date"},
                clock_in={"type": "string", "nullable": True, "description": "Ирсэн цаг"},
                clock_out={"type": "string", "nullable": True, "description": "Явсан цаг"},
                clock_in_hm={"type": "string", "example": "09:12"},
                clock_out_hm={"type": "string", "example": "17:41"},
                in_distance_m={"type": "number", "nullable": True, "description": "Ирэх үеийн гео зай (м)"},
                out_distance_m={"type": "number", "nullable": True},
                late_minutes={"type": "integer", "description": "Хоцролтын минут"},
                early_minutes={"type": "integer", "description": "Эрт явсан минут"},
                worked_minutes={"type": "integer"},
                break_minutes={"type": "integer", "description": "Үдийн завсарлага"},
                deduct_minutes={"type": "integer", "description": "Хасагдсан минут = хоцролт + эрт явсан"},
                payable_minutes={"type": "integer", "description": "Төлбөртэй минут"},
                worked_hm={"type": "string", "example": "8ц 15м"},
                payable_hm={"type": "string", "example": "7ц 30м"},
                is_late={"type": "boolean"}, is_early_leave={"type": "boolean"},
                status={"type": "string", "enum": ["working", "completed"]}, note={"type": "string"}),
            "PayrollRow": objschema(
                employee_id={"type": "integer"}, code={"type": "string"},
                full_name={"type": "string"}, position={"type": "string"},
                site_name={"type": "string"}, daily_rate={"type": "number", "example": 95000},
                day_credit={"type": "number", "description": "Хөдөлмөрийн өдөр (1.0 = бүтэн өдөр)"},
                night_days={"type": "integer"}, extra_hours={"type": "number"},
                pay_base={"type": "number"}, pay_extra={"type": "number"},
                leave_pay={"type": "number"}, absent_days={"type": "integer"},
                absent_streak={"type": "integer", "description": "Дараалан тасарсан хоног"},
                penalty={"type": "number", "description": "3+ хоног тасарвал сарын цалингийн 10%"},
                total={"type": "number", "description": "Олгох цалин"},
                pay_status={"type": "string", "example": "Шийтгэл −10%"},
                color={"type": "string", "enum": ["green", "orange", "red", "grey", "pink", "teal"]}),
            "Site": objschema(id={"type": "integer"}, name={"type": "string"},
                              address={"type": "string"}, lat={"type": "number"}, lng={"type": "number"},
                              radius_m={"type": "number", "example": 250},
                              employee_count={"type": "integer"}),
            "Leave": objschema(id={"type": "integer"}, employee_id={"type": "integer"},
                               code={"type": "string", "example": "EMP007"},
                               full_name={"type": "string", "example": "Эрдэнэбат Цэрэн"},
                               kind={"type": "string", "enum": ["чөлөө"], "example": "чөлөө"},
                               start_date={"type": "string", "format": "date"},
                               end_date={"type": "string", "format": "date"},
                               all_day={"type": "integer", "enum": [0, 1]},
                               start_time={"type": "string", "nullable": True},
                               end_time={"type": "string", "nullable": True},
                               hours={"type": "number", "example": 4},
                               status={"type": "string", "enum": ["pending", "approved",
                                                                  "rejected", "cancelled"]},
                               status_label={"type": "string", "enum": ["Хүлээгдэж байна",
                                                                       "Батлагдсан",
                                                                       "Татгалзсан",
                                                                       "Цуцлагдсан"]},
                               status_color={"type": "string", "enum": ["amber", "green",
                                                                       "red", "gray"]},
                               approved={"type": "integer", "enum": [0, 1],
                                         "description": "status='approved' үед 1"},
                               paid={"type": "integer", "enum": [0, 1],
                                     "description": "1 = цалинтай (цалинд нэмэгдэнэ)"},
                               requested_by={"type": "string", "enum": ["employee", "admin"]},
                               decided_at={"type": "string", "nullable": True},
                               decided_by={"type": "string", "nullable": True},
                               color={"type": "string", "enum": ["blue", "green", "red",
                                                                "amber", "gray", "teal",
                                                                "pink", "orange"]},
                               note={"type": "string"}),
            "Photo": objschema(
                path={"type": "string", "example": "2026-10/003_20261001_180201_out.jpg"},
                url={"type": "string", "example": "/api/photos?path=2026-10/003_20261001_180201_out.jpg"},
                employee_id={"type": "integer"}, code={"type": "string", "example": "EMP003"},
                full_name={"type": "string"}, work_date={"type": "string", "format": "date"},
                kind={"type": "string", "enum": ["in", "out", "extra_start", "extra_stop"]},
                taken_at={"type": "string", "nullable": True},
                source={"type": "string", "enum": ["camera", "file", "admin"]}),
            "WorkSegment": objschema(
                id={"type": "integer"}, employee_id={"type": "integer"},
                code={"type": "string"}, full_name={"type": "string"},
                work_date={"type": "string", "format": "date"},
                kind={"type": "string", "enum": ["extra", "night"]},
                start_ts={"type": "string"}, end_ts={"type": "string", "nullable": True},
                minutes={"type": "integer", "example": 120},
                hours={"type": "number", "example": 2.0},
                pay={"type": "number", "example": 33333},
                status={"type": "string", "enum": ["open", "closed", "approved", "rejected"]},
                status_label={"type": "string"}, note={"type": "string"},
                start_photo={"type": "string", "nullable": True},
                end_photo={"type": "string", "nullable": True}),
            "LivePay": objschema(
                employee_id={"type": "integer"}, code={"type": "string", "example": "EMP001"},
                full_name={"type": "string"}, month={"type": "string", "example": "2026-10"},
                currency={"type": "string", "example": "₮"},
                schedule={"type": "object", "properties": {
                    "start": {"type": "string", "example": "09:00"},
                    "end": {"type": "string", "example": "19:00"},
                    "lunch_start": {"type": "string", "example": "13:00"},
                    "lunch_end": {"type": "string", "example": "14:00"},
                    "lunch_paid": {"type": "boolean", "example": True},
                    "paid_minutes_per_day": {"type": "integer", "example": 600},
                    "paid_hours_per_day": {"type": "number", "example": 10.0},
                    "night_start": {"type": "string", "example": "19:00"},
                    "night_end": {"type": "string", "example": "03:00"},
                    "night_minutes": {"type": "integer", "example": 480},
                    "night_hours": {"type": "number", "example": 8.0}}},
                worked_minutes_today={"type": "integer", "example": 341},
                worked_hours_today={"type": "number", "example": 5.68},
                earned_today={"type": "number", "example": 94722},
                working_now={"type": "boolean"},
                hourly_rate={"type": "number", "example": 15000,
                             "description": "Өдрийн цагийн тариф = өдрийн цалин ÷ 10ц "
                                            "(үдийн завсарлага орсон)"},
                daily_rate={"type": "number", "example": 150000},
                month_total={"type": "number", "example": 601944},
                base_pay={"type": "number"}, extra_pay={"type": "number"},
                leave_pay={"type": "number"}, night_pay={"type": "number"},
                penalty={"type": "number"}, absent_days={"type": "integer"},
                today_leave={"type": "object", "nullable": True,
                             "description": "Зөвхөн БАТЛАГДСАН чөлөө"},
                today_pending_leave={"type": "object", "nullable": True,
                                     "description": "Хүлээгдэж буй хүсэлт (тасалдлыг нөхөхгүй)"}),
            "Notification": objschema(
                id={"type": "integer"}, employee_id={"type": "integer", "nullable": True},
                kind={"type": "string", "enum": ["leave_request", "leave_approved",
                                                "leave_rejected", "leave_cancel",
                                                "missed_start", "missed_end", "absent",
                                                "left_without_notice", "shift_unclosed",
                                                "leave_pending"]},
                title={"type": "string", "example": "ЧӨЛӨӨНИЙ ХҮСЭЛТ"},
                body={"type": "string"}, dedupe_key={"type": "string", "nullable": True},
                created_at={"type": "string"}, read_at={"type": "string", "nullable": True},
                unread={"type": "integer", "enum": [0, 1]}),
            "DayStatus": objschema(
                code={"type": "string", "enum": ["leave", "absent", "normal", "working", "off"]},
                label={"type": "string", "enum": ["Чөлөө", "Ирээгүй", "Хэвийн",
                                                 "Ажиллаж байна", "Амралтын өдөр"]},
                color={"type": "string", "enum": ["blue", "red", "green", "teal", "gray"]},
                absent_minutes={"type": "integer", "example": 600},
                leave_minutes={"type": "integer", "example": 0},
                absent_hours={"type": "number", "example": 10.0},
                leave_hours={"type": "number", "example": 3.0}),
            "LeaveDecision": objschema(approve={"type": "boolean", "example": True},
                                       paid={"type": "boolean", "example": False},
                                       message={"type": "string",
                                                "example": "EMP007 Эрдэнэбат Цэрэн — чөлөө "
                                                           "батлагдлаа (цалингүй)."}),
            "BoardRow": {"allOf": [EMP, objschema(
                status_code={"type": "string", "enum": [
                    "working", "working_late", "done", "done_late", "done_early", "done_both",
                    "absent", "pending", "day_off"]},
                status_label={"type": "string", "example": "Хоцорсон (+26 мин)"},
                color={"type": "string", "enum": ["green", "red", "amber", "gray", "darkred"]},
                clock_in_hm={"type": "string"}, clock_out_hm={"type": "string"},
                late_minutes={"type": "integer"}, early_minutes={"type": "integer"},
                deduct_minutes={"type": "integer"}, on_site={"type": "boolean"},
                is_late={"type": "boolean"}, is_early_leave={"type": "boolean"},
                day_status={"type": "string",
                            "enum": ["leave", "absent", "normal", "working", "off"]},
                day_status_label={"type": "string", "example": "Хэвийн"},
                day_status_color={"type": "string", "enum": ["blue", "red", "green",
                                                            "teal", "gray"]},
                absent_minutes={"type": "integer", "example": 0},
                leave_minutes={"type": "integer", "example": 0},
                on_leave={"type": "boolean"},
                pending_leave={"type": "boolean",
                               "description": "Хүлээгдэж буй хүсэлт байгаа эсэх "
                                              "(тасалдлыг НӨХӨХГҮЙ)"})]},
        },
    },
    "paths": PATHS,
}

with open(os.path.join(HERE, "openapi.json"), "w", encoding="utf-8") as f:
    json.dump(SPEC, f, ensure_ascii=False, indent=2)
print("openapi.json үүсгэгдлээ:", len(PATHS), "зам")
