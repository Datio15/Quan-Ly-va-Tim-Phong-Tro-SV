FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SCRIPTS_DIR=/app/scripts

# Công cụ cho scripts/backup.sh và restore-test.sh (SPEC §16): pg_dump/pg_restore/psql bản 16 (khớp
# PostgreSQL 16; bản 15 của Debian không dump được máy chủ 16), openssl để mã hóa, curl để gọi Blob REST.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl openssl \
 && install -d /usr/share/postgresql-common/pgdg \
 && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
 && . /etc/os-release \
 && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends postgresql-client-16 \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY worker/ ./worker/
# Ngữ cảnh build phụ "scripts" (thư mục scripts/ ở gốc repo), khai báo trong docker-compose.yml.
# Build tay: docker build --build-context scripts=./scripts -t <tên> ./worker
COPY --from=scripts backup.sh restore-test.sh ./scripts/

CMD ["python", "-m", "worker.main"]
