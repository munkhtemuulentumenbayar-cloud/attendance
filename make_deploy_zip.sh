#!/usr/bin/env bash
# Байршуулах багц (zip) угсрах — зөвхөн ажиллахад шаардлагатай файлууд.
set -euo pipefail
cd "$(dirname "$0")"
VER=$(python3 -c "import app; print(app.VERSION)" 2>/dev/null || echo "4.5.0")
OUT="../attendance_v${VER}_deploy.zip"
TMP=$(mktemp -d)
DEST="$TMP/attendance"
mkdir -p "$DEST/static" "$DEST/deploy" "$DEST/data"

for f in app.py core.py reports.py xlsxgen.py agent_cli.py make_openapi.py openapi.json \
         requirements.txt run.sh run.bat reseed_demo.py README.md \
         make_icons.py make_qr_poster.py make_phone_guide.py; do
  [ -f "$f" ] && cp "$f" "$DEST/"
done
cp -r static/. "$DEST/static/"          # index.html + icons/ + app.webmanifest + sw.js
cp deploy/install.sh deploy/attendance.service deploy/nginx.conf \
   deploy/DEPLOY.md deploy/DEPLOY_RENDER.md "$DEST/deploy/"
# Render.com / GitHub файлууд
for f in render.yaml .gitignore .dockerignore; do
  [ -f "$f" ] && cp "$f" "$DEST/"
done
printf 'data/ болон data/photos/ хоосон байна — эхлүүлэхэд автоматаар үүснэ.\n' > "$DEST/data/УНШИХ.txt"
[ -f Dockerfile ] && cp Dockerfile "$DEST/"
[ -f docker-compose.yml ] && cp docker-compose.yml "$DEST/"
chmod +x "$DEST/run.sh" "$DEST/deploy/install.sh"

rm -f "$OUT"
( cd "$TMP" && zip -qr "$OLDPWD/$OUT" attendance )
rm -rf "$TMP"
echo "✓ $OUT ($(du -h "$OUT" | cut -f1))"
unzip -l "$OUT" | tail -5
