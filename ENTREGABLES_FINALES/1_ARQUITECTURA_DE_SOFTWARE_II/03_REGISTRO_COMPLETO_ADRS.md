# Documento de Arquitectura: Registros de Decisiones de Arquitectura (ADRs)

**Plataforma Colaborativa de Precios — Nuvora (Armenia y Quindío)**

---

### Información Institucional
- **Institución:** Corporación Universitaria Empresarial Alexander von Humboldt (C.U.E.)
- **Facultad:** Ingenierías y Ciencias Básicas
- **Programa:** Ingeniería de Software
- **Seminario Nuclear:** IV (Arquitectura de Software II y Modelos de Calidad)
- **Docente:** Rubén Darío Díaz Bautista
- **Periodo Académico:** II-2026
- **Ubicación:** Armenia, Quindío, Colombia

### Integrantes del Equipo:
1. Alzate Berrio, Samuel
2. Arias Lemus, Isabella
3. Cuervo Ríos, Nicolás
4. Giraldo Espinosa, Maria Victoria
5. Hoyos Escobar, Valentina

---

## 1. Relación y Resumen Ejecutivo de los ADRs

Un **ADR** (*Architecture Decision Record*, o Registro de Decisión de Arquitectura) es una especificación técnica formal que captura una decisión arquitectónica fundamental del sistema: qué se decidió, por qué motivos se decidió así, qué alternativas fueron evaluadas y qué compensaciones (*trade-offs*) se asumen.

Todos los ADRs de Pricecol siguen la estructura estándar de la industria y la rúbrica del Seminario Nuclear: **Contexto**, **Escenarios y Medidas de Calidad Relacionadas (ISO/IEC 25010/25012/25040)**, **Alternativas Consideradas**, **Decisión** y **Consecuencias (Positivas y Negativas)**.

| ADR | Decisión Arquitectónica | Drivers / Escenarios | Resumen en Pocas Palabras |
| :---: | :--- | :--- | :--- |
| **ADR-01** | Monolito modular en Django con dominio desacoplado | `EC-04`, `EC-05`, `EC-06`, `M-09`, `M-010` | Una sola aplicación ordenada por módulos con núcleo puro en Python es más simple, económica y viable para TDD en el plazo que microservicios (puntaje 4.7 frente a 3.4). |
| **ADR-02** | PostgreSQL como base de datos transaccional | `EC-03`, `EC-04`, `CD-03`, `CD-04`, `M-10` | Concurrencia real MVCC sin bloqueos globales de tabla, funciones estadísticas (`percentile_cont`), `DISTINCT ON` y tipo `NUMERIC` exacto frente a SQLite. Sin PostGIS en v1 (Haversine ligero). |
| **ADR-03** | Coexistencia de precio del comercio y de la comunidad | `EC-02`, `EC-03`, `EC-06`, `M-02`, Ley 1480 | Ningún precio borra ni sobrescribe al otro. Si no coinciden, se muestran ambos con su autoría, fecha y la etiqueta "Discrepancia". |
| **ADR-04** | Vigencia del precio calculada en cada consulta | `EC-02`, `CD-01`, `M-01`, `AH-02` | Ventanas según volatilidad empírica: perecederos (2 a 5 días) vs abarrotes (7 a 15 días). Cálculo en memoria por lectura sin crons masivos que saturen la base de datos. |
| **ADR-05** | Motor antifraude de cuatro capas en memoria | `EC-01`, `EC-03`, `M-03`, `M-05`, `M-06` | Filtra errores de digitación (mediana histórica), ataques coordinados en 15 min, ráfagas/reputación y suplantación comercial (Anti-BOLA/IDOR) en $< 5\text{ ms}$. |
| **ADR-06** | Catálogo de sinónimos y alias moderado | `EC-03`, `CD-04`, `RF-001`, `RF-007` | Nombres coloquiales locales (*"panelita"*, *"blanquillo"*) con índice de trigramas (`pg_trgm`) aprobados por moderación para evitar manipulación entre competidores. |
| **ADR-07** | Ingesta de SIPSA/DANE solo como referencia | `EC-06`, `DA-03`, `S-01` | Precios mayoristas de la central Mercar de Armenia se ingieren en segundo plano y se presentan en bloque aparte; nunca compiten ni se mezclan con el precio minorista de góndola. |
| **ADR-08** | Participación sencilla del tendero de barrio | `EC-01`, `EC-06`, `N-03.1`, `N-03.3` | La comunidad reporta por la tienda (modo pasivo); el tendero confirma con un toque (*"Todo sigue igual"*) en 2 a 3 minutos diarios, sin requerir software POS ni lectores de código de barras. |
| **ADR-09** | Orden neutral por precio por unidad y promociones separadas | `EC-06`, `M-02 = 1.00`, Ley 1480 | Algoritmo matemático puro inmune a monetización o favoritismos comerciales. Las promociones se muestran en bloque separado sin alterar el ranking orgánico. |
| **ADR-10** | Caché distribuido (Redis), Celery y Caché Proxy HTTP | `EC-01`, `EC-02`, `EC-04`, `M-07`, OWASP | Lectura en $< 5\text{ ms}$ (Redis 7), tareas pesadas en segundo plano (Celery 5.7), invalidación atómica por versión de producto/catálogo y revalidación `ETag` / `304 Not Modified` sin payload. |
| **ADR-11** | Patrones arquitectónicos descartados formalmente | `IA-5`, `R-04` (Sección 3.3) | Se justifica el descarte de: Microservicios con Service Mesh, CQRS/Event Sourcing completo, Sagas distribuidas, BFF en v1, Circuit Breaker síncrono y Strangler Fig. |
| **ADR-12** | Seguridad multimedia forense y privacidad por diseño | `EC-03`, `M-06 = 1.00`, Ley 1581 | Purga total de metadatos EXIF/GPS en imágenes, nombres inmutables `UUIDv4`, Magic Bytes (JPEG/PNG/WEBP) e identificadores cifrados de 9 dígitos contra enumeración (OWASP A01). |

---

*(Los 12 documentos individuales y detallados se encuentran disponibles y versionados en el directorio `docs/architecture/adrs/` del repositorio).*


---

# ADR-001: Adopción de Monolito Modular con Núcleo de Dominio Puro y Puerto de Extensión

- **Estado:** Aceptada
- **Fecha:** 2026-11-02
- **Escenarios y Medidas Relacionadas:** `EC-04`, `EC-05`, `M-08`, `M-09`, `M-010`

## Contexto

El sistema Pricecol se construye en dos incrementos dentro de un horizonte de 1 mes por un equipo de 5 estudiantes:
1. **Corte 2 (Núcleo):** Catálogo de productos y presentaciones, directorio de establecimientos, registro colaborativo de precios y comparación neutral por unidad de medida.
2. **Corte 3 (Cambio de Alcance Deliberado):** Incorporación del Módulo Comercial (perfiles voluntarios de comercios, precios oficiales y promociones con reglas).

La medida **M-09** exige que la proporción de componentes preexistentes del núcleo modificados al integrar el módulo comercial sea $\le 0.30$ (meta deseable $\le 0.15$) con $0$ ADRs estructurales rotos, y **M-010** exige una cobertura TDD del dominio $\ge 85\%$ (meta deseable $\ge 95\%$).

## Alternativas Consideradas

1. **Alternativa A — Monolito Modular con Núcleo de Dominio Puro (`core_domain`) y Puerto `PriceSourcePort` (Seleccionada):**
   - Separa las reglas de negocio en un paquete Python puro (`core_domain`) libre de dependencias de base de datos o HTTP.
   - Define el protocolo `PriceSourcePort` para que `ComparePricesQueryService` consuma fuentes de precios de manera polimórfica.
2. **Alternativa B — Arquitectura de Microservicios Distribuidos:**
   - Separar Catálogo, Precios Colaborativos y Módulo Comercial en servicios independientes con bases de datos separadas.
   - *Razón de descarte:* Introduce latencia de red interna que perjudica `EC-04` ($P_{95} \le 2000\text{ ms}$) y sobrecarga operativa desproporcionada para el límite de 1 mes (`M-08`).
3. **Alternativa C — Monolito Django Tradicional Acoplado al ORM (Active Record en Vistas):**
   - Implementar la normalización, vigencia y ordenamiento directamente en `QuerySets` y vistas de Django.
   - *Razón de descarte:* Acopla las reglas del negocio a SQLite/PostgreSQL, impidiendo pruebas unitarias rápidas en memoria (`M-010`) y obligando a reescribir las vistas del núcleo cuando llegue el Módulo Comercial en el Corte 3 (violando `M-09`).

## Decisión

Adoptar la **Alternativa A (Monolito Modular con Núcleo de Dominio Puro)**. El paquete `core_domain` encapsula `UnitNormalizer`, `ValidityPolicy`, `AnomalyDetector`, `NeutralComparator` y `PriceSourcePort`. Los módulos Django `catalog` y `pricing` actúan como adaptadores de persistencia y presentación REST.

