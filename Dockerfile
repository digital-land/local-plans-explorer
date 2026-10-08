# syntax=docker/dockerfile:1

# --- Frontend assets -------------------------------------------------------
FROM node:24-trixie-slim AS frontend
WORKDIR /build

COPY package.json package-lock.json .npmrc ./
RUN npm ci --ignore-scripts

COPY digital-land-frontend.config.json rollup.config.js ./
COPY src ./src
RUN npm run build

# --- Application -----------------------------------------------------------
FROM python:3.13-slim-trixie
WORKDIR /code

ENV FLASK_CONFIG=application.config.DevelopmentConfig
ENV FLASK_APP=application.wsgi:app

ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5050
ENV FLASK_DEBUG=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    wget gnupg \
    && rm -rf /var/lib/apt/lists/*


RUN mkdir -p /etc/apt/keyrings && \
    wget -qO- https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor > /etc/apt/keyrings/postgresql.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/postgresql.gpg] http://apt.postgresql.org/pub/repos/apt trixie-pgdg main" > /etc/apt/sources.list.d/pgdg.list

RUN apt-get update && \
    apt-get install -y --no-install-recommends postgresql-client-16 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements ./requirements
RUN pip install --no-cache-dir -r requirements/requirements.txt

COPY . .
COPY --from=frontend /build/application/static ./application/static
EXPOSE 5050

ENTRYPOINT ["./docker-entrypoint.sh"]
