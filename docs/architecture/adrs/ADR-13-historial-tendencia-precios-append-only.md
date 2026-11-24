# ADR-13: Almacenamiento de Solo Inserción (Append-Only) y Serie Temporal de 90 Días para el Historial de Precios (Opción A2)

- **Identificador y título:** ADR-13: Almacenamiento de solo inserción (*Append-Only*) y agregación temporal en el dominio para el historial y tendencia de precios (Opción A2).
- **Estado y fecha:** Aceptado — 24 de noviembre de 2026 (Ampliación de alcance del Corte 3 — Anexo 1).
- **Escenarios relacionados:** **EC-08** (Trazabilidad y actualidad del dato del historial de 90 días — ISO/IEC 25012), **EC-02** (Actualidad del dato $\le 1\text{ min}$), **EC-04** (Eficiencia de desempeño en lectura) y **M-06** (Privacidad por diseño — Ley 1581 de 2012).

---

## 1. Contexto

El Anexo 1 del Corte 3 introduce la funcionalidad **A2. Historial y tendencia de precios**, donde el consumidor consulta cómo ha variado el precio de un producto en uno o varios establecimientos durante los últimos **90 días**, distinguiendo el origen de cada dato (`OFFICIAL_MERCHANT`, `COMMUNITY_VERIFIED`, `COMMUNITY_OCCASIONAL`, `PUBLIC_SOURCE`) y su estado de confiabilidad (`VERIFIED`, `LOW_CONFIDENCE`), sin permitir jamás identificar qué reportante registró cada precio (Ley 1581 de 2012).

Para satisfacer el mínimo exigible y la extensión opcional (comparar la tendencia de un producto entre dos establecimientos en la misma gráfica), el equipo debe resolver tres preguntas de diseño estructurales:
1. ¿Se justifica implementar *Event Sourcing* completo o basta con un almacenamiento relacional de solo inserción (*Append-Only*) en PostgreSQL?
2. ¿Cómo se tratan en el historial los precios marcados como no confiables (`LOW_CONFIDENCE` vs. `ANOMALOUS`)?
3. ¿Cuánto historial se conserva y cómo se evita degradar el almacenamiento y el tiempo de respuesta de las consultas en una VM `e2-micro` de 1 GB de RAM?

---

## 2. Alternativas Consideradas

### Alternativa A: Event Sourcing completo con Event Store separado y proyecciones CQRS
- **Ventajas:** Permite reconstruir estados pasados arbitrarios a partir de un flujo de eventos de dominio (`PriceReportedEvent`, `PriceSupersededEvent`).
- **Desventajas:** Introduce complejidad accidental elevada (sincronización eventual entre el Event Store y las vistas materializadas, versionado de esquemas de eventos y mayor consumo de RAM), innecesaria cuando un reporte de precio es por naturaleza un hecho inmutable en el tiempo.

### Alternativa B: Sobrescritura en tabla principal (`UPDATE`) con tabla secundaria de auditoría por Triggers
- **Ventajas:** La tabla principal solo tiene 1 fila por `(presentación, establecimiento)`.
- **Desventajas:** Rompe el diseño actual del núcleo donde `PriceReport` ya es inmutable, dificulta consultar en una sola lectura la serie de 90 días con su `source_type` y `reliability_status`, y acopla la lógica de negocio a triggers de base de datos difíciles de probar con TDD en `core_domain`.

### Alternativa C (Elegida): Modelo Relacional de Solo Inserción (*Append-Only*) sobre `PriceReport` con Filtro Puro de Serie Temporal en `core_domain`
- **Ventajas:**
  1. **Reutilización del 100 % del esquema persistente:** Desde el Corte 2, la tabla `PriceReport` fue diseñada como un registro inmutable de solo inserción (`append-only`), donde un nuevo precio no hace `UPDATE` sobre el anterior, sino que inserta una nueva fila con `reported_at` indexado (`Index(fields=["presentation", "establishment", "-reported_at"])`).
  2. **Testabilidad mediante TDD puro:** Las reglas que determinan qué precios entran en la serie de 90 días, cómo se filtran los estados de confiabilidad y cómo se calcula la variación porcentual de tendencia se implementan como funciones puras en `core_domain/price_history.py` sin tocar la base de datos.
  3. **Mínimo consumo de recursos en GCP (`e2-micro`):** Usa el mismo motor PostgreSQL 16 y el mismo sistema de versionado de caché en Redis (`get_product_comparison_cache_version_key`), garantizando que cualquier precio nuevo aparezca en el historial inmediatamente (cumpliendo `EC-02` y `EC-08`).

