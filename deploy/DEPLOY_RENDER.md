# Render.com дээр байршуулах — GitHub + Render + (сонголтоор) Claude API

Энэ системд сервер эсвэл Docker л хэрэгтэй — **гадаад Python сан байхгүй**,
өгөгдөл нь SQLite файл + зураг. Render дээр дараах давуу тал бий:

* **HTTPS үнэгүй, автоматаар** (`https://таны-нэр.onrender.com`) — гар утсанд
  **камер ба GPS ажиллахад HTTPS заавал** шаардлагатай, энэ нь шийдэгдэнэ.
* GitHub-д `git push` хийх бүрд **автомат deploy**.
* Free instance дээр **турших бүрэн үнэгүй**.

---

## А. GitHub руу оруулах (нэг удаа, 5 команд)

Төслийн хавтас дотор (файлууд нь `app.py`, `core.py`, `static/`, … байгаа газар):

```bash
git init
git add .
git commit -m "Attendance system v4.5 — хоёр төлбөр (10-ны цалин + 25-ны аванс)"
git branch -M main
git remote add origin https://github.com/<ТАНЫ-НЭР>/attendance.git
git push -u origin main
```

GitHub дээр эхлээд **хоосон** repository үүсгэнэ (README/gitignore нэмэхгүй).

⚠️ `.gitignore` нь `data/`, `*.db`, `exports/`, `screenshots/`, `.env`-г аль хэдийн
хасдаг — өгөгдөл, зураг, нууц мэдээлэл GitHub руу орохгүй. Push хийхийн өмнө
`git status` гэж шалгаж болно: `data/` мөр гарч ирэх ёсгүй.

---

## Б. Render — Blueprint-ээр (хамгийн хялбар, `render.yaml` бэлэн)

1. <https://dashboard.render.com> → **New +** → **Blueprint**
2. GitHub-аа холбож, `attendance` repository-г сонгоно → **Connect**
3. Render `render.yaml`-г уншиж, `attendance-system` үйлчилгээг үүсгэнэ → **Apply**
4. ~2–4 минутын дараа `https://attendance-system-XXXX.onrender.com` бэлэн

Энэ нь **Free** тохиргоо (дискгүй): сервер 15 минут идэвхгүй бол унтаж, дараагийн
хандалтад ~10–30 секундэд сэрнэ. Унтаж сэрэх бүрд өгөгдлийн сан шинээр үүсч,
**8 долоо хоногийн демо өгөгдөл автоматаар** бэлдэнэ — туршихad тохиромжтой.

## В. Render — гараар (Blueprint-гүйгээр)

1. **New +** → **Web Service** → repository сонгоно
2. **Language:** `Docker` · **Dockerfile Path:** `./Dockerfile`
3. **Instance Type:** `Free` (туршилт) эсвэл `Starter` (бодит)
4. **Health Check Path:** `/api/health`
5. **Environment Variables:**

| Key | Value |
|---|---|
| `TZ` | `Asia/Ulaanbaatar` |
| `HOST` | `0.0.0.0` |
| `ATTENDANCE_DB` | `/app/data/attendance.db` |
| `PYTHONUNBUFFERED` | `1` |

→ **Create Web Service**. `PORT`-ыг Render өөрөө өгнө — код уншиж автоматаар
сонсоно (`app.py` нь `PORT` env-ийг хүлээж авдаг).

---

## Г. Эхний туршилт

| | |
|---|---|
| Хаяг | `https://<нэр>.onrender.com` |
| Удирдлага | `admin` / `admin123` |
| Ажилтан | `EMP001 … EMP012` / `1234` |
| AI агент түлхүүр | `att_demo_agent_key_2026` |

**Турших дараалал:** Удирдлага → «Хоёр төлбөр» таб (25-ны аванс, 10-ны цалин,
«Аванс олгох»/«Цуцлах»/«Сэргээх») → «Хэвлэх / PDF» → Гарах → `EMP012`/`1234`-ээр
нэвтэрч «Миний цалингийн хуанли» → **гар утсаараа** нээж камер+GPS-тэй бүртгэлийг
турших (HTTPS тул ажиллана ✓).

---

## Д. Бодит ашиглалт — Free-ээс Starter + Диск руу шилжих

**Free instance-ийн гол хязгаарлалт:** файлын систем түр зуурын (ephemeral) —
дахин deploy/restart бүрд `data/` агуулга (сан + зураг) **устана**.

Бодит ажилд:

1. Render → үйлчилгээ → **Settings** → **Instance Type** → `Starter` (≈$7/сар)
2. **Disks** → **Add Disk**:
   * **Name:** `attendance-data`
   * **Mount Path:** `/app/data`  ← яг энэ зам (сан `data/attendance.db`,
     зураг `data/photos/` хоёулаа энд байрлана)
   * **Size:** `1 GB` (жижиг бригадт 1–2 жил хангалттай; зураг нэг өдөр ≈100–200 KB)
