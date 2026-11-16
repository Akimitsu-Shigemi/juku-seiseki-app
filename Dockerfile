FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 非rootユーザーで動かす（SECURITY.md）
RUN useradd -m appuser && chown -R appuser /app
USER appuser

ENV DB_PATH=/app/data/seiseki.db
EXPOSE 5000

# 起動時にダミーデータを用意し、本番WSGI(gunicorn)で起動
CMD ["sh", "-c", "mkdir -p /app/data && python seed.py && gunicorn -b 0.0.0.0:5000 app:app"]
