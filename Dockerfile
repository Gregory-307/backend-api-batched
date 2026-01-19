# Simple Python image - no Miniconda needed
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libusb-1.0-0 \
        patch \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /backend-api

# Install Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and patches
COPY . .

# Apply Hummingbot patches
RUN set -e; \
    SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])"); \
    for p in /backend-api/patches/*.patch; do \
        echo "Applying $p"; \
        patch -d "$SITE_PACKAGES" -p1 --forward < "$p" || true; \
    done

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
