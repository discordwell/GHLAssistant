FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY crm /app/crm
COPY workflows /app/workflows
COPY dashboard /app/dashboard
COPY hiring_tool /app/hiring_tool

RUN pip install -e ".[crm,workflows,dashboard,hiring,dev]"

CMD ["python", "-m", "maxlevel.cli", "--help"]

