# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies, the HSI/HTAR client, and uv
RUN apt-get update && apt-get install -y \
    curl \
    libedit2 \
    libmunge2 \
    libncurses6 \
    libtirpc3 \
    rpm \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv to PATH
ENV PATH="/root/.local/bin:$PATH"

# Copy project files
COPY pyproject.toml ./
COPY README.md ./

# Copy application code
COPY app/ ./app/
COPY examples/ ./examples/

# The configured HSI keytab is required by /config/hsi/verbose at runtime.
COPY credentials/avldata.keytab ./credentials/avldata.keytab

# The image is Debian-based, so use the vendor's Ubuntu x86_64 RPM.
# HSI/HTAR is installed under /hpss_src/hsihtar-10.3.0-3/bin.
COPY HSIupdate/hsihtar-clt-10.3.0-3.ubuntu.x86_64.rpm /tmp/hsihtar-clt.rpm
RUN rpm -ivh --nodeps /tmp/hsihtar-clt.rpm && \
    rm -f /tmp/hsihtar-clt.rpm && \
    ln -s /hpss_src/hsihtar-10.3.0-3/bin/hsi /usr/local/bin/hsi && \
    ln -s /hpss_src/hsihtar-10.3.0-3/bin/htar /usr/local/bin/htar

# Create necessary directories with proper permissions
RUN mkdir -p storages/caches storages/jobs && \
    chmod -R 777 storages

# Install Python dependencies
RUN /root/.local/bin/uv sync

# Expose the application port
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1

# Run the application
CMD ["/root/.local/bin/uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
