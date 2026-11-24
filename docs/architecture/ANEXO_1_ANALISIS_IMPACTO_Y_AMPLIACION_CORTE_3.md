# Anexo 1 — Registro de Análisis de Impacto, Estimación de Esfuerzo, ADRs y Escenarios Refinados (Ampliación del Corte 3)

- **Proyecto:** Pricecol (Nuvora) — Plataforma colaborativa de comparación de precios entre tiendas y supermercados en Armenia y el Quindío.
- **Opciones seleccionadas:**
  - **Bloque A (Funcionalidades del producto):** **A2. Historial y tendencia de precios** (con extensión opcional de comparación multi-establecimiento en la misma serie).
  - **Bloque B (Cloud Native, DevOps y Arquitectura Empresarial):** **B2. Entrega continua con controles de calidad** (Pipeline CI/CD como código, Quality Gate alineado al PAC, Trivy, Staging con prueba de humo en k6, promoción manual a producción y reversión).
- **Regla de trazabilidad (Sección 3.2 y Sección 7 del Anexo 1):** Este documento y los ADRs asociados (`ADR-13` y `ADR-14`) se registran y confirman en el historial de Git **antes del primer commit de implementación** de las funcionalidades `A2` y `B2`.

---

## 1. Respuesta a las Preguntas de Diseño Abiertas del Anexo 1

### 1.1 Preguntas de Diseño de la Opción A2 (Historial y tendencia de precios)

