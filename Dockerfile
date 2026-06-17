FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed for tgcrypto build and Playwright/Chromium runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install headless Chromium + its OS-level dependencies for Playwright
RUN playwright install --with-deps chromium

COPY . .

EXPOSE 8080

CMD ["python", "main.py"]
