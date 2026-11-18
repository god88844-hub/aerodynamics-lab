FROM python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535

WORKDIR /srv/aeroforge

COPY apps/api/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.lock && pip check

COPY packages ./packages
COPY apps/api/app ./apps/api/app
COPY apps/api/alembic ./apps/api/alembic
COPY apps/api/alembic.ini ./apps/api/alembic.ini
COPY data ./data

ENV PYTHONPATH=/srv/aeroforge/apps/api:/srv/aeroforge/packages:/srv/aeroforge/packages/shared-schemas
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