## Consecuencias

- **Positivas:**
  - Cobertura de pruebas unitarias TDD del dominio del **99%** (`M-010 = 0.99`), ejecutándose en $< 10\text{ ms}$.
  - En el Corte 3, el Módulo Comercial se implementa como una nueva app Django (`commercial`) que provee un `CommercialPriceSourceAdapter(PriceSourcePort)` sin modificar `core_domain` (`M-09` cercana a $0.00$).
- **Negativas / Trade-offs:**
  - Requiere mapear objetos del ORM a `ComparablePriceEntry` en la capa de servicios (`pricing/services.py`), lo cual añade una pequeña capa de traducción en memoria.


---

# ADR-002: Estrategia CQRS Ligero y Caché Versionada para Resolver la Tensión EC-02 vs. EC-04

- **Estado:** Aceptada
- **Fecha:** 2026-11-02
- **Escenarios y Medidas Relacionadas:** `EC-02`, `EC-04`, `M-01`, `M-07`

## Contexto

En el documento de calidad se identificó una tensión arquitectónica crítica (insumo ATAM):
- **EC-04 (Eficiencia de desempeño):** Las consultas superan con mucho a los registros, con picos de **500 usuarios concurrentes** en fin de semana de quincena, exigiendo un tiempo de respuesta $P_{95} \le 2000\text{ ms}$ (meta deseable $\le 1000\text{ ms}$, medida `M-07`). Esto motiva el uso intensivo de caché.
- **EC-02 (Actualidad del dato - ISO/IEC 25012):** Cuando un comercio o reportante actualiza el precio de un producto, la comparación debe dejar de presentar el precio anterior como vigente dentro de un plazo mínimo. Un TTL de caché largo violaría `EC-02`.

## Alternativas Consideradas

1. **Alternativa A — Pre-cálculo en Escritura + Caché de Lectura con Invalidación por Versión de Producto (Seleccionada):**
   - Al registrar un reporte (`ReportPriceUseCase`), se pre-calcula y almacena el `normalized_ref_price` (`100g`/`100ml`/`1 und`) y se incrementa atómicamente la llave de versión `pricecol:product:{id}:cache_ver`.
   - `ComparePricesQueryService` construye su llave de caché incluyendo dicha versión.
2. **Alternativa B — Cálculo Dinámico en Cada Lectura sin Caché:**
   - Garantiza frescura inmediata (`EC-02`), pero bajo 500 usuarios concurrentes satura la base de datos y degrada el $P_{95}$ por encima de $2000\text{ ms}$ (falla `M-07`).
3. **Alternativa C — Caché Basada Únicamente en Tiempo Fijo (TTL de 30 minutos):**
   - Cumple `EC-04`, pero muestra precios obsoletos durante 30 minutos tras un cambio oficial o comunitario (falla `EC-02`).

## Decisión

Adoptar la **Alternativa A**. Se desacopla el camino de escritura (`ReportPriceUseCase`) del camino de lectura (`ComparePricesQueryService`), pre-calculando la normalización al insertar e invalidando instantáneamente la versión de caché del producto modificado.

## Consecuencias

- **Positivas:**
  - Lecturas repetidas de comparación se sirven desde memoria en $< 5\text{ ms}$, cumpliendo holgadamente `M-07` ($P_{95} \le 1000\text{ ms}$).
  - Cuando entra un nuevo precio, la versión cambia en el acto y la siguiente lectura refleja el precio actualizado en $0\text{ s}$ de retraso (`EC-02`).
- **Negativas / Trade-offs:**
  - Añade dos campos desnormalizados (`normalized_ref_price`, `reference_unit_label`) en la tabla `PriceReport`.


---

# ADR-003: Detección Antifraude en Memoria y Privacidad por Diseño (Ley 1581)

- **Estado:** Aceptada
- **Fecha:** 2026-11-02
- **Escenarios y Medidas Relacionadas:** `EC-01`, `EC-03`, `M-03`, `M-05`, `M-06`

## Contexto

La plataforma enfrenta dos exigencias simultáneas en el flujo de registro de precios:
1. **Tensión Seguridad (`EC-03`) vs. Operabilidad en Góndola (`EC-01`):** Se deben detectar reportes falsos individuales o coordinados por competidores (`M-05 >= 0.80`), pero sin exigir pasos manuales pesados (captchas complejos, fotos obligatorias o verificaciones síncronas externas) que impidan registrar el precio en $\le 15\text{ s}$ con red móvil inestable (`M-03 >= 0.80`).
2. **Privacidad por Diseño (Ley 1581 de 2012 y `M-06 = 1.00`):** La ubicación y la identidad del reportante son datos personales sensibles que no deben exponerse en ningún endpoint público, pero el sistema necesita detectar ráfagas de spam de una misma fuente.

## Alternativas Consideradas

1. **Alternativa A — Heurística Estadística en Memoria (`AnomalyDetector`) + Hash Pseudonimizado SHA-256 (`reporter_hash`) (Seleccionada):**
   - Evaluar en $< 2\text{ ms}$ la desviación porcentual frente a la mediana histórica del producto, la frecuencia de reportes del mismo `reporter_hash` en 10 minutos y la concurrencia de outliers en 15 minutos.
   - No recolectar ni almacenar coordenadas GPS del reportante; transformar el identificador de sesión/usuario mediante `SHA-256(SECRET_KEY + token)` y excluir `reporter_hash` de todos los serializers públicos.
2. **Alternativa B — Exigir Fotografía de Factura/Góndola con OCR Síncrono y Geolocalización GPS Obligatoria:**
   - Eleva la precisión antifraude, pero con conectividad móvil limitada en los pasillos de un supermercado tarda $> 25\text{ s}$ (incumple `EC-01` / `M-03`) y recolecta coordenadas GPS personales riesgosas bajo la Ley 1581 (`M-06`).
3. **Alternativa C — Moderación 100% Manual Posterior sin Filtro Automático:**
   - Deja expuestos precios falsos como vigentes hasta que un moderador humano revise la cola (incumple `EC-03`: *"Los datos no confiables no se presentan como vigentes sin advertencia"*).

## Decisión

Adoptar la **Alternativa A**. Los reportes con puntaje de confianza $< 0.45$ se marcan automáticamente como `ANOMALOUS` y quedan excluidos de las comparaciones públicas; los reportes con confianza entre $0.45$ y $0.74$ se marcan como `LOW_CONFIDENCE` y se muestran únicamente con etiqueta explícita de advertencia.

## Consecuencias

- **Positivas:**
  - Cumplimiento del **100%** en detección sobre el dataset de prueba `E4` (`M-05 = 1.00`, superando el umbral de `0.80` y la meta deseable de `0.90`).
  - Cumplimiento del **100%** en auditoría de privacidad de endpoints (`M-06 = 1.00`).
  - Sobrecarga computacional inferior a $5\text{ ms}$, preservando la agilidad de `EC-01`.
- **Negativas / Trade-offs:**
  - Cuando un producto es completamente nuevo y aún no tiene precios históricos de referencia, el detector solo puede validar límites físicos y ráfagas de spam; por ello se complementa con la carga inicial de precios de referencia (`seed_quindio` / SIPSA).


---

# ADR-004: Algoritmo de Ordenamiento Neutral y Separación Estricta de Promociones (EC-06)

- **Estado:** Aceptada
- **Fecha:** 2026-11-02
- **Escenarios y Medidas Relacionadas:** `EC-06`, `M-02`

## Contexto

El Estatuto del Consumidor (Ley 1480 de 2011) y el escenario `EC-06` establecen que el orden de la comparación debe responder únicamente a los criterios declarados al usuario y que todo contenido promocional debe distinguirse en el **100% de los casos** (`M-02 = 1.00`). Existe el riesgo de que, al incorporar el Módulo Comercial, las promociones alteren el orden orgánico o se confundan con precios regulares.

## Alternativas Consideradas

1. **Alternativa A — Función de Ordenamiento Inmune a Atributos Comerciales + Bloque Separado `promotional_highlights_separated` (Seleccionada):**
   - `NeutralComparator` ordena la lista de candidatos usando exclusivamente la tupla matemática del criterio elegido (`(normalized_ref_price, raw_price, -freshness_score)` para `UNIT_PRICE_ASC`), sin incluir jamás `is_promotional` ni `source_type` como factor de priorización.
   - Adicionalmente, inyecta la etiqueta `CONTENIDO PROMOCIONAL DISTINGUIDO` en `warning_messages` y expone una colección separada `promotional_highlights_separated`.
2. **Alternativa B — Posicionar Ofertas Patrocinadas en los Primeros 2 Lugares con Etiqueta "Patrocinado":**
   - Aunque las etiquete, altera el orden declarado de la lista principal, induciendo a error en pantallas móviles pequeñas e incumpliendo `EC-06` (`M-02 < 1.00`).

