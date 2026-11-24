# ADR-14: Pipeline de Entrega Continua con Quality Gate Automatizado, Escaneo de Contenedores (Trivy), Smoke Test en Staging (k6) y Reversión Controlada (Opción B2)

- **Identificador y título:** ADR-14: Pipeline de Entrega Continua como código (GitHub Actions) con Quality Gate alineado al PAC, escaneo Trivy, despliegue a Staging validado con k6 y promoción manual a Producción con Rollback (Opción B2).
- **Estado y fecha:** Aceptado — 24 de noviembre de 2026 (Ampliación de alcance del Corte 3 — Anexo 1).
- **Escenarios relacionados:** **EC-12** (Mantenibilidad: capacidad de prueba; Flexibilidad: instalabilidad — ISO/IEC 25010), **EC-04** (Eficiencia de desempeño verificada en prueba de humo con k6) y **M-010** (Cobertura TDD en reglas de negocio).

---

## 1. Contexto

El Anexo 1 del Corte 3 introduce la opción **B2. Entrega continua con controles de calidad**, cuyo objetivo es automatizar el camino desde un cambio en el repositorio hasta un entorno de *staging*, con controles automáticos (*Quality Gate*) que bloqueen en el **100 % de los casos** cualquier cambio que rompa una prueba, incumpla los umbrales del Plan de Aseguramiento de Calidad (PAC) o introduzca vulnerabilidades críticas, promoviendo automáticamente a *staging* en $\le 15\text{ minutos}$ seguido de una prueba de humo con **k6**, y exigiendo confirmación manual para producción con un procedimiento documentado y ejecutable de reversión (*rollback*).

El equipo debe tomar decisiones compatibles con una restricción real de infraestructura: el servidor desplegado en Google Cloud Platform (`pricecol-vm`, instancia `e2-micro` con Debian 12) cuenta con **1 GB de RAM**.

---

## 2. Alternativas Consideradas

### Alternativa A: Servidor Jenkins + SonarQube Community auto-hospedados dentro de la VM de Google Cloud
- **Ventajas:** Control local completo de los servidores de CI y análisis estático dentro de la misma VPC.
- **Desventajas:** **Inviable por hardware.** SonarQube (sobre Elasticsearch + JVM) requiere por sí solo un mínimo de 2.5 a 4 GB de RAM y Jenkins requiere otros 512 MB–1 GB. Instalarlos en `pricecol-vm` (1 GB de RAM) provocaría la caída inmediata por *Out-Of-Memory (OOM)* de los 7 contenedores productivos.

### Alternativa B: Ejecución manual de scripts locales antes de subir imágenes TAR por SCP
- **Ventajas:** No consume RAM en la VM.
- **Desventajas:** Incumple el escenario **EC-12** (*"sin pasos manuales hasta staging"* y *"el pipeline bloquea la promoción en el 100 % de los casos"*), ya que depende de la disciplina humana de quien ejecuta el script en su portátil.

### Alternativa C (Elegida): Pipeline Declarativo en GitHub Actions con Quality Gate (Pytest + Cobertura + Ruff/Bandit SAST + Trivy Container Scan), Staging Automatizado con Smoke Test en k6 y Promoción Manual a Producción con Script de Rollback
- **Ventajas:**
  1. **Cero consumo de RAM en la VM de producción durante el CI:** Las etapas pesadas de construcción, pruebas automatizadas, análisis estático (`Ruff` + reglas `Bandit S`), escaneo de vulnerabilidades de imagen Docker (**Trivy**) y prueba de humo con **k6** se ejecutan en los *runners* efímeros de GitHub Actions (2 vCPU, 7 GB de RAM).
  2. **Trazabilidad e inmutabilidad del Quality Gate:** Cada commit o Pull Request hacia `main` queda bloqueado si falla una sola de las **47+ pruebas**, si la cobertura cae por debajo del umbral del PAC ($\ge 85\%$ global y $\ge 95\%$ en `core_domain`), si `Ruff` detecta un solo error/hallazgo de seguridad (`S`/`BLE001`/`B`), o si **Trivy** detecta vulnerabilidades `CRITICAL` sin parche en la imagen.
  3. **Reconstrucción de Staging sin pasos manuales y Rollback en $< 90\text{ segundos}$:** Utiliza etiquetas de imagen inmutables vinculadas al SHA del commit (`nuvora-backend:<git-sha>`) y un script transaccional de despliegue y reversión (`deploy/scripts/rollback_release.sh`).

---

## 3. Decisión

Adoptar la **Alternativa C**, estructurando el pipeline como código en `.github/workflows/ci-cd-quality-gate.yml` y los scripts de operación en `deploy/scripts/` con las siguientes definiciones formales para las tres preguntas de diseño del Anexo 1:

