# syntax=docker/dockerfile:1.7

FROM node:24.18.0-alpine3.24 AS frontend-build

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


FROM python:3.14.7-slim-bookworm AS backend-build

ARG UV_VERSION=0.12.2
ENV PIP_ROOT_USER_ACTION=ignore \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /build/backend
RUN python -m pip install --no-cache-dir "uv==${UV_VERSION}"
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-group dev


FROM python:3.14.7-slim-bookworm AS runtime

ARG APP_VERSION=0.2.1
LABEL org.opencontainers.image.title="Leave Planner" \
      org.opencontainers.image.version="${APP_VERSION}"

ENV HOME=/tmp \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend/src \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:${PATH}"

RUN groupadd --gid 10001 leaveplanner \
    && useradd --uid 10001 --gid leaveplanner --no-create-home leaveplanner

WORKDIR /app/backend
COPY --from=backend-build /build/backend/.venv /app/.venv
COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations
COPY backend/src ./src
COPY docs/reference/HR78_Medical_Dental_Annual_Leave_Policy_v3_2025-07.pdf /app/docs/reference/
COPY docs/reference/HRS09_Medical_Dental_Annual_Leave_Guidance_v1_2025-07.pdf /app/docs/reference/
COPY --from=frontend-build /build/frontend/dist /app/frontend/dist

USER 10001:10001
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