## Decisión

Adoptar la **Alternativa A**. Ninguna relación comercial o promoción puede alterar el orden matemático del ranking principal.

## Consecuencias

- **Positivas:**
  - Cumplimiento estricto del $100\%$ en `M-02` (`X = 1.00`), verificado mediante pruebas unitarias TDD y pruebas de integración.
  - Equidad garantizada entre tiendas de barrio y grandes superficies.
- **Negativas / Trade-offs:**
  - El payload JSON de comparación incluye tanto `ranked_results` como `promotional_highlights_separated`.


---

# ADR-005: Despliegue Reproducible mediante Contenedores Docker y Contrato OpenAPI 3

- **Estado:** Aceptada
- **Fecha:** 2026-11-02
- **Escenarios y Medidas Relacionadas:** Flexibilidad (Instalabilidad), Mínimos exigibles de la Guía (Sección 8.1)

## Contexto

La Guía del Seminario Nuclear exige como mínimos obligatorios:
1. Despliegue reproducible del sistema.
2. API documentada con el estándar correspondiente al estilo elegido (OpenAPI 3 para REST).
3. Ejecución automatizada de pruebas TDD y análisis estático.

## Alternativas Consideradas

1. **Alternativa A — Contenedores Docker (`Dockerfile` + `docker-compose.yml`) con Inicialización Automática de Migraciones y Semilla SIPSA + `drf-spectacular` (Seleccionada):**
   - Empaqueta Python, dependencias fijadas, migraciones, carga de datos semilla de Armenia/Quindío (`seed_quindio`) y exposición del servidor en el puerto `8000` con un solo comando `docker compose up --build`.
   - Genera automáticamente el esquema OpenAPI 3 en `/api/schema/` y Swagger UI en `/api/docs/`.
2. **Alternativa B — Despliegue Manual en Máquina Local o VM sin Contenedores:**
   - Propenso a diferencias de entorno entre los 5 integrantes del equipo y el docente evaluador.

## Decisión

Adoptar la **Alternativa A**. Proveer `Dockerfile`, `docker-compose.yml` y el contrato exportado `openapi.yaml` en la raíz del repositorio.

## Consecuencias

- **Positivas:**
  - Cualquier evaluador o integrante del equipo levanta el sistema completo con datos de prueba de Armenia/Quindío en un solo comando reproducible.
  - La documentación OpenAPI 3 permanece siempre sincronizada con los serializers de código.
- **Negativas / Trade-offs:**
  - Requiere tener Docker Desktop o motor OCI instalado para la ejecución contenerizada (aunque sigue pudiendo ejecutarse nativamente con `.venv`).


---

# ADR-01: Monolito Modular en Django con Dominio Desacoplado

- **Estado:** Aceptada
- **Fecha:** 2026-11-02
- **Escenarios y Medidas Relacionadas:** `EC-04`, `EC-05`, `EC-06`, `IA-3`, `IA-4`, `IA-5`, `M-07`, `M-09`, `M-010`, `R-04`

---

## Contexto

El núcleo de la plataforma colaborativa Pricecol debe construirse en el plazo estricto de un corte académico (`R-04`) por un equipo de cinco estudiantes aplicando la disciplina de Desarrollo Guiado por Pruebas (**TDD**). Al mismo tiempo, el sistema debe responder a requisitos arquitectónicos rigurosos:
1. **EC-04:** Eficiencia de desempeño bajo picos de 500 usuarios concurrentes en fin de semana de quincena, con un tiempo de respuesta $P_{95} \le 2000\text{ ms}$ (meta deseable $\le 1000\text{ ms}$, medida `M-07`).
2. **EC-02:** Actualidad del dato; un precio sustituido debe dejar de mostrarse en menos de 60 segundos.
3. **EC-05:** Extensibilidad e incorporación del Módulo Comercial en el Corte 3 sin rediseño estructural del núcleo (`M-09` componentes modificados $\le 0.15$).
4. **Impulsores IA-1 e IA-2:** Exigen que la evaluación de confiabilidad antifraude, la proyección de precios vigentes y la invalidación de la caché ocurran de forma coordinada con consistencia transaccional local.

---

## Alternativas Consideradas

### 1. Alternativa 1 — Monolito Modular con Dominio Desacoplado (Seleccionada — Puntaje: 4.7)
- Una sola base de código en **Python / Django 6 + DRF** desplegada como proceso web unificado, respaldada por **PostgreSQL**, **Redis 7** y un frontend reactivo en **React**.
- Organización modular estricta por contextos delimitados (`accounts`, `catalog`, `pricing`, `core_domain`) con reglas de dominio aisladas en un paquete puro de Python libre de ORM y dependencias de I/O.
- Verificación de fronteras modulares en el pipeline de Integración Continua (CI).

### 2. Alternativa 2 — Servicios Desacoplados con Backend-For-Frontend (BFF) (Puntaje: 3.4)
- Un BFF en FastAPI o Node.js frente a dos microservicios Django independientes: *Servicio de Ingesta/Catálogo* y *Servicio de Consulta/Comparación*, cada uno con su propia base de datos y eventos vía Message Broker.
- *Razón de Descarte:* Aunque permite escalado independiente de lecturas y aislamiento de fallos, introduce saltos de red adicionales que penalizan la conexión móvil lenta en pasillos de supermercados (`EC-01`), depende de consistencia eventual entre servicios (retrasando la actualidad exigida en `EC-02`), obliga a pedir medianas históricas por red externa (`EC-03`) y multiplica el esfuerzo de despliegue y pipelines en un equipo de 5 estudiantes (`R-04`).

---

## Decisión

Adoptar la **Alternativa 1 (Monolito Modular con Dominio Desacoplado)**. 

Las reglas críticas de normalización por unidad de medida (`UnitNormalizer`), vigencia temporal (`ValidityPolicy`), confiabilidad antifraude (`AnomalyDetector`) y ordenamiento neutral (`NeutralComparator`) residen en un núcleo de dominio puro (`core_domain`) sin dependencias de Django, bases de datos ni HTTP (arquitectura hexagonal ligera). 

La interacción se complementa con capas de servicio (`Service Layer`), adaptadores de fuentes de datos (`PriceSourcePort`), objetos de transferencia de datos (`DTOs`) y serializadores DRF. Al contar con una sola base de datos transaccional (PostgreSQL), la consistencia entre evaluación, persistencia e invalidación de caché es atómica, local y directamente verificable.

---

## Consecuencias

### Positivas:
- **Viabilidad operativa:** Un solo framework, un solo despliegue contenerizado y un único pipeline de CI/CD factible en el plazo del semestre.
- **Rendimiento predecible:** `EC-04` se satisface sin la complejidad de sistemas distribuidos mediante caché en memoria, proyecciones indexadas y réplicas del proceso web.
- **Testeabilidad ágil:** Las reglas de dominio se prueban en memoria a nivel unitario en menos de 10 ms, permitiendo una cobertura TDD del **99%** (`M-010 = 0.99`).
- **Modificabilidad protegida:** El desacoplamiento garantiza que la llegada del Módulo Comercial en el Corte 3 se implemente conectando un nuevo adaptador al puerto `PriceSourcePort` sin tocar el motor de comparación (`M-09 \le 0.15`).

### Negativas / Trade-offs:
- **Riesgo de acoplamiento accidental:** Requiere disciplina de equipo y análisis estático con linters para evitar que la lógica de negocio se filtre indebidamente en vistas o modelos del ORM.
- **Punto único de contención en escritura:** Ráfagas intensas de registro podrían competir con lecturas, lo cual se mitiga descargando el trabajo pesado a workers de Celery en segundo plano (ADR-10).
- **Escalabilidad a gran escala:** Si en el futuro el volumen de usuarios creciera órdenes de magnitud o múltiples equipos independientes operaran el sistema, la Alternativa 2 (microservicios) debería ser reevaluada.


---

# ADR-02: PostgreSQL como Base de Datos Transaccional Principal

- **Estado:** Aceptada
- **Fecha:** 2026-11-02
- **Escenarios y Medidas Relacionadas:** `EC-03`, `EC-04`, `CD-03`, `CD-04`, `M-10`

---

## Contexto

El sistema Pricecol opera bajo concurrencia real donde múltiples réplicas del proceso web y trabajadores en segundo plano (Celery) leen y escriben simultáneamente. 

El motor de confiabilidad antifraude requiere calcular estadísticas de agregación (medianas históricas por producto mediante percentiles continuos y selección del reporte verificado más reciente por establecimiento). Asimismo, el catálogo comercial exige búsquedas de texto eficientes, insensibles a tildes o acentos, y tolerantes a errores ortográficos menores. Por último, la normativa del consumidor exige precisión decimal exacta (`NUMERIC`) en precios expresados en pesos colombianos (COP).

---

## Alternativas Consideradas

