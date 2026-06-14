FROM python:3.13.13-slim

# Install system build dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY celery/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium and its OS dependencies required by Playwright
RUN playwright install --with-deps chromium

# Copy the Django application code
COPY django /app
