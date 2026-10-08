FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
# cache-bust: 2026-10-03-v2
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt 2>/dev/null || \
    pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Create data directory for OI/Elo storage
RUN mkdir -p data

# Don't run as root in production
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2