### 1. PostgreSQL 18 / 16 (Seleccionada)
- Motor relacional cliente-servidor robusto con control de concurrencia multiversión (**MVCC**) y bloqueo a nivel de fila (*row-level locking*), evitando cuellos de botella en escrituras concurrentes.
- Soporte nativo para la función estadística `percentile_cont(0.50)` para medianas exactas, cláusula `DISTINCT ON` para deducir el precio vigente más reciente por tupla `(presentación, establecimiento)`, y extensiones como `unaccent` y `pg_trgm` (trigramas) para búsquedas flexibles.
- Integridad referencial fuerte, tipo `NUMERIC(12, 2)` de punto fijo para dinero y restricciones `CHECK` a nivel de esquema.

### 2. SQLite
- Motor relacional embebido basado en archivo plano.
- *Razón de Descarte:* Posee bloqueo a nivel de base de datos completa (*database-level lock*) ante operaciones de escritura, lo cual genera errores de concurrencia (`database is locked`) cuando el servidor web y los workers de Celery escriben a la vez. No soporta de forma nativa funciones estadísticas como `percentile_cont`, carece de cláusula `DISTINCT ON` y maneja tipado dinámico débil que no garantiza la precisión financiera exigida.

---

## Decisión

Adoptar **PostgreSQL** como motor de base de datos relacional principal para producción y pruebas de integración.

Se decide explícitamente **no incluir PostGIS en la versión 1 (v1)**: a la escala geográfica del municipio de Armenia y el departamento del Quindío, la búsqueda espacial de establecimientos se resuelve de forma óptima y liviana mediante un prefiltro por caja delimitadora (*bounding box*) sobre columnas `latitude` y `longitude` indexadas, calculando la distancia geodésica mediante la fórmula matemática de **Haversine** en la capa de aplicación o en consulta SQL.

---

## Consecuencias

### Positivas:
- **Alta concurrencia:** El proceso web y los workers de Celery leen y escriben en paralelo sin bloquear las tablas completas.
- **Integridad y precisión financiera:** Cero redondeos espurios en precios en COP (`CD-03`, `CD-04`).
- **Capacidades avanzadas:** Agregaciones estadísticas y búsquedas fonéticas/trigramas resueltas eficientemente en el motor de persistencia.

### Negativas / Trade-offs:
- **Dependencia de servicio externo:** El entorno de desarrollo local y el pipeline de pruebas de integración requieren levantar un contenedor de PostgreSQL (gestionado en el archivo de orquestación `docker-compose.yml`), a diferencia de SQLite que reside en un archivo local.


---

# ADR-03: Coexistencia Visible y Transparente del Precio Oficial y el Reporte Comunitario

- **Estado:** Aceptada
- **Fecha:** 2026-11-02
- **Escenarios y Medidas Relacionadas:** `EC-02`, `EC-03`, `EC-06`, `M-02`, `Ley 1480 de 2011`

---

## Contexto

Con la integración del Módulo Comercial en el Corte 3, los establecimientos comerciales registrados y verificados publican sus precios oficiales. Al mismo tiempo, los consumidores y reportantes comunitarios continúan registrando en tiempo real los precios que observan físicamente en las góndolas y cajas de los mismos establecimientos.

Surge el dilema ético y arquitectónico cuando ambos actores reportan un precio diferente para el mismo producto en el mismo local:
- El comercio tiene el derecho legítimo de comunicar su lista oficial de precios.
- El consumidor tiene el derecho a que no se silencie la evidencia real de lo cobrado efectivamente en caja.

Otorgar a cualquiera de los dos el monopolio absoluto sobre el dato rompería la neutralidad (`EC-06`) o la confianza en la plataforma.

---

## Alternativas Consideradas

### 1. Coexistencia Visible con Trazabilidad y Etiqueta de Discrepancia (Seleccionada)
- Ningún precio se sobrescribe ni se elimina.
- Cuando coexistan un precio oficial y un reporte comunitario reciente, la comparación los presenta en paralelo, indicando de forma explícita su procedencia (`OFFICIAL_MERCHANT` vs `COMMUNITY_OCCASIONAL` / `COMMUNITY_FREQUENT`), su marca de tiempo y resaltando la etiqueta de **"Discrepancia"** si no coinciden.

### 2. Prioridad Absoluta al Precio Oficial (Ocultando Reportes Comunitarios)
- *Razón de Descarte:* Un comercio inescrupuloso podría publicar precios artificialmente bajos en la app pero cobrar precios más altos en la caja registradora, anulando el valor de la auditoría ciudadana y violando el Estatuto del Consumidor (Ley 1480 de 2011).

### 3. Prioridad Absoluta al Reporte Comunitario (Sobrescribiendo el Oficial)
- *Razón de Descarte:* Dejaría a los comerciantes indefensos ante reportes erróneos, malintencionados o de competidores desleales, retirándoles el canal legítimo para rectificar información oficial sobre su propio negocio.

---

## Decisión

Adoptar la **Alternativa 1**.

En el modelo de datos de Pricecol, cada registro de precio (`PriceReport`) es una observación inmutable con su tipo de origen (`source_type`), autor y fecha. En la capa de dominio, el comparador neutral agrupa las observaciones vigentes y, ante diferencias entre la fuente oficial y la comunitaria para el mismo establecimiento, preserva ambas y expone la alerta de discrepancia al usuario final.

---

## Consecuencias

### Positivas:
- **Transparencia y neutralidad:** Protege la veracidad del mercado sin sesgarse a favor de las cadenas ni silenciar a la ciudadanía.
- **Extensibilidad limpia (EC-05):** El modelo de datos no sufre mutaciones destructivas al entrar el Módulo Comercial; simplemente se habilita el valor `SourceType.OFFICIAL_MERCHANT` para comercios verificados.

### Negativas / Trade-offs:
- **Carga cognitiva en la interfaz:** La aplicación web y móvil debe diseñar componentes visuales que expliquen claramente la procedencia de cada cifra sin confundir al usuario en pantallas móviles pequeñas.
- **Juicio en el consumidor:** La plataforma no actúa como juez sancionador; entrega la evidencia para que sea el consumidor quien tome una decisión de compra informada.


---

# ADR-04: Vigencia Temporal del Precio Calculada Dinámicamente por Consulta

- **Estado:** Aceptada
- **Fecha:** 2026-11-02
- **Escenarios y Medidas Relacionadas:** `EC-02`, `CD-01`, `M-01`, `AH-02`

---

## Contexto

El atributo de calidad de **Actualidad del Dato** (norma **ISO/IEC 25012**) exige que la plataforma no induzca a error al consumidor presentando precios desactualizados como si estuvieran vigentes.

La "vigencia" en Pricecol aplica estrictamente al **precio observado**, no al estado de descomposición del alimento. La evidencia empírica obtenida en la entrevista de campo con tenderos de Armenia (`AH-02`) demostró que la volatilidad de los precios varía radicalmente según la categoría del producto:
- **Alta Volatilidad (Perecederos: carnes, frutas, verduras, lácteos, huevos):** Cambian cada 1 a 2 días según el abastecimiento en la central mayorista (Mercar).
- **Baja Volatilidad (Abarrotes y Aseo: granos secos, enlatados, detergentes, aceites):** Presentan listas de precios más estables con variaciones quincenales o mensuales.

---

## Alternativas Consideradas

### 1. Cálculo Dinámico de Vigencia en la Consulta según la Volatilidad (Seleccionada)
- Las reglas de vigencia residen en la política de dominio puro `ValidityPolicy`.
- La vigencia se evalúa en el momento de la consulta comparando la antigüedad del reporte frente a la ventana de tiempo propia de su categoría:
  - **Alta Volatilidad (Perecederos):** Plenamente vigente hasta los **2 días**; estado de advertencia (`EXPIRING_SOON`) entre los **días 3 y 5**; expirado (`EXPIRED`) a partir del **día 6** (quedando excluido de la comparación).
  - **Baja Volatilidad (Abarrotes y Aseo):** Plenamente vigente hasta los **7 días**; estado de advertencia entre los **días 8 y 15**; expirado a partir del **día 16**.
- Se complementa con sustitución inmediata (`SUPERSEDED`) si aparece un reporte verificado más reciente para el mismo producto y establecimiento.

### 2. Estado de Vigencia Almacenado y Actualizado mediante Tarea Programada Masiva (Cron)
- *Razón de Descarte:* Un campo estático `is_valid` en base de datos se desactualiza segundo a segundo. Un cron periódico (ej. cada medianoche) que barra miles de registros consumiría I/O innecesario en la base de datos y mostraría datos vencidos durante el lapso entre ejecuciones.

### 3. Plazo de Vigencia Único Fijo para Todos los Productos (ej. 7 días)
- *Razón de Descarte:* Ignora la realidad comercial del departamento del Quindío: un precio de carne o tomate de hace 6 días casi con certeza ya varió en la tienda, mientras que un precio de arroz o atún de 8 días probablemente sigue vigente.

