# Despliegue reproducible del Núcleo de Pricecol API Backend con soporte PostgreSQL
# Cumple el requisito de Flexibilidad (Instalabilidad) y Mínimos Exigibles de la Guía.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir "django>=6.1.2" "djangorestframework>=3.15.2" "djangorestframework-simplejwt>=5.4.0" "drf-spectacular>=0.28.0" "Pillow>=11.0.0" "psycopg[binary]>=3.2.0" "redis>=5.2.0" "celery>=5.4.0" "pytest>=8.3.0" "pytest-django>=4.9.0" "pytest-cov>=6.0.0" "ruff>=0.9.0"

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && python manage.py seed_quindio && python manage.py runserver 0.0.0.0:8000"]
