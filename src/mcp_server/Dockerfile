FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --requirement requirements.txt \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
COPY server.py .
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["python", "server.py"]