---

## Decisión

Adoptar la **Alternativa 1**.

La política `ValidityPolicy` se ejecuta en memoria como parte del pipeline del comparador. La base de datos almacena el momento exacto de la observación (`reported_at`), y el sistema calcula en tiempo real si el precio es `VALID`, `EXPIRING_SOON`, `SUPERSEDED` o `EXPIRED`. La interfaz expone la frescura con frases claras como *"Reportado hace 4 días (podría haber variado)"*.

---

## Consecuencias

### Positivas:
- **Consistencia absoluta:** Los precios expirados jamás llegan al ranking final de comparación (`EC-02`).
- **Eficiencia en base de datos:** Se eliminan procesos batch masivos que bloqueen tablas solo para actualizar banderas booleanas.
- **Transparencia:** El consumidor conoce la frescura de la información antes de trasladarse al establecimiento comercial.

### Negativas / Trade-offs:
- **Dependencia de la comunidad:** En productos de muy baja rotación de reportes, los precios pueden expirar y dejar temporalmente al producto sin comparaciones activas, incentivando la participación comunitaria para renovar la observación.


---

# ADR-05: Motor Antifraude y Detección de Anomalías de Cuatro Capas

- **Estado:** Aceptada
- **Fecha:** 2026-11-02
- **Escenarios y Medidas Relacionadas:** `EC-01`, `EC-03`, `CD-02`, `M-03`, `M-05`, `M-06`, `RNF-003`

---

## Contexto

En una plataforma de precios abierta y colaborativa existe el riesgo constante de manipulación deliberada o involuntaria:
1. **Errores tipográficos humanos:** Digitar un cero de más o de menos (ej. \$40.000 en vez de \$4.000 por una libra de café).
2. **Sabotaje de competidores desleales:** Comerciantes o usuarios maliciosos que intentan dañar la reputación de un negocio reportando precios falsamente inflados o absurdamente bajos.
3. **Spam masivo y ataques coordinados:** Bots o grupos coordinados que saturan el sistema con precios ficticios.
4. **Suplantación de fuentes oficiales (BOLA / IDOR):** Usuarios que intentan emitir precios con procedencia de comercio oficial sin ser los legítimos dueños del establecimiento.

El escenario **EC-03** exige que la detección alcance al menos el **80%** sobre el conjunto de prueba controlado de 100 observaciones (`M-05 \ge 0.80`, deseable $\ge 90\%$), mientras que **EC-01** exige que el reporte se procese en menos de 15 segundos sin fricciones operativas excesivas.

---

## Alternativas Consideradas

### 1. Motor de Confiabilidad Estadístico en Cuatro Capas en Memoria (Seleccionada)
- Ejecuta una canalización defensiva en `< 5 ms`:
  - **Capa 1 (Desviación frente a Mediana Histórica):** Compara el precio normalizado frente a la mediana de los últimos 25 reportes válidos del producto. Desviaciones extremas ($> 35\%$) marcan el reporte como `ANOMALOUS` (excluido del ranking público); desviaciones moderadas ($22\% - 35\%$) asignan confianza baja (`LOW_CONFIDENCE`) y requieren moderación.
  - **Capa 2 (Ataques Coordinados de Outliers):** Si 3 o más cuentas o identificadores distintos reportan precios con desviación $\ge 18\%$ para el mismo local en una ventana de 15 minutos, se penaliza drásticamente el score de confianza ($-0.55$) y se alerta por posible ataque orquestado.
  - **Capa 3 (Control de Ráfagas y Reputación Anti-Farming):** Más de 4 reportes de la misma fuente en 10 minutos activa penalización por spam. Asimismo, múltiples reportes para el mismo par (producto, tienda) dentro de 24 horas no suman reputación acumulativa, bloqueando granjas de karma.
  - **Capa 4 (Control de Acceso y Suplantación Comercial - Anti-BOLA):** Solo comercios verificados por moderación (`is_verified=True`) pueden reportar bajo procedencia `OFFICIAL_MERCHANT`, y exclusivamente sobre locales de los que son propietarios directos (`owner`). Cualquier intento sobre locales ajenos se degrada a fuente comunitaria o se rechaza con `403 Forbidden`.

### 2. Moderación 100% Manual Previa a la Publicación
- *Razón de Descarte:* Generaría un cuello de botella inmanejable. Los precios tardarían horas o días en aparecer, destruyendo la utilidad en tiempo real de la plataforma.

### 3. Exigencia Obligatoria de Fotografía de Factura con OCR Síncrono
- *Razón de Descarte:* Viola el escenario `EC-01` (`M-03 \ge 0.80` en $\le 15\text{ s}$). En pasillos de tiendas de barrio o subterráneos con conectividad 3G/H+, subir y procesar fotos obligatorias eleva el tiempo a $> 30\text{ s}$, causando el abandono del usuario.

---

## Decisión

Adoptar la **Alternativa 1**.

El componente `AnomalyDetector` reside en el núcleo de dominio puro (`core_domain/anomaly_detector.py`) y evalúa el contexto en milisegundos. Los reportes sospechosos son enviados automáticamente a la cola de moderación del sistema (`GET /api/v1/moderation/flagged-reports/`) junto con el desglose matemático que motivó la alerta (`anomaly_notes`), permitiendo a los moderadores auditar y tomar acciones disciplinarias con un solo clic.

---

## Consecuencias

### Positivas:
- **Eficacia demostrada:** Detección del **100%** de anomalías sobre el dataset de prueba sintético (`M-05 = 1.00`), superando el umbral de 0.80.
- **Rapidez en góndola:** El flujo de reporte ocurre en milisegundos sin fricción para el usuario legítimo (`EC-01`).
- **Seguridad contra suplantaciones:** Se previene eficazmente la manipulación de precios oficiales por terceros.

### Negativas / Trade-offs:
- **Arranque en frío:** Para productos nuevos sin historial, la detección de la Capa 1 se apoya temporalmente en umbrales físicos absolutos y en la semilla de precios del DANE/SIPSA (ADR-07).


---

# ADR-06: Catálogo de Sinónimos y Normalización Lingüística Moderada

- **Estado:** Aceptada
- **Fecha:** 2026-11-02
- **Escenarios y Medidas Relacionadas:** `EC-03`, `CD-04`, `RF-001`, `RF-007`, `ISO/IEC 25012`

---

## Contexto

En el departamento del Quindío y la región cafetera, los consumidores y tenderos utilizan una rica variedad de modismos y nombres coloquiales para los productos de la canasta familiar (por ejemplo: *"panelita"*, *"blanquillo"*, *"revuelto"*, *"guineo"*, *"chócolo"*, *"cuajada"*).

Para que la búsqueda sea efectiva y la comparación sea científicamente válida:
1. El motor de búsqueda debe entender la terminología local y asociarla al producto molde correspondiente.
2. La comparación entre presentaciones distintas debe restringirse estrictamente a la **misma dimensión física** (masa en gramos/kilogramos, volumen en mililitros/litros, o conteo en unidades), impidiendo sumar peras con manzanas.
3. Se debe impedir que comercios malintencionados introduzcan sinónimos falsos o manipulen términos de búsqueda para desviar clientes hacia sus establecimientos.

---

## Alternativas Consideradas

### 1. Catálogo de Alias y Sinónimos con Moderación Humana (Seleccionada)
- Cada producto molde (`Product`) posee una lista controlada de `aliases` (ej. `["panela", "panelita", "dulce de caña"]`) y una dimensión normalizada fija (`UnitOfMeasure`).
- El catálogo se nutre por tres vías:
  - Carga semilla inicial con los términos más comunes del Quindío.
  - Sugerencias de alias enviadas por los usuarios.
  - Registro de búsquedas fallidas sin resultados (*zero-results search log*), lo que alerta a los moderadores para asociar nuevos modismos legítimos con un solo clic.
- Búsqueda eficiente mediante índices de trigramas (`pg_trgm`) e insensibilidad a tildes (`unaccent`).

### 2. Creación Libre y Descentralizada de Alias por los Usuarios sin Revisión
- *Razón de Descarte:* Desembocaría en la polución del catálogo, términos ofensivos y tácticas desleales de SEO interno donde un comercio asocia términos populares a sus productos exclusivos.

### 3. Catálogo Rígido Estándar sin Soporte de Alias
- *Razón de Descarte:* Frustraría la experiencia del consumidor quindiano, arrojando "0 resultados" ante términos cotidianos y reduciendo la adopción de la plataforma.

---

## Decisión

Adoptar la **Alternativa 1**.

El modelo relacional mantiene la separación estricta: `Product` (producto abstracto molde con categoría y dimensión física inmutable) y `ProductPresentation` (marca comercial, gramaje declarado, código de barras EAN e imagen de referencia). Cualquier adición o modificación de alias requiere aprobación de un usuario con rol `MODERATOR`.

---

## Consecuencias

