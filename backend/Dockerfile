FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY tests ./tests

RUN useradd --system --uid 10001 app && chown -R app /srv
USER app

EXPOSE 8000
# Chờ CSDL, đặt mật khẩu demo (chỉ tài khoản chưa có mật khẩu), rồi chạy api.
ENV FORWARDED_ALLOW_IPS=127.0.0.1,172.16.0.0/12,10.0.0.0/8,192.168.0.0/16
CMD python -m app.seed_passwords && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1     --proxy-headers --forwarded-allow-ips "$FORWARDED_ALLOW_IPS"
