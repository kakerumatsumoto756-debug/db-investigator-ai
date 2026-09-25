FROM python:3.12-slim AS dependencies

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY backend/requirements.txt backend/requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt
ENV PYTHONPATH=/app

FROM dependencies AS test-dependencies
RUN pip install --no-cache-dir -r requirements-dev.txt

FROM test-dependencies AS test
COPY backend/app ./app
COPY tests ./tests
COPY pytest.ini ./pytest.ini
CMD ["pytest", "-q"]

FROM dependencies AS runtime
COPY backend/app ./app
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
