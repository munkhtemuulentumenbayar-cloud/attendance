FROM python:3.12-slim

# Цагийн бүс: Улаанбаатар
ENV TZ=Asia/Ulaanbaatar \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0 \
    ATTENDANCE_DB=/app/data/attendance.db

WORKDIR /app
COPY app.py core.py reports.py xlsxgen.py agent_cli.py make_openapi.py openapi.json reseed_demo.py ./
COPY static ./static
RUN mkdir -p /app/data

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD python3 -c "import os,sys,urllib.request; p=os.environ.get('PORT','8000'); sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+p+'/api/health',timeout=4).status==200 else 1)"

CMD ["python3", "app.py"]
