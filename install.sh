#!/usr/bin/env bash
# ==========================================================================
#  Цаг бүртгэл ба ирцийн систем — Ubuntu/Debian серверт нэг командаар суулгах
# ==========================================================================
#  Хэрэглээ (сервер дээр, root эрхээр):
#     sudo bash install.sh              # суулгаж, systemd үйлчилгээ болгожоно
#     sudo bash install.sh --demo       # + 8 долоо хоногийн демо өгөгдөл
#     sudo bash install.sh --port 8080  # өөр порт
#
#  Дараа нь:  http://<серверийн-IP>:8000
#             Удирдлага: admin / admin123      Ажилтан: EMP001…EMP012 / 1234
# ==========================================================================
set -euo pipefail

APP_DIR="/opt/attendance"
SERVICE="attendance"
PORT="${PORT:-8000}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEMO=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --demo)  DEMO=1; shift ;;
    --port)  PORT="$2"; shift 2 ;;
    --dir)   APP_DIR="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Тодорхойгүй сонголт: $1"; exit 1 ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "⚠  root эрхээр ажиллуулна уу:  sudo bash $0 $*" >&2; exit 1
fi

echo "── 1/4 · Системийн багц шалгах ─────────────────────────────"
export DEBIAN_FRONTEND=noninteractive
if ! command -v python3 >/dev/null; then
  apt-get update -qq && apt-get install -y -qq python3
fi
python3 - <<'PY'
import sys
assert sys.version_info >= (3, 10), f"Python 3.10+ хэрэгтэй (одоо {sys.version.split()[0]})"
print("   ✓ Python", sys.version.split()[0], "— гадаад сан шаардахгүй")
PY
# Цагийн бүс (Улаанбаатар)
timedatectl set-timezone Asia/Ulaanbaatar 2>/dev/null || ln -sf /usr/share/zoneinfo/Asia/Ulaanbaatar /etc/localtime || true

echo "── 2/4 · Файлуудыг $APP_DIR руу хуулах ─────────────────────"
mkdir -p "$APP_DIR/data" "$APP_DIR/static" "$APP_DIR/deploy"
for f in app.py core.py reports.py xlsxgen.py agent_cli.py make_openapi.py \
         openapi.json requirements.txt run.sh reseed_demo.py README.md demo_stub.js; do
  [[ -f "$SRC_DIR/$f" ]] && cp -f "$SRC_DIR/$f" "$APP_DIR/"
done
cp -f "$SRC_DIR"/static/* "$APP_DIR/static/" 2>/dev/null || true
cp -f "$SRC_DIR"/deploy/attendance.service "$APP_DIR/deploy/" 2>/dev/null || true
chmod +x "$APP_DIR/run.sh" 2>/dev/null || true

echo "── 3/4 · Өгөгдлийн сан бэлтгэх ─────────────────────────────"
cd "$APP_DIR"
ATTENDANCE_DB="$APP_DIR/data/attendance.db" python3 -c "import core; core.init_db()" \
  && echo "   ✓ Схем + 12 ажилтан, 5 ажлын байр, тохиргоо бэлэн"
if [[ $DEMO -eq 1 ]]; then
  ATTENDANCE_DB="$APP_DIR/data/attendance.db" python3 reseed_demo.py | tail -3
  echo "   ✓ Демо өгөгдөл (8 долоо хоног) үүслээ"
fi

echo "── 4/4 · systemd үйлчилгээ ─────────────────────────────────"
cat > "/etc/systemd/system/$SERVICE.service" <<UNIT
[Unit]
Description=Attendance System (Цаг бүртгэл ба ирцийн систем)
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
Environment=TZ=Asia/Ulaanbaatar
Environment=HOST=0.0.0.0
Environment=PORT=$PORT
Environment=ATTENDANCE_DB=$APP_DIR/data/attendance.db
ExecStart=/usr/bin/python3 $APP_DIR/app.py
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now "$SERVICE"
sleep 2
systemctl is-active --quiet "$SERVICE" && echo "   ✓ Үйлчилгээ ажиллаж байна" || {
  echo "   ✗ Ажилласангүй — лог:"; journalctl -u "$SERVICE" -n 20 --no-pager; exit 1; }

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
cat <<INFO

════════════════════════════════════════════════════════════════
  БЭЛЭН!  Браузер дээрээ нээнэ үү:

    http://${IP:-<серверийн-IP>}:$PORT

  Удирдлага :  admin / admin123        ← эхний нэвтрэлтийн дараа солино уу
  Ажилтан   :  EMP001 … EMP012 / 1234  ← ПИН-үүдийг солино уу
  AI агент  :  att_demo_agent_key_2026

  Удирдлагын командууд:
    systemctl status $SERVICE          # төлөв
    journalctl -u $SERVICE -f          # лог (шууд)
    systemctl restart $SERVICE         # дахин эхлүүлэх
    cd $APP_DIR && python3 reseed_demo.py   # демо өгөгдөл шинэчлэх

  Дараагийн алхмууд (үйлдвэрлэлд):
    • docker compose up -d  (эсвэл энэ скрипт) — аль нэгийг нь сонгоно
    • nginx + HTTPS (deploy/nginx.conf жишээ) — гар утсанд GPS/камер
      ажиллахад HTTPS ЗААВАЛ шаардлагатай
    • Нөөц хуулбар:  crontab -e →  0 2 * * * cp $APP_DIR/data/attendance.db \\
        $APP_DIR/data/backup_\$(date +%F).db
════════════════════════════════════════════════════════════════
INFO