### Positivas:
- **Calidad de datos (ISO/IEC 25012):** Base de datos limpia, unificada y normalizada.
- **Protección contra competencia desleal:** Ningún actor puede secuestrar términos de búsqueda ajenos.
- **Comparabilidad física exacta (RF-007):** El normalizador de unidades (`UnitNormalizer`) opera sobre dimensiones garantizadas por el catálogo molde.

### Negativas / Trade-offs:
- **Sobrecarga de moderación:** Requiere que el equipo de moderadores dedique tiempo a auditar las sugerencias de alias y las búsquedas fallidas.


---

# ADR-07: Ingesta de SIPSA/DANE Exclusivamente como Fuente Institucional de Referencia Separada

- **Estado:** Aceptada
- **Fecha:** 2026-11-02
- **Escenarios y Medidas Relacionadas:** `EC-06`, `DA-03`, `S-01`

---

## Contexto

En la fase inicial de lanzamiento de una plataforma colaborativa (problema del arranque en frío o *cold-start*), la ausencia de masa crítica de usuarios reportantes puede resultar en un catálogo sin precios observados, disminuyendo el interés de los primeros visitantes.

El Sistema de Información de Precios y Abastecimiento del Sector Agropecuario (**SIPSA**) del **DANE** recopila y publica diariamente los precios de alimentos agrícolas en las principales centrales mayoristas del país, incluyendo la central mayorista **Mercar** en Armenia. Sin embargo, dichos precios corresponden a cotizaciones al por mayor expresadas en bultos, huacales, canastillas o arrobas, y no a precios de góndola minorista al consumidor final.

---

## Alternativas Consideradas

### 1. Carga Inicial Propia de Campo y SIPSA como Referencia Institucional Separada (Seleccionada)
- La plataforma arranca con una semilla real tomada en campo por el equipo en tiendas y supermercados de Armenia (`seed_quindio` / `seed_simulated_market_data`).
- Los boletines del SIPSA se ingieren de forma asíncrona mediante un adaptador desacoplado (`PriceSourcePort`), registrando las cotizaciones bajo la categoría `SourceType.PUBLIC_REFERENCE`.
- Dichos precios se presentan en una sección contextual claramente diferenciada (*"Precio mayorista de referencia en Mercar Armenia"*) y **nunca compiten ni se mezclan en el ranking orgánico de precios minoristas**.

### 2. Conversión Matemática de SIPSA a Precio Unitario e Inclusión en el Ranking General
- *Razón de Descarte:* Dividir el costo de un bulto de 50 kg de papa entre 50 para obtener el precio por kilo y compararlo directamente contra el precio de una tienda de barrio induciría a error grave al consumidor. El consumidor no puede comprar un kilo suelto a precio de bulto mayorista en Mercar, violando la neutralidad y veracidad de la información (`EC-06`).

### 3. Arrancar sin Ninguna Información Previa
- *Razón de Descarte:* Una aplicación vacía desincentiva el registro y genera abandono inmediato durante las pruebas de usuario.

---

## Decisión

Adoptar la **Alternativa 1**.

Las observaciones provenientes de fuentes oficiales/institucionales se etiquetan como `PUBLIC_REFERENCE`. Se emplean exclusivamente como valor de referencia informativo en la interfaz y como línea base de dispersión inicial para el motor antifraude cuando un producto carece de histórico comunitario previo.

---

## Consecuencias

### Positivas:
- **Utilidad inmediata:** La aplicación ofrece información relevante sobre la tendencia de precios en la región desde el día uno.
- **Protección de la confianza del consumidor:** Se evita la distorsión del mercado al no comparar canales mayoristas con comercio al detal.
- **Resiliencia de ingesta:** Al ejecutarse en segundo plano por lotes fuera del camino crítico de las peticiones de usuario, fallos en el portal del DANE no afectan la operatividad del backend ni requieren patrones complejos como *Circuit Breaker*.

### Negativas / Trade-offs:
- **Esfuerzo de recolección de campo:** Obliga al equipo a levantar periódicamente una muestra de precios reales en el terreno para alimentar el arranque minorista.


---

# ADR-08: Mecanismo de Participación de Baja Fricción para Tenderos de Barrio

- **Estado:** Aceptada
- **Fecha:** 2026-11-02
- **Escenarios y Medidas Relacionadas:** `EC-01`, `EC-06`, `N-03.1`, `N-03.3`

---

## Contexto

Las tiendas de barrio tradicionales en Armenia y el Quindío operan con márgenes estrechos, escasa tecnificación y una alta carga operativa. La entrevista presencial de campo realizada a tenderos locales (`AH-02`) reveló dos condiciones ineludibles:
1. Ninguna tienda tradicional cuenta con sistemas POS modernos, lectores de códigos de barras conectados a la nube ni personal dedicado a tareas administrativas digitales.
2. El tendero promedio dispone como máximo de **2 a 3 minutos diarios** para interactuar con una herramienta tecnológica en su teléfono celular.

Exigir flujos complejos de digitalización excluiría a las tiendas de barrio de la plataforma, sesgando la comparación en favor de las grandes cadenas organizadas.

---

## Alternativas Consideradas

### 1. Modelo Híbrido: Modo Pasivo Comunitario y Confirmación Rápida "En un Toque" (Seleccionada)
- **Modo Pasivo (Cero fricción):** La tienda de barrio adquiere presencia y visibilidad en el mapa y en el comparador gracias a los reportes que sus propios vecinos y clientes registran en góndola. El tendero no tiene que hacer nada para aparecer en Pricecol.
- **Modo Activo (2 a 3 minutos al día):** Si el tendero decide verificar su comercio, la plataforma le presenta una interfaz minimalista en su móvil con los precios que la comunidad ha reportado sobre su negocio, permitiéndole:
  - Presionar un botón verde: **"Todo sigue igual"** (confirmación en un toque que renueva la vigencia de los precios reportados).
  - Corregir en la misma fila el valor si hubo una variación en el día.
  - La confirmación cuenta como precio oficial del comercio (`OFFICIAL_MERCHANT`), limitada a una vez por día por producto y registrada en la bitácora de auditoría.

### 2. Exigir Integración con Sistemas POS o Lectores de Código de Barras
- *Razón de Descarte:* Impondría barreras económicas y de hardware insalvables para el comercio tradicional de barrio.

### 3. Exigir que el Tendero Digite Manualmente su Catálogo Completo
- *Razón de Descarte:* Supera con creces el límite de tiempo de 3 minutos diarios, provocando el abandono inmediato de la aplicación.

---

## Decisión

Adoptar la **Alternativa 1**.

El diseño del backend y de los endpoints del rol `MERCHANT` prioriza acciones atómicas por lotes, permitiendo actualizar o confirmar los precios de los productos más vendidos de la tienda en segundos sin fricción tecnológica.

---

## Consecuencias

### Positivas:
- **Inclusión y equidad comercial:** Permite a la tienda tradicional de esquina competir en igualdad de condiciones de visibilidad frente a supermercados de cadena sin costo de licenciamiento.
- **Respeto a la realidad del usuario:** Cumple estrictamente con el presupuesto temporal de 2 a 3 minutos diarios manifestado en la investigación de campo.

### Negativas / Trade-offs:
- **Dependencia de la comunidad en modo pasivo:** Si los clientes no reportan con frecuencia sobre una tienda específica, sus precios perderán vigencia y saldrán del ranking hasta que alguien los registre nuevamente.
- **Riesgo de confirmaciones automáticas a ciegas:** Se mitiga limitando las confirmaciones masivas a un máximo de una vez cada 24 horas y auditando discrepancias reportadas por los clientes posteriores.


---

# ADR-09: Ordenamiento Neutral por Precio por Unidad y Separación Estricta de Promociones

- **Estado:** Aceptada
- **Fecha:** 2026-11-02
- **Escenarios y Medidas Relacionadas:** `EC-06`, `M-02`, `RNF-007`, `Ley 1480 de 2011 (Estatuto del Consumidor)`

---

## Contexto

El Estatuto del Consumidor colombiano (Ley 1480 de 2011) y el escenario de calidad **EC-06** exigen que el ordenamiento de una plataforma de comparación de precios responda de forma transparente y predecible a los criterios matemáticos declarados al usuario. Adicionalmente, cualquier contenido publicitario, patrocinado o promocional debe distinguirse de manera inequívoca en el **100% de los casos** (`M-02 = 1.00`).

Al incorporar el Módulo Comercial existe el peligro latente de que los comercios paguen por destacar productos, alterando de forma oculta el orden del ranking o desplazando a tiendas más baratas que no cuentan con presupuesto publicitario.

---

## Alternativas Consideradas

