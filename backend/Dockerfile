# backend/Dockerfile
# Pinned base image for reproducible builds
FROM python:3.12-slim@sha256:2be8daddbb829e3fc0ce04a85eb6a1da9205ec26e4508c25100a8e8b3a7ee89a AS base
WORKDIR /app

FROM base AS deps
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

FROM deps AS dev
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM deps AS prod
# Non-root user for security
RUN addgroup --system app && adduser --system --ingroup app app
COPY . .
RUN chown -R app:app /app
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
