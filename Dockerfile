FROM python:3.11.9-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TESSERACT_CMD=/usr/bin/tesseract \
    TESSERACT_LANG=spa+eng

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-spa \
    && tesseract --list-langs | grep -qx eng \
    && tesseract --list-langs | grep -qx spa \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py aplicar_migraciones --instalar-esquema --inicializar-catalogos && exec gunicorn --bind 0.0.0.0:${PORT:-8000} config.wsgi:application"]
