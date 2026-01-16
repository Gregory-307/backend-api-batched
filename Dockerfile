# Start from a base image with Miniconda installed
FROM continuumio/miniconda3

# ---- slow layers (cached) ----------------------------------------------------
# Install system dependencies
RUN apt-get update && \
    apt-get install -y sudo libusb-1.0 python3-dev gcc patch && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /backend-api

# Copy the Conda environment file and create the environment
COPY environment.yml .
RUN conda env create -f environment.yml

# ---- fast layer: copy source & patches ---------------------------------------
# Make RUN commands use the new environment
SHELL ["conda", "run", "-n", "backend-api", "/bin/bash", "-c"]

# Copy the current directory contents (including patches/) into the container
COPY . .

# Apply all runtime patches in one go
RUN set -e; \
    cd /opt/conda/envs/backend-api/lib/python3.12/site-packages && \
    for p in /backend-api/patches/*.patch; do \
        echo "⚙️  Applying $p"; \
        patch -p1 --forward --silent < "$p" || true; \
    done

# The code to run when container is started
ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "backend-api", \
           "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", \
           "--reload"]