### 1. Motor de Comparación Inmune a Relaciones Comerciales y Bloque Promocional Separado (Seleccionada)
- El comparador neutral (`NeutralComparator` en `core_domain`) es una función matemática pura que solo admite criterios objetivos declarados por el usuario:
  - `UNIT_PRICE_ASC` (orden primario por defecto: precio normalizado por unidad de medida estándar `100g`, `100ml` o `1 unidad`).
  - `RAW_PRICE_ASC` (orden por precio nominal del empaque).
  - `FRESHNESS_DESC` (orden por antigüedad y frescura del dato).
- El algoritmo desconoce por completo cualquier atributo comercial, monetización o tamaño del negocio.
- Las promociones (`is_promotional=True`) se extraen y se entregan en una colección independiente (`promotional_highlights_separated`) para renderizarse en un bloque visual claramente demarcado.

### 2. Intercalar Ofertas Patrocinadas en los Primeros Lugares con Etiqueta "Patrocinado"
- *Razón de Descarte:* Aunque se añada una etiqueta textual pequeña, ubicar un precio más caro en la primera posición induce a error en pantallas móviles pequeñas, distorsiona la neutralidad y viola la métrica `M-02` ($M\text{-}02 < 1.00$).

### 3. Delegar el Ordenamiento a la Capa de Presentación (Frontend / BFF)
- *Razón de Descarte:* Dispersa la lógica de negocio, impide la verificación con pruebas unitarias TDD reproducibles en el backend y abre la puerta a inconsistencias entre clientes web y móviles.

---

## Decisión

Adoptar la **Alternativa 1**.

El ranking principal de comparación es matemáticamente neutral y reproducible. Ningún comercio puede comprar posiciones dentro de la lista orgánica.

---

## Consecuencias

### Positivas:
- **Cumplimiento estricto de la ley:** Protección de los derechos del consumidor y garantía de neutralidad auditada (`M-02 = 1.00`).
- **Equidad comercial:** Una tienda de barrio con el precio más bajo por kilo aparecerá siempre en el puesto número uno, por encima de una gran cadena multinacional.
- **Testeabilidad total:** El comportamiento del comparador se verifica exhaustivamente en memoria con pruebas unitarias TDD.

### Negativas / Trade-offs:
- **Estructura de respuesta dual:** El payload de la API debe devolver dos colecciones diferenciadas: `ranked_results` y `promotional_highlights_separated`.


---

# ADR-10: Estrategia de Caché Distribuido con Invalidación Reactiva, Tareas en Segundo Plano y Caché Proxy HTTP

- **Estado:** Aceptada (Actualizada tras implementación)
- **Fecha:** 2026-11-02 (Revisada: 2026-11-13)
- **Escenarios y Medidas Relacionadas:** `EC-01`, `EC-02`, `EC-04`, `IA-1`, `IA-2`, `M-01`, `M-03`, `M-07`, `OWASP A01/A05`

---

## Contexto

En el análisis de requerimientos de Pricecol existe una marcada asimetría de tráfico: las operaciones de lectura (consumidores comparando precios) superan ampliamente a las operaciones de escritura (reportes de góndola). Durante fines de semana y quincenas, la concurrencia alcanza **500 usuarios simultáneos**, requiriendo un tiempo de respuesta $P_{95} \le 2000\text{ ms}$ (meta deseable $\le 1000\text{ ms}$, medida `M-07`).

Esto motiva el uso de caché agresivo. Sin embargo, el escenario **EC-02** prohíbe terminantemente mostrar precios sustituidos u obsoletos más allá de unos pocos segundos. Un simple TTL largo de caché violaría la veracidad de la información. Al mismo tiempo, el registro de un precio debe completarse en $\le 15\text{ s}$ en redes móviles débiles (`EC-01`), por lo que tareas pesadas (auditoría forense, re-cálculos de rankings y sincronización de índices) no pueden ejecutarse de forma síncrona en el hilo HTTP del servidor web.

---

## Alternativas Consideradas

### 1. Arquitectura de Tres Capas: Caché Distribuido (Redis) + Worker Asíncrono (Celery) + Middleware de Caché Proxy HTTP (Seleccionada)
- **Caché en Memoria Distribuido (Redis 7):** Almacena rankings de comparación pre-calculados serializados.
- **Invalidación Reactiva Basada en Versiones:** Cada producto y el catálogo global poseen llaves atómicas de versión (`pricecol:product:{id}:cache_ver` y `pricecol:catalog:cache_ver`). Cuando un precio es reportado o aprobado, la versión se incrementa inmediatamente en memoria ($O(1)$), invalidando al instante las llaves derivadas de caché sin requerir barridos lentos de claves.
- **Procesamiento en Segundo Plano (Celery 5.7):** Tareas costosas (`pricing.prewarm_product_comparison_cache_task`, `accounts.record_audit_event_task`, `pricing.evaluate_catalog_price_validity_task`) se despachan asíncronamente mediante `transaction.on_commit()` hacia colas de Redis, liberando la respuesta HTTP en milisegundos.
- **Caché Proxy HTTP / Edge & Client Cache (`HttpProxyCacheMiddleware`):**
  - Los endpoints públicos de lectura (`/api/v1/products/{id}/compare/`, `/payment-methods/`, etc.) emiten cabeceras `Cache-Control: public, s-maxage=120, stale-while-revalidate=60` y un `ETag` determinístico vinculado a la versión de Redis.
  - Peticiones condicionales de proxies o navegadores con `If-None-Match` se cortocircuitan en $O(1)$ devolviendo **`304 Not Modified` con 0 bytes de carga**, ahorrando ancho de banda móvil.
  - Endpoints privados (`/api/v1/auth/*`, `/api/v1/moderation/*`, `?mine=true`) emiten estrictamente `Cache-Control: no-store, no-cache, private, must-revalidate` para prevenir ataques de **Web Cache Deception** (OWASP).

### 2. Cálculo en Cada Lectura sin Caché Directamente contra la Base de Datos
- *Razón de Descarte:* Con 500 usuarios concurrentes, las consultas repetidas de agregación saturan el pool de conexiones de PostgreSQL y disparan el $P_{95}$ por encima de los 5 segundos (falla `EC-04`).

### 3. Caché Exclusivamente Basada en Tiempo Fijo (TTL de 30 o 60 minutos)
- *Razón de Descarte:* Cumple la velocidad, pero muestra precios viejos durante todo el tiempo de vida del caché, violando directamente `EC-02`.

---

## Decisión

Adoptar la **Alternativa 1**.

Se implementó el stack desacoplado:
1. **Redis 7** en contenedor Docker como almacén de caché distribuido y broker de mensajería.
2. **Celery 5.7** operando en worker dedicado para ejecutar tareas asíncronas fuera del ciclo de vida de la petición HTTP.
3. **`HttpProxyCacheMiddleware`** registrado en la tubería de Django para el manejo de cabeceras de borde, validación `ETag`, respuestas `304` y configuración de proxy inverso Nginx (`deploy/nginx/pricecol_proxy_cache.conf`) con directiva `proxy_cache_lock on;` (anti-estampida de caché).

---

## Consecuencias

### Positivas:
- **Tiempos de respuesta excelentes:** Lecturas repetidas desde caché se sirven en $< 5\text{ ms}$, cumpliendo sobradamente `M-07` ($P_{95} \le 1000\text{ ms}$).
- **Actualidad instantánea (EC-02):** Un cambio de precio invalida atómicamente la versión y la siguiente lectura sirve el nuevo precio con 0 segundos de retraso.
- **Ahorro masivo de red móvil:** Revalidación con `304 Not Modified` sin re-transmitir el cuerpo JSON.
- **Seguridad perimetral:** Rutas administrativas y datos privados blindados contra almacenamiento indebido en proxies compartidos.

### Negativas / Trade-offs:
- **Componentes adicionales de infraestructura:** Requiere desplegar y monitorear el servicio Redis y los workers de Celery junto al proceso web de Django.
- **Degradación elegante obligatoria:** El middleware y los servicios deben contar con fallbacks a caché local (`LocMemCache`) o ejecución síncrona si Redis no está disponible temporalmente.


---

# ADR-11: Registro y Justificación de Patrones Arquitectónicos Descartados

- **Estado:** Aceptada
- **Fecha:** 2026-11-02
- **Escenarios y Medidas Relacionadas:** `IA-5`, `R-04`, Sección 3.3 de la Guía de Arquitectura

---

## Contexto

Durante el proceso de diseño arquitectónico y análisis de compensaciones (**ATAM**) se evaluaron diversos patrones de diseño y arquitecturas comunes en la industria del software para sistemas distribuidos y de alta concurrencia.

Dejar formalmente documentadas las razones técnicas y contextuales por las cuales dichos patrones **no fueron adoptados** en la versión inicial (v1) de Pricecol previene la reapertura improductiva de debates técnicos sin que medie nueva evidencia empírica o un cambio en los requerimientos del negocio.

---

## Patrones Evaluados y Descartados

