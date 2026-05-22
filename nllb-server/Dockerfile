FROM nvidia/cuda:12.5.1-base-ubuntu24.04

RUN apt-get update && apt-get install -y \
  python3-pip \
  python3-dev \
  && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app

ENV UV_PYTHON_DOWNLOADS=0 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock* ./
COPY .python-version ./
RUN uv sync --no-dev --frozen --extra-index-url https://pytorch.org

COPY *.py .
COPY *.json .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "mt_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
