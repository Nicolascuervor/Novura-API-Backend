# Despliegue reproducible del Núcleo de Pricecol API Backend con soporte PostgreSQL
# Cumple el requisito de Flexibilidad (Instalabilidad) y Mínimos Exigibles de la Guía.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "django>=6.1.2" "djangorestframework>=3.15.2" "drf-spectacular>=0.28.0" "psycopg[binary]>=3.2.0" "pytest>=8.3.0" "pytest-django>=4.9.0" "pytest-cov>=6.0.0" "ruff>=0.9.0"

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && python manage.py seed_quindio && python manage.py runserver 0.0.0.0:8000"]
