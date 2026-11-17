FROM python:3.11-slim

WORKDIR /srv/aeroforge

COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY packages ./packages
COPY apps/api/app ./apps/api/app
COPY data ./data

ENV PYTHONPATH=/srv/aeroforge/apps/api:/srv/aeroforge/packages:/srv/aeroforge/packages/shared-schemas
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