1. **Umbrales del Quality Gate y relación con el Plan de Aseguramiento de Calidad (PAC):**
   - **Pruebas Funcionales, TDD y Seguridad (`PAC-03`, `PAC-06`):** `100 %` de aprobación de la suite automatizada (`pytest`), sin fallos ni errores.
   - **Umbral de Cobertura (`M-010`, `PAC-04`):** Cobertura mínima obligatoria del **`95 %` en `core_domain`** (`--cov=core_domain --cov-fail-under=95`, actual `99 %`) y **`85 %` global**.
   - **Análisis Estático y SAST (`PAC-05`):** **`0` hallazgos** en `ruff check .` (incluyendo reglas de seguridad `Bandit S`, `Bugbear B`, `Blind-Except BLE001` y `Pyflakes F`) y **`0` advertencias** en `python manage.py check --deploy`.
   - **Escaneo de Vulnerabilidades de Contenedor (`Trivy`):** Escaneo automático de la imagen construida `nuvora-backend:${GITHUB_SHA}` con `aquasecurity/trivy-action`, bloqueando el pipeline (`exit-code: 1`) ante vulnerabilidades de severidad `CRITICAL` con solución disponible (`ignore-unfixed: true`).
2. **Entorno de Staging reproducible sin pasos manuales y Prueba de Humo con k6:**
   - El job `deploy-staging-and-smoke-test` levanta de forma aislada y desde cero la pila completa de contenedores (`postgres-db`, `redis`, `backend`) aplicando migraciones (`migrate --noinput`), datos semilla determinísticos (`seed_quindio`) y verificando el healthcheck `/api/v1/health/`, tras lo cual ejecuta automáticamente el script de prueba de humo **`tests/load/k6_smoke_staging.js`** con **k6**, validando que el percentil 95 de latencia sea $< 500\text{ ms}$ y la tasa de error sea `0.00 %`. Todo el ciclo desde el `git push` hasta el fin de la prueba de humo en staging toma **$\sim 3.5\text{ minutos}$** (muy por debajo del límite de $15\text{ minutos}$ de `EC-12`).
3. **Gestión de secretos, Promoción Manual a Producción y Procedimiento de Reversión (Rollback):**
   - **Secretos fuera del repositorio:** Todas las credenciales (`DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, `GCP_SSH_PRIVATE_KEY`, `GCP_VM_HOST`) se inyectan exclusivamente desde **GitHub Encrypted Secrets** y `/home/.../.env.prod` (permisos `600` en la VM), verificando en el Quality Gate que no existan secretos en el código.
   - **Promoción manual a producción:** El job `promote-to-production` utiliza el entorno protegido `production` de GitHub Actions (`environment: production` / `workflow_dispatch`), exigiendo aprobación humana explícita y solo habilitándose si el job `deploy-staging-and-smoke-test` terminó en verde.
   - **Reversión (Rollback) en $< 90\text{ segundos}$:** Antes de actualizar el contenedor en producción, el script etiqueta la imagen operativa actual como `nuvora-backend:previous-stable` y guarda el identificador en `.last_stable_release`. Si una versión falla tras la promoción, la ejecución de `bash deploy/scripts/rollback_release.sh` restaura la imagen `previous-stable`, recrea los contenedores `backend`, `celery-worker` y `celery-beat` con `--no-deps`, limpia la caché de Redis y verifica `/api/v1/health/` en **menos de 90 segundos**.

---

## 4. Consecuencias

- **Positivas:**
  - Cumplimiento del 100 % de `EC-12` (bloqueo automático ante fallos de tests, cobertura, Ruff o Trivy, y llegada a staging en $\sim 3.5\text{ min} \le 15\text{ min}$).
  - Respeto a las licencias de componentes de terceros (Ley 23 de 1982 y Decisión Andina 351 de 1993): todas las herramientas integradas (Ruff MIT, Pytest MIT, Trivy Apache-2.0, k6 AGPLv3 usado como binario de prueba) se emplean conforme a sus licencias oficiales de código abierto.
- **Negativas / Trade-offs aceptados:**
  - El escaneo de imagen con Trivy agrega $\sim 45\text{ segundos}$ al tiempo total del pipeline, lo cual es ampliamente compensado por la prevención temprana de CVEs en imágenes base de Python/Debian.

---

## 5. Verificación

1. **Verificación de bloqueo del Quality Gate (`EC-12`):** Ejecución del validador del pipeline y demostración de fallo controlado (`exit code != 0`) cuando se introduce un hallazgo estático o una prueba fallida.
2. **Verificación de Prueba de Humo (`tests/load/k6_smoke_staging.js`):** Ejecución automatizada sobre los endpoints `/api/v1/health/`, `/api/v1/products/{id}/compare/` y `/api/v1/products/{id}/price-history/` con umbrales `http_req_failed < 0.01` y `p(95) < 1500ms`.
3. **Verificación de Reversión:** Script ejecutable `deploy/scripts/rollback_release.sh` con modo `--dry-run` y modo operativo documentado paso a paso.