### 1. CQRS Completo con Event Sourcing
- *Descripción:* Separar físicamente las bases de datos de lectura y escritura, almacenando el estado exclusivamente como una secuencia inmutable de eventos de dominio (`PriceReportCreated`, `PriceAnomalousFlagged`, etc.).
- *Razón de Descarte:* El modelo de datos de Pricecol ya cuenta con un historial inmutable y acumulativo de observaciones de precios (`PriceReport`). Implementar versionado formal de eventos y reconstrucción de agregados añade una sobrecarga cognitiva y operativa que no resuelve ningún requerimiento funcional no cubierto y amenaza el plazo del proyecto (`R-04`). Se adoptó un **CQRS ligero en la capa de servicios** (separando `ReportPriceUseCase` de `ComparePricesQueryService`) sobre la misma base de datos.

### 2. Microservicios con Service Mesh (Istio / Linkerd)
- *Descripción:* Fragmentar el backend en microservicios independientes para Catálogo, Reportes, Tiendas, Moderación y Comparación, comunicados por gRPC con una malla de servicios.
- *Razón de Descarte:* Ningún escenario de calidad a la escala prevista (500 usuarios concurrentes en el departamento del Quindío) justifica los costos de serialización de red, orquestación de Kubernetes ni la complejidad del despliegue para un equipo de 5 estudiantes (`IA-5`).

### 3. Sagas Distribuidas (Orquestación / Coreografía)
- *Descripción:* Coordinar transacciones de larga duración a través de múltiples servicios independientes con eventos de compensación.
- *Razón de Descarte:* Al operar sobre un monolito modular con base de datos única (PostgreSQL), el sistema aprovecha transacciones **ACID nativas locales** (`@transaction.atomic`), garantizando consistencia inmediata sin riesgo de estados intermedios inconsistentes ni necesidad de transacciones de compensación.

### 4. Backend-For-Frontend (BFF) Dedicado en v1
- *Descripción:* Crear un servicio intermedio en Node.js o FastAPI exclusivo para transformar las respuestas para la aplicación móvil o web.
- *Razón de Descarte:* En la versión 1 existe una sola interfaz cliente principal. Introducir un BFF agrega un salto de red adicional innecesario en conexiones móviles lentas. Se reevaluará en una fase posterior si las necesidades del portal comercial especializado justifican un canal diferenciado.

### 5. Circuit Breaker Síncrono para Ingesta Externa
- *Descripción:* Patrón de aislamiento de fallos en llamadas síncronas hacia APIs de terceros.
- *Razón de Descarte:* La ingesta de fuentes públicas (SIPSA del DANE) se ejecuta en segundo plano por lotes fuera del camino crítico de las peticiones de los usuarios. Si el portal del DANE no responde, la tarea de Celery simplemente reintenta más tarde sin degradar en ningún momento la experiencia de navegación de los consumidores.

### 6. Strangler Fig (Patrón Estrangulador)
- *Descripción:* Migración incremental progresiva de un sistema heredado (*legacy*) hacia una nueva arquitectura.
- *Razón de Descarte:* Pricecol es un desarrollo *greenfield* (diseñado desde cero); no existe un sistema heredado que deba ser reemplazado gradualmente. El patrón queda registrado como una alternativa viable a futuro si alguna vez se decidiera extraer un módulo fuera del monolito.

---

## Decisión

Descartar formalmente estos seis patrones en la versión 1 (v1).

En su lugar, el sistema adopta un conjunto coherente de patrones orientados a la mantenibilidad y eficiencia: **Capas con dependencias hacia el dominio (Hexagonal ligera)**, **Service Layer**, **Repository implícito mediante ORM**, **DTOs**, **Adapter / Port**, **Strategy para ordenamientos**, **Cache-Aside con invalidación reactiva**, **Proyección indexada** y **Claves de idempotencia**.

---

## Consecuencias

### Positivas:
- **Simplicidad arquitectónica:** Menos piezas móviles, menos tecnologías desplegables y menor superficie de ataque (`IA-5`).
- **Claridad de diseño:** El equipo se enfoca en la excelencia del núcleo de dominio y la calidad del código TDD sin dispersión en infraestructura compleja.

### Negativas / Trade-offs:
- Si el proyecto se internacionalizara o escalara a millones de registros con decenas de desarrolladores, varios de estos patrones (en particular el BFF y la extracción de servicios) tendrían que ser reabiertos con base en métricas reales de rendimiento.


---

# ADR-12: Seguridad y Privacidad por Diseño: Sanitización Forense Multimedia y Pseudonimización Criptográfica

- **Estado:** Aceptada
- **Fecha:** 2026-11-10
- **Escenarios y Medidas Relacionadas:** `EC-01`, `EC-03`, `M-06`, `Ley 1581 de 2012 (Habeas Data)`, `OWASP Top 10 (A01, A03, A04, A08)`

---

## Contexto

La plataforma Pricecol permite que usuarios y comercios adjunten evidencia fotográfica (fotos de góndola, recibos, logotipos de establecimientos, fotos de perfil e imágenes representativas de presentaciones y productos). 

Esto introduce dos riesgos de seguridad de primer orden:
1. **Privacidad y Protección de Datos Personales (Ley Estatutaria 1581 de 2012 y Métrica M-06 = 1.00):** Las cámaras de teléfonos inteligentes incrustan automáticamente metadatos EXIF que contienen coordenadas GPS de alta precisión, marca del dispositivo, número de serie y hora exacta. Si estos metadatos se exponen públicamente, se compromete la seguridad física del reportante en su vida cotidiana.
2. **Vulnerabilidades de Carga de Archivos (OWASP Unrestricted File Upload / Path Traversal / DoS):** Riesgo de ejecución de código arbitrario (*polyglot files*, ejecutables camuflados como imágenes), bombas de descompresión (*decompression bombs* por consumo excesivo de memoria) e inyecciones de ruta en el sistema de archivos.
3. **Enumeración Secuencial de Cuentas (OWASP A01 / IDOR):** El uso de identificadores primarios correlativos (`1, 2, 3...`) en usuarios y perfiles permite a un atacante barrer el catálogo y deducir la base de clientes.

---

## Alternativas Consideradas

### 1. Pipeline de Sanitización Forense en Memoria, Nombres UUIDv4 Inmutables e IDs Cifrados (Seleccionada)
- **Sanitización de Imágenes (`ImageSecurityService`):**
  - Límite duro de tamaño de archivo (máximo 5 MB).
  - Inspección de cabeceras binarias reales (*Magic Bytes*) permitiendo exclusivamente `JPEG`, `PNG` y `WEBP`.
  - Límite estricto de resolución (máximo 25 Megapíxeles) para neutralizar bombas de descompresión.
  - **Purga total de metadatos EXIF/GPS:** La imagen se decodifica y se re-dibuja píxel por píxel en un nuevo lienzo en memoria limpia (`Pillow`), descartando todos los diccionarios de metadatos antes de serializarla al disco.
  - **Nombre inmutable `UUIDv4`:** El nombre de archivo original enviado por el cliente se descarta inmediatamente, asignando un identificador UUIDv4 para neutralizar cualquier intento de *Path Traversal*.
  - Cabecera HTTP `Cache-Control: public, max-age=604800, immutable` para contenido estático seguro.
- **Identificadores Cifrados de 9 Dígitos (`generate_encoded_entity_id`):**
  - Generación de IDs primarios no correlativos en el rango de 9 dígitos (`100_000_000` a `2_147_483_647`) combinando HMAC-SHA256 con la llave secreta del sistema y entropía criptográfica (`secrets`).
- **Anonimización del Reportante (`reporter_hash`):**
  - Hash SHA-256 unidireccional con salt secreto del token de sesión, impidiendo la trazabilidad externa de la identidad ciudadana.

### 2. Guardar el Archivo Original Directamente en Disco sin Re-codificar
- *Razón de Descarte:* Expone las coordenadas GPS del reportante en los endpoints públicos (`M-06 < 1.00`, violando la Ley 1581) y abre la puerta a vectores de ataque RCE y Path Traversal en el servidor.

---

## Decisión

Adoptar la **Alternativa 1**.

Todo archivo multimedia pasa obligatoriamente por el servicio transversal `ImageSecurityService.validate_and_sanitize()` antes de tocar el almacenamiento persistente. Las identidades se protegen mediante pseudonimización unidireccional y claves criptográficas de 9 dígitos.

---

## Consecuencias

### Positivas:
- **Cumplimiento legal y ético perfecto:** Métrica `M-06 = 1.00` verificada en pruebas automatizadas de seguridad.
- **Inmunidad contra subida de archivos maliciosos:** Prevención de ataques RCE, XSS vía imágenes SVG y *decompression bombs*.
- **Cero fugas de geolocalización:** Los metadatos GPS son destruidos irremediablemente durante la transcodificación.

### Negativas / Trade-offs:
- **Consumo computacional:** La re-codificación en memoria requiere ciclos de CPU por cada imagen subida, mitigado con el límite de tamaño a 5 MB y el uso de librerías en C (`Pillow`).

