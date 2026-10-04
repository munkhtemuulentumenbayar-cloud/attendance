# Байршуулах заавар (Deploy) — v4.5

> **Render.com + GitHub (HTTPS-тэй, үнэгүй эхлэл):** `deploy/DEPLOY_RENDER.md` —
> GitHub руу push → Render Blueprint (`render.yaml` бэлэн) → диск холбох заавар.
> Бүх замд нэг л удаа тохируулах зүйл: `TZ`, өгөгдлийн сангийн зам, диск.

Систем нь **гадаад сан шаардахгүй** (Python 3.10+ стандарт сангууд), өгөгдөл нь
SQLite файл, зураг нь `data/photos/` хавтаст. Гурван аргаас аль нэгийг сонгоно.

---

## 0. Сервергүй турших (хамгийн хурдан — 1 файл)

Багц доторх **`preview_demo.html`**-г хоёр дараад л интерфэйс бүхэлдээ нээгдэнэ:
интернэт, сервер, суулгац **шаардлагагүй** — бүх жишээ өгөгдөл файл дотор.
Гар утсан дээр ч ажиллана (хүснэгт, «Хоёр төлбөр» таб, ажилтны карт, хэвлэх).
Энэ нь зөвхөн ХАРАХ демо — бодит бүртгэл хийхэд доорх 2 эсвэл 3-р арга хэрэгтэй.

---

## 1. Энэ дээр шууд турших (хамгийн хурдан)

Хөгжүүлэлтийн орчинд сервер ажиллаж байна — браузер дээрх **Live Preview**-г нээнэ:

* **Удирдлага:** `admin` / `admin123`
* **Ажилтан:** `EMP001 … EMP012` / `1234`

---

## 2. Ubuntu/Debian сервер (нэг команд) — санал болгож буй

```bash
scp attendance_v4.5_deploy.zip root@СЕРВЕРИЙН-IP:/root/
ssh root@СЕРВЕРИЙН-IP
apt-get update && apt-get install -y unzip
unzip attendance_v4.5_deploy.zip -d /root/attendance_src
cd /root/attendance_src/attendance
sudo bash deploy/install.sh --demo        # --demo: 8 долоо хоногийн жишээ өгөгдөл
```

Дараа нь: `http://СЕРВЕРИЙН-IP:8000`

Скрипт юу хийдэг: Python шалгах → `/opt/attendance` руу хуулах → схем + 12 ажилтан,
5 ажлын байр үүсгэх → `systemd` үйлчилгээ болгож асаах (сервер асахад автоматаар
эхэлнэ, унавал дахин асаана).

| Команд | Утга |
|---|---|
| `systemctl status attendance` | Төлөв |
| `journalctl -u attendance -f` | Лог шууд |
| `systemctl restart attendance` | Дахин эхлүүлэх |
| `cd /opt/attendance && python3 reseed_demo.py` | Демо өгөгдөл шинэчлэх |
| `bash deploy/install.sh --port 8080` | Өөр портоор |

---

## 3. Docker (сервер эсвэл оффисын компьютер)

```bash
cd attendance
docker compose up -d --build        # → http://СЕРВЕР:8000
docker compose logs -f attendance
```

`docker-compose.yml` нь `./data`-г volume болгосон тул өгөгдөл, зураг контейнерээс
гадна үлдэж, шинэчлэхэд алдагдахгүй.

---

## 4. Windows дээр (оффисын компьютер, Docker-гүйгээр)

1. Python 3.10+ суулгана (python.org → «Add Python to PATH» ✓)
2. Хавтсыг задлаад `run.bat` (эсвэл `python app.py`) ажиллуулна
3. Браузер: `http://localhost:8000` · Гар утсанд: `http://<компьютерийн-IP>:8000`
   (Windows Firewall дээр 8000 портыг нээх шаардлагатай)

---

## 5. HTTPS — гар утсанд ЗААВАЛ

Гар утсанд **GPS ба камер** ажиллахад браузер зөвхөн HTTPS (эсвэл localhost) дээр
зөвшөөрдөг. Домэйнтэй бол `deploy/nginx.conf` жишээгээр nginx + certbot (үнэгүй
Let's Encrypt) тохируулна. Домэйнгүй бол Cloudflare Tunnel / Tailscale ашиглаж
болно.

---

## 6. Үйлдвэрлэлд орохын өмнөх жагсаалт (checklist)

- [ ] Админы нууц үг солих (`admin123` → хүчтэй нууц үг)
- [ ] Ажилтан бүрийн ПИН солих (`1234`)
- [ ] AI агентын түлхүүр (`att_demo_agent_key_2026`) устгаж, шинэ үүсгэх
- [ ] Тохиргоо: компанийн нэр, өдрийн цалин (ажилтан бүрээр), шөнийн үүрэг,
      авансын дүн/нөхцөл, ажлын байруудын координат + радиус
- [ ] Үнэн өгөгдөл оруулах эсвэл `python3 reseed_demo.py` — демо өгөгдлийг
      бодит ажил эхлэхээс өмнө цэвэрлэх
- [ ] Нөөц хуулбар (сар бүр, автомат):
      `0 2 * * * cp /opt/attendance/data/attendance.db /opt/attendance/data/backup_$(date +\%F).db`
- [ ] `data/photos/` хавтаст зай хангалттай эсэх (бүртгэл бүр 2 зураг ≈ 100–200 КБ)
- [ ] HTTPS + нэвтрэх хязгаарлалт (зөвхөн компанийн сүлжээ эсвэл VPN)

---

## 7. Шинэчлэх (update)

```bash
systemctl stop attendance
cp -r /opt/attendance/data /root/backup_data_$(date +%F)     # нөөц
# шинэ хувилбарын файлуудыг /opt/attendance руу хуулна (data/ хавтсыг ХӨНДӨХГҮЙ)
systemctl start attendance
curl -s localhost:8000/api/health                            # хувилбар шалгах
```

Өгөгдлийн сангийн схем автоматаар шинэчлэгддэг (`core.migrate()`) — гараар
юу ч хийх шаардлагагүй.
