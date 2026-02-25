FROM python:3.11-slim

WORKDIR /app

# System deps for OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
  tesseract-ocr \
  tesseract-ocr-fra \
  poppler-utils \
  && rm -rf /var/lib/apt/lists/*

# Python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Application code
COPY . .

EXPOSE 8000 8001

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
