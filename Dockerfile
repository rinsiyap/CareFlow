FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /opt/careflow

COPY app/backend/requirements-runtime.txt ./requirements-runtime.txt

RUN pip install --no-cache-dir -r requirements-runtime.txt

COPY app/backend/careflow_api ./app/backend/careflow_api

WORKDIR /opt/careflow/app/backend

EXPOSE 8000

CMD ["uvicorn", "careflow_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
