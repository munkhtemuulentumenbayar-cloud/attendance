@echo off
REM Цаг бүртгэл ба ирцийн систем — Windows дээр эхлүүлэх
REM Python 3.10+ суулгасан байх шаардлагатай (python.org)
chcp 65001 >nul
cd /d "%~dp0"

set PORT=8000
set HOST=0.0.0.0
set TZ=Asia/Ulaanbaatar

echo ── Цаг бүртгэл ба ирцийн систем ──
echo Порт: %PORT%
echo Удирдлага: admin / admin123     Ажилтан: EMP001 ... EMP012 / 1234
echo.
echo Браузер дээрээ нээнэ уу:  http://localhost:%PORT%
echo.

python app.py
pause
