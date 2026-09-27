# Production Dockerfile for Magicpin Vera AI Engine
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . /app/magicpin_vera

# Expose port (overridden by $PORT on Render/Railway/Fly)
EXPOSE 8080

# Health check probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:' + str(os.environ.get('PORT', 8080)) + '/v1/healthz')" || exit 1

# Start Uvicorn HTTP server
CMD exec uvicorn magicpin_vera.bot:app --host 0.0.0.0 --port ${PORT:-8080}
