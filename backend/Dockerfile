FROM python:3.12-slim

WORKDIR /code

# Install dependencies first (cached layer if requirements don't change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code into /code/backend/ to match M5's import paths
# (M5 uses: from backend.app.database import ...)
COPY . /code/backend/

# Create data directory for SQLite
RUN mkdir -p /code/data

EXPOSE 8000

# Run from /code so "backend.app.main" resolves correctly
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