1. **¿Se justifica Event Sourcing o basta con un almacenamiento de solo inserción (*Append-Only*)? Justifique la decisión frente a los escenarios.**
   - **Respuesta:** Basta y es arquitectónicamente superior un **almacenamiento relacional de solo inserción (*Append-Only*)** sobre la tabla `PriceReport` (documentado en **[ADR-13](file:///c:/Users/nicoc/OneDrive/Documentos/5.%20Proyects/Pricecol-API-Backend/docs/architecture/adrs/ADR-13-historial-tendencia-precios-append-only.md)**). Un reporte de precio en góndola es por definición un hecho puntual e inmutable en el tiempo: cuando el precio de un producto cambia en un establecimiento, el sistema nunca hace `UPDATE` sobrescribiendo el valor anterior, sino que inserta un nuevo registro con marca temporal `reported_at`, `source_type` y `reliability_status`, pasando el registro anterior al estado calculado `SUPERSEDED`. Adoptar *Event Sourcing* completo añadiría sobrecarga de memoria y complejidad de proyecciones eventuales innecesarias en nuestra VM `e2-micro` de 1 GB de RAM, mientras que el modelo *append-only* indexado por `(presentation_id, establishment_id, -reported_at)` resuelve `EC-08` y `EC-04` en $< 15\text{ ms}$ sin tocar el esquema existente (`M-09 = 0.00`).
2. **¿Se muestran en el historial los precios que la plataforma marcó como no confiables? ¿Cómo?**
   - **Respuesta:** Se distingue entre los dos niveles de alerta del motor antifraude (`ADR-05`):
     - Los reportes clasificados como **`ANOMALOUS`** (desviación $> 35\%$ sin evidencia fotográfica ni reputación, o ráfagas de spam) **se excluyen en el 100 % de los casos** del historial público para evitar que intentos de sabotaje o errores de digitación deformen la gráfica de tendencia.
     - Los reportes clasificados como **`LOW_CONFIDENCE`** (desviación atípica moderada entre $22\%$ y $35\%$, o precios extremos respaldados con evidencia) **sí pueden incluirse en la serie**, pero cada punto lleva explícitamente los campos `"reliability_status": "LOW_CONFIDENCE"` y `"requires_warning": true` para que la gráfica los distinga visualmente de los puntos `"VERIFIED"` (y el consumidor pueda ocultarlos enviando `?include_low_confidence=false`).
3. **¿Cuánto historial se conserva y cómo afecta esa decisión al almacenamiento y al desempeño de la consulta?**
   - **Respuesta:**
     - **Almacenamiento:** Se conserva en línea en PostgreSQL un horizonte de **365 días** antes de archivado frío. Dado que cada fila de `PriceReport` ocupa $\sim 280\text{ bytes}$ (las imágenes viven fuera de la base de datos en el volumen `/app/media`), incluso 100.000 reportes anuales consumen apenas $\sim 28\text{ MB}$ ($< 0.1\%$ del disco de 30 GB de la VM).
     - **Desempeño de la consulta:** El endpoint de historial acota la ventana máxima consultable a **90 días** (`days <= 90`, por defecto `90`), utiliza el índice compuesto B-Tree sobre `(presentation_id, establishment_id, -reported_at)` y almacena la serie calculada en **Redis** vinculada a la clave de versión del producto (`get_product_comparison_cache_version_key`). Así, las lecturas repetidas responden en $< 10\text{ ms}$ y cualquier cambio de precio invalida la caché al instante, apareciendo en el historial dentro del plazo de `EC-02` ($< 1\text{ s}$).

---

### 1.2 Preguntas de Diseño de la Opción B2 (Entrega continua con controles de calidad)

1. **¿Qué umbrales tiene el Quality Gate y cómo se relacionan con el Plan de Aseguramiento de Calidad (PAC)?**
   - **Respuesta:** El *Quality Gate* del pipeline (`.github/workflows/ci-cd-quality-gate.yml`, documentado en **[ADR-14](file:///c:/Users/nicoc/OneDrive/Documentos/5.%20Proyects/Pricecol-API-Backend/docs/architecture/adrs/ADR-14-entrega-continua-quality-gate-trivy-k6.md)**) aplica de forma bloqueante los mismos umbrales del `PAC`:
     - **Aprobación de casos de prueba (`PAC-03`, Prioridad Alta = 100 %):** `100 %` de las pruebas unitarias TDD, de integración y de seguridad OWASP/Ley 1581 deben aprobar (`pytest`).
     - **Cobertura de código (`M-010`, `PAC-04`):** Cobertura mínima obligatoria del **`95 %` en `core_domain`** (`--cov=core_domain --cov-fail-under=95`) y **`85 %` global**.
     - **Análisis estático y SAST (`PAC-05`):** **`0` errores y `0` advertencias** en `ruff check .` (incluyendo reglas de seguridad `Bandit S`, `Bugbear B` y `Blind-Except BLE001`).
     - **Seguridad del contenedor (`Trivy`):** **`0` vulnerabilidades `CRITICAL` con parche disponible** en la imagen Docker del backend.
2. **¿Cómo se revierte un despliegue defectuoso y en cuánto tiempo?**
   - **Respuesta:** Mediante el script automatizado `deploy/scripts/rollback_release.sh`. Antes de promover una nueva imagen a producción, el despliegue conserva la imagen previa etiquetada como `nuvora-backend:previous-stable`. Si se detecta una anomalía post-despliegue, el operador ejecuta `bash deploy/scripts/rollback_release.sh`, el cual restituye `nuvora-backend:previous-stable`, recrea los contenedores `backend`, `celery-worker` y `celery-beat` sin tocar el volumen de PostgreSQL ni `/app/media`, limpia la caché de Redis y verifica `HTTP 200` en `/api/v1/health/`. El tiempo total de reversión medido es **inferior a 90 segundos**.
3. **¿El entorno de staging puede reconstruirse desde cero sin pasos manuales?**
   - **Respuesta:** **Sí, al 100 %.** En cada ejecución del pipeline, el job `deploy-staging-and-smoke-test` aprovisiona desde cero los contenedores de base de datos (`PostgreSQL 16`), caché (`Redis 7`) y aplicación (`nuvora-backend`), ejecuta automáticamente `manage.py migrate --noinput`, carga el catálogo y mercado simulado del Quindío (`manage.py seed_quindio` y `seed_simulated_market`), espera el healthcheck `/api/v1/health/` y ejecuta la prueba de humo con **k6** (`tests/load/k6_smoke_staging.js`), todo en **$\sim 3.5\text{ minutos}$ sin intervención humana**.

---

## 2. Plantilla 8.1 — Registros de Decisión Arquitectónica (ADRs de la Ampliación)

*(Los documentos completos también se encuentran en `docs/architecture/adrs/ADR-13-historial-tendencia-precios-append-only.md` y `docs/architecture/adrs/ADR-14-entrega-continua-quality-gate-trivy-k6.md`).*

### 2.1 Resumen en Formato Plantilla 8.1: ADR-13 (Opción A2)

| Campo | Contenido |
| :--- | :--- |
| **Identificador y título** | **ADR-13:** Almacenamiento de solo inserción (*Append-Only*) y agregación temporal en el dominio para el historial y tendencia de precios (Opción A2). |
| **Estado y fecha** | **Aceptado** — 24 de noviembre de 2026 (Ampliación Corte 3, no reemplaza ADRs previos; extiende `ADR-02` y `ADR-07`). |
| **Contexto** | Se requiere consultar la serie histórica y tendencia de los últimos 90 días de un producto en uno o varios establecimientos sin sobrescribir precios anteriores, distinguiendo origen y confiabilidad, respetando la Ley 1581 (`M-06 = 1.00`) y operando dentro de 1 GB de RAM. |
| **Escenarios relacionados** | **EC-08** (Historial de 90 días con trazabilidad y actualidad), **EC-02** (Actualidad $\le 1\text{ min}$), **EC-04** (Desempeño en lectura) y **EC-05** (Evolución sin romper el núcleo). |
| **Alternativas consideradas** | **1. Event Sourcing completo con Event Store separado:** Descartado por sobrecosto de memoria RAM y complejidad de sincronización eventual.<br>**2. Sobrescritura (`UPDATE`) con tabla de auditoría por triggers:** Descartado por acoplar reglas de negocio a la base de datos y dificultar TDD.<br>**3. Almacenamiento relacional *Append-Only* sobre `PriceReport` + servicio puro `PriceHistoryService` en `core_domain`:** Elegido por reutilizar el 100 % del esquema actual e índices B-Tree existentes. |
| **Decisión** | Mantener `PriceReport` como tabla *append-only*, implementar las reglas de filtrado temporal (90 días), exclusión de `ANOMALOUS`, marcación de `LOW_CONFIDENCE` y cálculo de variación porcentual mediante TDD en `core_domain/price_history.py`, y exponer `GET /api/v1/products/{product_id}/price-history/` con soporte para 1 o múltiples establecimientos y caché versionada en Redis. |
| **Consecuencias** | **Positivas:** `M-09 = 0.00` (cero cambios destructivos al núcleo), soporte nativo para comparar 2+ establecimientos en la misma gráfica y cumplimiento estricto de `M-06 = 1.00`.<br>**Negativas / Riesgos:** Múltiples reportes en un mismo día generan varios puntos en la serie; se mitiga entregando la serie ordenada cronológicamente más un resumen estadístico del periodo (mínimo, máximo, promedio y cambio `%`). |
| **Verificación** | Suite TDD en `tests/unit/test_price_history_tdd.py`, pruebas de integración de `EC-08` en `tests/integration/test_api_flows.py` y auditoría de privacidad en `tests/security/test_privacy_m06.py`. |

---

### 2.2 Resumen en Formato Plantilla 8.1: ADR-14 (Opción B2)

| Campo | Contenido |
| :--- | :--- |
| **Identificador y título** | **ADR-14:** Pipeline de Entrega Continua como código con Quality Gate automatizado (Pytest, Ruff/Bandit, Trivy), Staging con prueba de humo en k6 y reversión controlada (Opción B2). |
| **Estado y fecha** | **Aceptado** — 24 de noviembre de 2026 (Ampliación Corte 3; extiende `ADR-01` y `ADR-07`). |
| **Contexto** | Se requiere automatizar la construcción, verificación de calidad, escaneo de seguridad de contenedores, despliegue a staging con prueba de humo y promoción manual a producción con reversión, sin saturar la memoria RAM (1 GB) de la VM productiva en GCP. |
| **Escenarios relacionados** | **EC-12** (Bloqueo del 100 % de cambios defectuosos y despliegue a staging en $\le 15\text{ min}$ sin pasos manuales) y **EC-04** (Desempeño validado con k6). |
| **Alternativas consideradas** | **1. Jenkins + SonarQube auto-hospedados en la VM de GCP:** Descartado porque SonarQube + Jenkins exigen $> 3\text{ GB}$ de RAM y colapsarían la instancia `e2-micro`.<br>**2. Scripts manuales locales antes de SCP:** Descartado por depender de intervención humana e incumplir `EC-12`.<br>**3. Pipeline en GitHub Actions + Quality Gate (`pytest --cov`, `ruff check`, `Trivy`) + Staging con `k6` + Promoción manual y script de Rollback:** Elegido por ejecutarse en runners externos de 7 GB de RAM con bloqueo automático al 100 %. |
| **Decisión** | Implementar `.github/workflows/ci-cd-quality-gate.yml` con 4 etapas encadenadas: (1) Quality Gate de código y cobertura TDD ($\ge 95\%$ en `core_domain`), (2) Construcción Docker y escaneo de vulnerabilidades con **Trivy**, (3) Despliegue automático de entorno Staging desde cero y prueba de humo con **k6** (`tests/load/k6_smoke_staging.js`), y (4) Promoción manual a producción protegida con respaldo de imagen previa y script `deploy/scripts/rollback_release.sh`. |
| **Consecuencias** | **Positivas:** Bloqueo del 100 % de regresiones funcionales, de estilo o de seguridad antes de staging; reconstrucción limpia de staging en $\sim 3.5\text{ min}$; reversión en $< 90\text{ s}$.<br>**Negativas / Riesgos:** El escaneo de imagen con Trivy añade $\sim 45\text{ s}$ al pipeline. |
| **Verificación** | Ejecución del pipeline, script de verificación del Quality Gate (`deploy/scripts/verify_quality_gate.py`), prueba de humo `tests/load/k6_smoke_staging.js` y prueba del procedimiento de rollback. |

---

## 3. Plantilla 8.2 — Escenarios de Calidad Refinados (`EC-08` y `EC-12`)

Formato completo de Bass, Clements y Kazman (2021):

### 3.1 Escenario Refinado `EC-08` (Opción A2 — Historial y tendencia de precios)

| Parte | Descripción | Especificación Refinada del Equipo (`EC-08`) |
| :--- | :--- | :--- |
| **Fuente del estímulo** | Quién o qué genera el estímulo. | Consumidor (autenticado o anónimo) desde la aplicación web o cliente HTTP. |
| **Estímulo** | Evento o condición que llega al sistema. | Solicita el historial y tendencia de precios de los últimos 90 días de un producto en uno o dos establecimientos (`GET /api/v1/products/{id}/price-history/?days=90&establishment_ids=1,2`) inmediatamente después de que se registró un cambio de precio en la semana. |
| **Artefacto** | Parte del sistema afectada. | `PriceHistoryService` (`core_domain/price_history.py`), `ProductPriceHistoryAPIView` (`pricing/views.py`), tabla `PriceReport` (PostgreSQL 16) y caché versionada en Redis. |
| **Entorno** | Condiciones en que ocurre el estímulo. | Operación normal con nuevos reportes comunitarios y oficiales ingresando concurrentemente. |
| **Respuesta** | Lo que el sistema hace ante el estímulo. | El registro del nuevo precio conserva los valores anteriores (*append-only*), invalida la versión de caché del producto, filtra fuera los reportes `ANOMALOUS`, y devuelve la serie temporal de los últimos 90 días indicando en cada punto su origen (`source_type`), estado de confiabilidad (`reliability_status`), precio normalizado (`100g`/`100ml`) y resumen de variación porcentual, sin exponer ningún dato del reportante. |
| **Medida de la respuesta** | Valor verificable con el que se juzga la respuesta. | **1.** El 100 % de los puntos de la serie indica su `source_type` y `reliability_status`.<br>**2.** El 100 % de los reportes `ANOMALOUS` es excluido de la serie.<br>**3.** El cambio de precio aparece en el historial en **$\le 2\text{ segundos}$** tras su registro (cumpliendo el plazo de `EC-02`).<br>**4.** **0 %** de exposición de identidad o GPS del reportante (`M-06 = 1.00`, Ley 1581). |

---

### 3.2 Escenario Refinado `EC-12` (Opción B2 — Entrega continua con controles de calidad)

| Parte | Descripción | Especificación Refinada del Equipo (`EC-12`) |
| :--- | :--- | :--- |
| **Fuente del estímulo** | Quién o qué genera el estímulo. | Integrante del equipo de desarrollo que envía un commit o Pull Request hacia la rama `main`. |
| **Estímulo** | Evento o condición que llega al sistema. | Incorpora un cambio de código que (Caso A) rompe una prueba TDD, baja la cobertura de `core_domain` de 95 % o introduce un hallazgo crítico en Ruff/Bandit/Trivy; o (Caso B) cumple todos los controles de calidad. |
| **Artefacto** | Parte del sistema afectada. | Pipeline de CI/CD (`.github/workflows/ci-cd-quality-gate.yml`), entorno efímero de Staging (Docker), suite de humo (`tests/load/k6_smoke_staging.js`) y scripts de despliegue/rollback (`deploy/scripts/`). |
| **Entorno** | Condiciones en que ocurre el estímulo. | Flujo continuo de integración y entrega del Corte 3 en el repositorio Git. |
| **Respuesta** | Lo que el sistema hace ante el estímulo. | En el Caso A, el *Quality Gate* falla con código de salida distinto de cero y bloquea automáticamente las etapas de Staging y Producción. En el Caso B, construye la imagen, la escanea con Trivy, levanta Staging desde cero con PostgreSQL y Redis, ejecuta la prueba de humo con k6 y deja lista la versión para promoción manual a producción con respaldo para rollback. |
| **Medida de la respuesta** | Valor verificable con el que se juzga la respuesta. | **1.** El pipeline bloquea la promoción a staging y producción en el **100 % de los casos** ante fallos de tests, cobertura $< 95\%$ en dominio, hallazgos en Ruff o CVEs críticos en Trivy.<br>**2.** Un cambio válido reconstruye staging desde cero y supera la prueba de humo con k6 en **$\le 15\text{ minutos}$** (medido: $\sim 3.5\text{ min}$) con **0 pasos manuales**.<br>**3.** La reversión (*rollback*) a la versión estable previa se completa en **$\le 90\text{ segundos}$**. |

---

## 4. Plantilla 8.3 — Registro de Análisis de Impacto y Estimación de Esfuerzo (Previo a la Construcción)

*Nota metodológica: De conformidad con la sección 8.3 del Anexo 1, las columnas de **Tipo de cambio** y **Esfuerzo estimado (h)** se diligencian y registran en este commit previo al desarrollo; la columna de **Esfuerzo real (h)** se consolida al cierre de la implementación para el contraste del Entregable 6.*

| Componente | Tipo de cambio (`nuevo`, `modificado`, `sin cambio`) | Esfuerzo estimado (h) | Esfuerzo real (h) | Observaciones de Análisis de Impacto |
| :--- | :---: | :---: | :---: | :--- |
| **`core_domain/entities.py`, `unit_normalizer.py`, `validity_policy.py`, `anomaly_detector.py`, `neutral_comparator.py`** | **sin cambio** | 0.0 h | *Pendiente al cierre* | **Reutilización del 100 % del núcleo existente (`M-09 = 0.00`).** No se altera ninguna regla previa. |
| **`pricing/models.py` (`PriceReport`)** | **sin cambio** | 0.0 h | *Pendiente al cierre* | El modelo `PriceReport` ya fue diseñado como *append-only* con `source_type`, `reliability_status`, `reported_at` e índices compuestos B-Tree. Cero migraciones destructivas. |
| **`core_domain/price_history.py` (Opción A2 — TDD)** | **nuevo** | 3.0 h | *Pendiente al cierre* | Nuevo módulo puro de dominio desarrollado con TDD: ventana de 90 días, exclusión de `ANOMALOUS`, distinción de fuentes/confiabilidad, comparación entre 2 establecimientos y cálculo de tendencia (`%` variación, min, max, promedio). |
| **`tests/unit/test_price_history_tdd.py` (Opción A2 — TDD)** | **nuevo** | 2.5 h | *Pendiente al cierre* | Suite TDD unitaria para las reglas que determinan qué precios entran en la serie de 90 días y comparación multi-establecimiento. |
| **`pricing/services.py`, `pricing/serializers.py`, `pricing/views.py` y `pricecol_api_backend/urls.py` (Opción A2)** | **modificado** | 3.5 h | *Pendiente al cierre* | Se agrega `PriceHistoryQueryService` (con caché en Redis vinculada a la versión del producto) y el endpoint `GET /api/v1/products/{product_id}/price-history/` sin modificar los endpoints existentes. |
| **`tests/integration/test_api_flows.py` y `tests/security/test_privacy_m06.py` (Opción A2)** | **modificado** | 2.0 h | *Pendiente al cierre* | Pruebas end-to-end del escenario `EC-08` y verificación de que el historial cumple `M-06 = 1.00` (Ley 1581: cero exposición del reportante). |
| **`.github/workflows/ci-cd-quality-gate.yml` (Opción B2)** | **nuevo** | 3.5 h | *Pendiente al cierre* | Pipeline CI/CD como código: Quality Gate (`pytest --cov`, `ruff check`, `manage.py check`), escaneo de contenedor con `Trivy`, despliegue automático a Staging + Smoke Test con `k6` y job de promoción manual a Producción. |
| **`tests/load/k6_smoke_staging.js` (Opción B2)** | **nuevo** | 1.5 h | *Pendiente al cierre* | Prueba de humo en `k6` ejecutada automáticamente tras desplegar en Staging (valida `/api/v1/health/`, comparación e historial de 90 días con `p(95) < 1500ms` y `0%` errores). |
| **`deploy/scripts/rollback_release.sh` y `deploy/scripts/verify_quality_gate.py` (Opción B2)** | **nuevo** | 2.0 h | *Pendiente al cierre* | Script automatizado de reversión a versión estable previa en $< 90\text{ s}$ con procedimiento documentado y script verificador del Quality Gate para `EC-12`. |
| **Total Ampliación Corte 3 (`A2` + `B2`)** | **5 nuevos / 2 modificados / 2 sin cambio** | **18.0 h** | *Pendiente al cierre* | **El 100 % del núcleo del Corte 2 permanece intacto (`sin cambio`), demostrando alta capacidad de evolución (`EC-05`).** |
