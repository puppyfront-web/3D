FROM python:3.12-slim-bookworm

WORKDIR /app

# Switch apt to Aliyun mirror — deb.debian.org is often unreachable from CN
# networks (502 Bad Gateway) which breaks build-essential install. Debian 12
# uses the deb822 format (debian.sources); older layout uses sources.list.
# Cover both so the sed never fails silently.
RUN { [ -f /etc/apt/sources.list.d/debian.sources ] \
        && sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' \
            /etc/apt/sources.list.d/debian.sources || true; } \
    && { [ -f /etc/apt/sources.list ] \
        && sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' \
            /etc/apt/sources.list || true; }

# System dependencies for PyMuPDF, parsers, magic bytes, OCR libs, and healthcheck
#   - libmagic1: required by python-magic for MIME sniffing
#   - libgl1, libglib2.0-0: required at runtime by PaddleOCR/OpenCV
RUN apt-get update -o Acquire::Retries=3 && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    postgresql-client \
    libmagic1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Use Aliyun PyPI mirror for faster, reliable installs from CN networks
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ \
    && pip config set global.trusted-host mirrors.aliyun.com

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# OCR is an optional extra (paddleocr+paddlepaddle are heavy). Install behind
# `|| true` so a mirror/registry hiccup doesn't break the main image build —
# OCRService degrades to no-op when the libs are absent.
RUN pip install --no-cache-dir paddleocr paddlepaddle || \
    echo "WARN: OCR deps install failed; OCR will degrade gracefully"

# Copy application code
COPY . .

# Copy and set entrypoint
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Create storage directory
RUN mkdir -p /app/storage

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
