#!/usr/bin/env bash
# Цаг бүртгэлийн систем — хурдан эхлүүлэх скрипт
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--port) PORT="$2"; shift 2 ;;
    -h|--host) HOST="$2"; shift 2 ;;
    --reset)   rm -rf data && echo "⚠  Мэдээллийн сан устгагдлаа (дараагийн ажиллуулалтад демо өгөгдөл дахин үүснэ)"; shift ;;
    --seed)    python3 -c "import core; core.init_db()" && echo "✓ Демо өгөгдөл бэлэн"; exit 0 ;;
    *) echo "Хэрэглээ: $0 [--port 8000] [--host 0.0.0.0] [--reset] [--seed]"; exit 1 ;;
  esac
done

PY=$(command -v python3 || command -v python)
echo "── Цаг бүртгэл ба ирцийн систем ──"
echo "Порт: $PORT | Хост: $HOST"
echo "Ажилтны нэвтрэлт: EMP001 / 1234  (EMP001…EMP012)"
echo "Удирдлага:        admin / admin123"
echo
exec env PORT="$PORT" HOST="$HOST" "$PY" app.py
