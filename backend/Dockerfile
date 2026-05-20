FROM python:3.11-slim

WORKDIR /app

# System dependencies for psycopg2 and Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser (for IFIX scraper)
RUN playwright install --with-deps chromium || echo "Playwright install skipped"

# Copy application code
COPY . .

EXPOSE 5004

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5004"]
