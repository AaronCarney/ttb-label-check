# CPU-only container image for the label-check service. No GPU is required:
# the local reader runs on CPU and the image stays on a small instance.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    OPENBLAS_NUM_THREADS=2

# OpenBLAS sits under OpenCV and NumPy and reads OPENBLAS_NUM_THREADS when the
# library loads, which happens before any of this project's code runs. So it is
# the one thread cap `LocalVisionEngine` cannot set for itself, and its docstring
# says so: it belongs in the process environment, and this image is where the
# deployed product sets it. Left unset, OpenBLAS runs one thread per core and
# contends with the three onnxruntime sessions a read has already sized. 2 is
# what `.gitlab-ci.yml` uses for the same reason.

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# `uv sync` installs into /app/.venv. Put its bin ahead of the system Python on
# PATH so CMD resolves the uvicorn from the locked environment.
ENV PATH="/app/.venv/bin:$PATH"

# The built island bundle and the Jinja templates both ship under app/ui/, so
# copying app/ is enough for the web interface.
COPY app ./app
COPY rules ./rules
COPY assets ./assets
# The real label images the sample-batch download serves. .dockerignore excludes
# tests/ and then negates this one path.
COPY tests/fixtures/labels ./tests/fixtures/labels

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
