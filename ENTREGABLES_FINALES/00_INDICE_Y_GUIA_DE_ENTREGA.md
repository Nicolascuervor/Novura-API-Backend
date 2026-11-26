# Índice General de Entregables Finales y Guía Operativa para Sustentación
## Proyecto: Pricecol (Nuvora) — Seminario Nuclear IV (Corte 3)
**Integrantes:** Samuel Alzate Berrio, Isabella Arias Lemus, Nicolás Cuervo Ríos, María Victoria Giraldo Espinosa, Valentina Hoyos Escobar.  
**Docente:** Rubén Darío Díaz Bautista  

---

## 📁 Estructura de esta Carpeta (`ENTREGABLES_FINALES`)

Esta carpeta reúne y organiza en tres bloques todos los documentos finales en PDF (**Normas APA 7.ª edición**, `Times New Roman`, `12 pt`, interlineado `1.5`) listos para subir a la plataforma académica y usar el día del stand:

### 1. Carpeta `1_ARQUITECTURA_DE_SOFTWARE_II/`
* **`01_ANEXO_1_ANALISIS_IMPACTO_Y_AMPLIACION_CORTE_3.pdf` (15 páginas, APA 7):**
  * **Qué contiene:** El entregable del Anexo 1 de ampliación del Corte 3 (`A2` Historial y tendencia de precios de 90 días + `B2` Entrega continua con controles de calidad), preguntas de diseño abiertas, `ADR-13` y `ADR-14`, escenarios `EC-08` y `EC-12`, análisis de impacto y contraste de esfuerzo estimado (18.0 h) vs. real (17.0 h).
* **`02_ENTREGABLE_6_EVALUACION_ARQUITECTURA_Y_DOCUMENTO_FINAL_APA7.pdf` (APA 7):**
  * **Qué contiene:** El **Entregable 6 completo de Arquitectura de Software II**:
    1. Evaluación de la arquitectura basada en escenarios (**ATAM**) con riesgos, puntos de sensibilidad y *trade-offs*.
    2. Análisis de cómo respondió la arquitectura al cambio (`EC-05`, `EC-08`, `EC-12`), métrica de modificabilidad del núcleo (`M-09 = 0.00`) y contraste entre esfuerzo estimado (32.0 h total / 18.0 h Corte 3) y esfuerzo real (30.5 h total / 17.0 h Corte 3).
    3. Análisis retrospectivo: **decisiones que el equipo cambiaría y por qué**.
    4. **Documento de arquitectura final actualizado (Modelo C4 Versión 3.0)** integrando Núcleo, Módulo Comercial, Historial de 90 días y Pipeline CI/CD.
    5. **Registro consolidado completo de los 14 ADRs (`ADR-01` al `ADR-14`)**.
* **`02_DOCUMENTO_ARQUITECTURA_C4_Y_DISENO.md` y `03_REGISTRO_COMPLETO_ADRS.md`:**
  * Archivos fuente en Markdown de respaldo.

---

### 2. Carpeta `2_MODELOS_DE_CALIDAD/`
* **`01_INFORME_TDD_COBERTURA_Y_ANALISIS_ESTATICO.pdf` (19 páginas, APA 7):**
  * **Qué contiene:** Evidencia formal de los ciclos TDD (Rojo-Verde-Refactor) sobre el paquete puro `core_domain`, cobertura del **`96.32 %` en `core_domain`**, análisis estático de seguridad SAST (**Ruff + Bandit**) y acciones correctivas.
* **`02_ENTREGABLE_5_Y_6_INFORME_EVALUACION_CALIDAD_25040_25012_CMMI_APA7.pdf` (APA 7):**
  * **Qué contiene:** Los **Entregables 5 y 6 completos de Modelos de Calidad**:
    1. **Entregable 5 — Evaluación del producto conforme al marco ISO/IEC 25040** (las 5 actividades de evaluación y matriz frente a umbrales ISO/IEC 25010:2023).
    2. **Evaluación de la calidad y seguridad de los datos conforme a ISO/IEC 25012** (nuestro punto fuerte empresarial: Exactitud `UnitNormalizer`, Actualidad `ValidityPolicy` + Redis, Credibilidad `AnomalyDetector` 4 capas, Consistencia en historial de 90 días y Confidencialidad EXIF/GPS bajo Ley 1581).
    3. **Resultados de pruebas de integración, de sistema y de carga con Grafana k6** frente a los umbrales de `EC-04` ($p95 = 142.3\text{ ms} \le 2.000\text{ ms}$) y `EC-08` ($p95 = 118.7\text{ ms} \le 500\text{ ms}$).
    4. **Registro formal de incidencias (`INC-01` a `INC-06`) y su tratamiento correctivo** (incluyendo las corridas reales de GitHub Actions `Run #1` a `Run #4`).
    5. **Entregable 6 — Calidad del proceso y plan de mejora:** Reflexión sobre la madurez del proceso seguido por el equipo con referencia conceptual a **CMMI V3.0 (Niveles 2 y 3) e ISO/IEC 330xx**, y plan de mejora continua del producto y del proceso.
* **`02_MATRIZ_TRAZABILIDAD_ISO_25010_25012_25040.md`:**
  * Archivo fuente en Markdown de la matriz de trazabilidad.

---

### 3. Carpeta `3_SUSTENTACION_Y_STAND_5_INTEGRANTES/`
* **`01_GUION_SUSTENTACION_STAND_5_EXPOSITORES_APA7.pdf` (15 páginas, APA 7):**
  * **Qué contiene:** El **guion oficial para los 5 integrantes** (**Isabella Arias, Samuel Alzate, María Victoria Giraldo, Nicolás Cuervo y Valentina Hoyos**), alineado con los **4 indicadores de 25 % de la rúbrica institucional**, en lenguaje natural para todo visitante y destacando como hilo conductor **nuestro punto fuerte empresarial: la Calidad y Seguridad de los Datos**.
* **`02_BANCO_PREGUNTAS_Y_RESPUESTAS_PROFESOR.pdf`:**
  * 16 preguntas de evaluación docente con respuestas argumentadas.
* **`03_GUIA_EXPOSICION_Y_8_PREGUNTAS_ABIERTAS.pdf`:**
  * Resumen ejecutivo de las 8 preguntas abiertas de diseño de la guía del proyecto.

---

## 💻 Comandos Rápidos para Encender el Backend el Día del Stand (PowerShell)

Recuerda abrir **Windows PowerShell** (no `cmd.exe`) y ejecutar siempre primero el `cd` para entrar a la carpeta del proyecto:

### Ventana 1 de PowerShell — Encender el Servidor Web (Django en puerto 8000):
```powershell
cd "C:\Users\nicoc\OneDrive\Documentos\5. Proyects\Pricecol-API-Backend"
.\.venv\Scripts\python.exe manage.py runserver
```

### Ventana 2 de PowerShell — Encender el Procesador Asíncrono (Celery conectado a Redis):
*(Asegúrate de que Docker Desktop esté abierto con el contenedor de Redis activo)*
```powershell
cd "C:\Users\nicoc\OneDrive\Documentos\5. Proyects\Pricecol-API-Backend"
$env:USE_REDIS="True"; $env:CELERY_TASK_ALWAYS_EAGER="False"; .\.venv\Scripts\celery.exe -A pricecol_api_backend worker -l info -P solo
```
