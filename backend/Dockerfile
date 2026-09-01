FROM python:3.12-slim

WORKDIR /srv/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run (and most managed container hosts) inject the port to listen on via $PORT and route
# to it — a hardcoded 8000 means the container is up but nothing reaches it, which presents as a
# generic "container failed to start" rather than a port mismatch. Defaults to 8000 so local
# `docker run` and the compose stack are unchanged.
ENV PORT=8000
EXPOSE 8000

# Migrations run here rather than being assumed. docker-compose.yml runs `alembic upgrade head`
# in its own `command:`, which overrides this CMD — so that path was covered while a plain
# `docker run` or a Cloud Run deploy silently started against a database with no schema.
#
# RUN_MIGRATIONS=0 opts out, for deployments that run migrations as a separate one-off job
# (the cleaner pattern once there's more than one instance: several cold-starting containers
# racing `alembic upgrade head` is safe in practice but not correct in principle).
CMD ["sh", "-c", "if [ \"${RUN_MIGRATIONS:-1}\" = \"1\" ]; then alembic upgrade head; fi && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