3. `render.yaml` ашиглаж байгаа бол: `plan: free` → `plan: starter` болгож,
   файлын доод хэсгийн `disk:` блокийг нээгээд push хийнэ.

⚠️ Дисктэй үйлчилгээг **олон instance болгож scale хийх боломжгүй** — SQLite нэг
instance-д зориулагдсан. Render үүнийг автоматаар хязгаарлана.

**Тохиргооны дараа заавал:** админы нууц үг солих, ажилтан бүрийн ПИН солих,
`att_demo_agent_key_2026` түлхүүрийг устгаж шинээр үүсгэх, ажлын байрны
координат/радиус ба өдрийн цалинг бодит утгаар оруулах.

---

## Е. Нөөц хуулбар (backup) — Render дээр shell шаардлагагүй

Админ эрхээр **`https://<нэр>.onrender.com/api/admin/backup.zip`** хаягаас
бүх өгөгдлийг (сан + бүх зураг) ZIP болгон татаж авна. Браузераас шууд татагдана.

Сард нэг удаа (эсвэл өдөр бүр) татаж компьютер/Google Drive-д хадгалахыг
зөвлөнө. Сэргээх: ZIP доторх `attendance.db`-г `/app/data/attendance.db`
болгож, `photos/` хавтсыг `/app/data/photos/` руу тавиад үйлчилгээг restart
хийнэ. (Starter дээр Render-ийн Shell-ээс ч хийж болно.)

---

## Ж. Claude API түлхүүр (сонголтоор)

**Энэ систем Claude (эсвэл өөр гадаад AI) API-г дууддаггүй** — бүх тооцоо
локал, Python стандарт сангуудаар. Тиймээс байршуулахад **түлхүүр шаардлагагүй**.

Түлхүүрийг дараах тохиолдолд ашиглана:

* Системд холбогдсон **AI агент** (өөрийн скрипт/чатбот) — «Өнөөдөр хэн
  ажилласан?», «10-нд хэдэн төгрөг олгох вэ?» гэх мэт асуултад системийн
  API-аас (`X-API-Key: att_…`) өгөгдөл татаж хариулах.
* Зургийн хяналтыг AI-аар шалгах (тусдаа хөгжүүлэлт).

Хэрэв холбох бол:

1. Render → үйлчилгээ → **Environment** → **Add Environment Variable**
   * Key: `ANTHROPIC_API_KEY` · Value: `sk-ant-…` → **Secret** гэж тэмдэглэнэ
2. `.env` файлыг **хэзээ ч GitHub руу push хийхгүй** (`.gitignore`-д байгаа).
3. `att_demo_agent_key_2026` демо түлхүүрийг устгаж, «AI агент» табаас шинэ
   түлхүүр үүсгэнэ.

---

## З. Алдаа гарвал (troubleshooting)

| Шинж тэмдэг | Шалтгаан / шийдэл |
|---|---|
| Build `failed` | Render → Logs. Dockerfile байрлал `./Dockerfile` эсэх; repo дотор `app.py`, `static/` байгаа эсэх |
| «No open ports detected» | `PORT` env-ийг ашиглахгүй байх — манай код `os.environ["PORT"]`-ыг уншдаг тул зөв; env дээр `HOST=0.0.0.0` байгаа эсэх |
| Deploy дараа өгөгдөл алга | Free instance = түр зуурын диск. Дээрх **Д** хэсгээр диск нэмнэ |
| Сервер унтаж байна | Free tier 15 мин идэвхгүй бол унтана; эхний хандалт 10–30 сек. Бодит ажилд Starter |
| Цаг буруу | `TZ=Asia/Ulaanbaatar` env байгаа эсэх |
| Гар утсанд камер/GPS ажиллахгүй | Зөвхөн HTTPS дээр ажиллана — Render автоматаар HTTPS өгдөг тул `.onrender.com` хаягийг ашиглана (өөрийн домэйн бол HTTPS тохируулна) |
| Диск нэмэх боломжгүй | Диск нь Starter ба түүнээс дээш багцад; Free-д боломжгүй |

---

## И. Шинэчлэх (шинэ хувилбар гаргах)

```bash
git add . && git commit -m "шинэчлэл" && git push
```
→ Render автоматаар дахин deploy хийнэ. Дискэн дээрх `data/` **хөндөгдөхгүй**.
Шалгах: `https://<нэр>.onrender.com/api/health` → `{"version":"4.5.0", …}`

---

## К. Хувилбарын тэмдэглэл

| | |
|---|---|
| Dockerfile | `python:3.12-slim`, TZ=Asia/Ulaanbaatar, HEALTHCHECK `/api/health` |
| Эхлэх хугацаа | Шинэ сан үүсгэхэд ~4–15 сек (12 ажилтан + 8 долоо хоногийн демо) |
| Санах ой | < 100 MB |
| Өгөгдөл | `data/attendance.db` (SQLite) + `data/photos/YYYY-MM/` |
| Нөөц | `GET /api/admin/backup.zip` (админ) |