---

## 3. Decisión

Adoptar la **Alternativa C (Almacenamiento de Solo Inserción *Append-Only* con servicio de dominio puro `PriceHistoryService`)**, estableciendo las siguientes reglas de diseño explícitas:

1. **Almacenamiento Append-Only vs. Event Sourcing:** No se adopta *Event Sourcing* completo porque cada reporte de precio es un hecho atómico e inmutable que no sufre mutaciones parciales de estado posteriores (salvo moderación administrativa trazada en `AuditEventLog`). El almacenamiento *append-only* en `PriceReport` con índice compuesto `(presentation_id, establishment_id, -reported_at)` ofrece la misma trazabilidad temporal con $O(\log N)$ de costo de lectura.
2. **Política de inclusión según confiabilidad (`VERIFIED`, `LOW_CONFIDENCE`, `ANOMALOUS`):**
   - Los precios **`ANOMALOUS`** (desviación $> 35\%$ sin evidencia o ráfagas de spam) **se excluyen siempre** de la serie histórica pública para impedir que intentos de sabotaje distorsionen la curva de tendencia.
   - Los precios **`VERIFIED`** se incluyen por defecto en la serie.
   - Los precios **`LOW_CONFIDENCE`** (desviación moderada $22\%–35\%$) se incluyen con el indicador explícito `requires_warning: true` y su estado `reliability_status: "LOW_CONFIDENCE"` para que la gráfica del frontend los represente con un marcador visual diferenciado (o permita filtrarlos mediante el parámetro `include_low_confidence=true|false`).
3. **Política de retención y ventana de consulta:**
   - **En almacenamiento (PostgreSQL):** Se conserva el historial completo en línea durante **365 días** para auditoría e inteligencia de inflación regional (con particionamiento/archivado anual frío posterior). Dado que cada fila de `PriceReport` ocupa $\sim 280\text{ bytes}$, 100.000 reportes anuales representan apenas $\sim 28\text{ MB}$ en disco, sin impacto en el disco de 30 GB de la VM.
   - **En consulta (`GET /api/v1/products/{product_id}/price-history/`):** La ventana por defecto es de **90 días** (acotada entre 1 y 90 días según `EC-08`), soportando el filtro por uno o varios establecimientos (`establishment_ids`) para cubrir tanto el mínimo exigible como la extensión opcional (comparar dos establecimientos en la misma gráfica) y vinculando la clave de caché a la versión del producto (`invalidate_product_comparison_cache`) para que todo cambio se refleje en $< 1\text{ s}$.
4. **Privacidad por Diseño (Ley 1581 de 2012 / `M-06 = 1.00`):** Ningún punto de la serie histórica incluye `reporter_hash`, ID de usuario ni coordenadas del reportante; solo expone `reported_at`, `raw_price`, `normalized_ref_price`, `reference_unit_label`, `source_type`, `reliability_status`, `confidence_score` y `is_promotional`.

---

## 4. Consecuencias

- **Positivas:**
  - Cero migraciones destructivas sobre el esquema de base de datos (`M-09 = 0.00`, estabilidad estructural máxima en la segunda medición de `EC-05`).
  - Cumplimiento simultáneo del mínimo exigible y de la extensión opcional (comparación multi-establecimiento en la misma serie).
  - Respeto absoluto de `M-06 = 1.00` (Habeas Data).
- **Negativas / Trade-offs aceptados:**
  - Si un establecimiento registra múltiples reportes el mismo día para la misma presentación, la serie puede contener varios puntos intradía; se resuelve ordenando cronológicamente (`reported_at ASC`) y entregando además el resumen estadístico del periodo (precio mínimo, máximo, promedio y porcentaje de variación).

---

## 5. Verificación

1. **Suite TDD unitaria (`tests/unit/test_price_history_tdd.py`):** Verifica en `core_domain/price_history.py` el corte exacto de la ventana de 90 días, la exclusión del 100 % de registros `ANOMALOUS`, la distinción de `source_type` (`OFFICIAL_MERCHANT`, `COMMUNITY_VERIFIED`, `COMMUNITY_OCCASIONAL`, `PUBLIC_SOURCE`), el cálculo de tendencia porcentual y la agrupación multi-establecimiento.
2. **Prueba de integración y privacidad (`tests/integration/test_api_flows.py` y `tests/security/test_privacy_m06.py`):** Verifica el endpoint `GET /api/v1/products/{id}/price-history/`, la aparición inmediata de un nuevo precio en la serie (invalidación de caché `EC-02` / `EC-08`) y la ausencia total de PII del reportante.
