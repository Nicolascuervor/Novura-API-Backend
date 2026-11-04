# Pricecol API Backend — Plataforma Colaborativa de Comparación de Precios

**Universidad:** Corporación Universitaria Empresarial Alexander von Humboldt (Armenia, Quindío)  
**Seminario Nuclear IV (II-2026):** Arquitectura de Software II y Modelos de Calidad  
**Autores:** Samuel Alzate Berrio, Isabella Arias Lemus, Nicolás Cuervo Ríos, Maria Victoria Giraldo Espinosa, Valentina Hoyos Escobar  
**Docente:** Rubén Darío Díaz Bautista  

---

## Resumen Arquitectónico y de Calidad (ISO/IEC 25010:2023 + ISO/IEC 25012)

Backend API RESTful construido bajo un estilo de **Monolito Modular con Núcleo de Dominio Puro (`core_domain`) y CQRS Ligero**, diseñado específicamente para satisfacer los escenarios `EC-01` a `EC-06` y alcanzar los umbrales de las medidas `M-01` a `M-11`.

### Estado Actual de las Medidas Automatizadas (Evidencias `E1`, `E3`, `E4`, `E5`)

| Medida | Característica (ISO 25010 / 25012) | Meta Mínima | Meta Deseable | Resultado Obtenido | Evidencia en el Repositorio |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **M-01** | Exactitud de reglas de dominio (Normalización y Vigencia) | `1.00` | `1.00` | **`1.00` (100%)** | `tests/unit/test_normalization_and_validity.py` |
| **M-02** | Neutralidad de comparación (`EC-06`, Ley 1480) | `1.00` | `1.00` | **`1.00` (100%)** | `tests/unit/test_comparator_and_anomaly.py` |
| **M-05** | Detección de reportes anómalos (`EC-03`) | `>= 0.80` | `>= 0.90` | **`1.00` (10/10)** | `TestAnomalyDetectorTDD` (`E4`) |
| **M-06** | Privacidad del reportante (Ley 1581, sin GPS ni PII) | `1.00` | `1.00` | **`1.00` (9/9)** | `tests/security/test_privacy_m06.py` (`E4`) |
| **M-07** | Latencia bajo 500 usuarios concurrentes (`EC-04`) | `P95 <= 2000ms` | `P95 <= 1000ms` | **Caché sub-10ms** | `tests/load/k6_ec04_500_users.js` (`E3`) |
| **M-09** | Estabilidad estructural del núcleo (`EC-05`) | `<= 0.30` | `<= 0.15` | **`0.00` en puerto** | `core_domain/ports.py` + `test_api_flows.py` |
| **M-010** | Cobertura TDD de reglas de negocio (`core_domain`) | `>= 0.85` | `>= 0.95` | **`0.99` (99%)** | `pytest --cov=core_domain` (`E1`, `E5`) |

---

## Ejecución Rápida (Local o con Contenedores Docker)

### Opción 1: Entorno Local con Python / `.venv`

```powershell
# 1. Aplicar migraciones y cargar datos semilla de Armenia/Quindío (DANE SIPSA)
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py seed_quindio

# 2. Ejecutar suite completa de pruebas TDD, seguridad (M-06) y cobertura (M-010)
.venv\Scripts\python.exe -m pytest

# 3. Ejecutar análisis estático (Evidencia E5)
.venv\Scripts\python.exe -m ruff check core_domain catalog pricing tests

# 4. Iniciar el servidor de desarrollo
.venv\Scripts\python.exe manage.py runserver
```

### Opción 2: Despliegue Reproducible con Docker

```powershell
docker compose up --build
```

---

## Endpoints Principales y Documentación OpenAPI 3

Con el servidor activo en `http://localhost:8000`:
- **Swagger UI Interactivo:** `http://localhost:8000/api/docs/`
- **Redoc:** `http://localhost:8000/api/redoc/`
- **Esquema OpenAPI 3 (YAML):** `http://localhost:8000/api/schema/` (y exportado en `openapi.yaml`)
- **Comparación Neutral Normalizada:** `GET /api/v1/products/1/compare/?sort_by=UNIT_PRICE_ASC&municipality=Armenia`
- **Registro Ágil en Góndola (`EC-01`):** `POST /api/v1/price-reports/`
