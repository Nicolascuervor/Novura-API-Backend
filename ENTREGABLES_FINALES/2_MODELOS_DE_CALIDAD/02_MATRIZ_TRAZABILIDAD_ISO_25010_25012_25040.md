# Especificación de Calidad, Calidad de Datos (ISO/IEC 25012) y Matriz de Trazabilidad

**Proyecto:** Plataforma Colaborativa de Comparación de Precios — Pricecol  
**Normas aplicadas:** ISO/IEC 25010:2023, ISO/IEC 25012:2008, ISO/IEC 25021/25022/25023, ISO/IEC 25040:2024  

---

## 1. Justificación del Modelo ISO/IEC 25010:2023 frente a Modelos Clásicos (McCall y FURPS+)

| Criterio | McCall (1977) | FURPS+ (Grady, 1992) | ISO/IEC 25010:2023 + ISO/IEC 25012 (Adoptado) |
| :--- | :--- | :--- | :--- |
| **Capacidad de interacción e Inclusividad** | Limitado a "Usabilidad" básica de operación. | Agrupa factores humanos y estética sin desglose de accesibilidad ni autodescriptividad. | **Superior:** Incorpora explícitamente *Capacidad de interacción*, *Inclusividad* (WCAG 2.2 AA, `M-04`), *Protección contra errores de usuario* y *Autodescriptividad* (`EC-01`, `EC-06`). |
| **Calidad de Datos Colaborativos** | No diferencia calidad del código de la calidad del dato. | Trata los datos solo como requisito funcional o de persistencia. | **Esencial para Pricecol:** Se integra nativamente con **ISO/IEC 25012**, permitiendo medir **Actualidad** (`EC-02`) y **Credibilidad** (`EC-03`) sobre reportes ciudadanos. |
| **Marco de Medición y Evaluación** | Métricas subjetivas sin estándar de evaluación formal. | Sin división normalizada entre elementos de medida y proceso de evaluación. | **Estándar SQuaRE completo:** Conecta con `25021/25022/25023` ($X = A/B$) y el proceso de decisión de `25040` (*Cumple*, *Cumple con observación*, *No cumple*). |

---

## 2. Características Críticas de Calidad de Datos (ISO/IEC 25012)

En una plataforma colaborativa donde confluyen consumidores ocasionales, reportantes frecuentes y comercios con intereses propios, la calidad de los datos es tan crítica como la del software:

1. **Actualidad (*Currentness* — `EC-02`):**
   - **Problema:** Los precios de productos perecederos y abarrotes cambian semanalmente o por promociones de quincena.
   - **Mecanismo implementado:** `ValidityPolicy` en [`core_domain/validity_policy.py`](../../core_domain/validity_policy.py) calcula el `freshness_score` ($0.00$ a $1.00$), marca como `SUPERSEDED` cualquier precio anterior apenas se registra uno nuevo verificado en el mismo establecimiento, y expira automáticamente precios que superen la ventana de su categoría (`7 días` perecederos, `15 días` abarrotes).
2. **Credibilidad (*Credibility* — `EC-03`):**
   - **Problema:** Usuarios malintencionados o competidores pueden inyectar precios falsos para desviar clientes.
   - **Mecanismo implementado:** `AnomalyDetector` en [`core_domain/anomaly_detector.py`](../../core_domain/anomaly_detector.py) contrasta cada reporte contra la mediana histórica verificada, ráfagas por `reporter_hash` en 10 minutos y reportes coordinados en 15 minutos (`M-05 = 1.00`).
3. **Exactitud y Consistencia Semántica (*Accuracy & Consistency* — `M-01`):**
   - **Problema:** Comparar una bolsa de leche de `900 ml` contra una de `1.1 L` por su precio de empaque induce a error al consumidor.
   - **Mecanismo implementado:** `UnitNormalizer` en [`core_domain/unit_normalizer.py`](../../core_domain/unit_normalizer.py) normaliza toda presentación a su unidad de referencia (`100g`, `100ml`, `1 und`) con aritmética `Decimal` exacta.
4. **Confidencialidad del Dato Personal (*Confidentiality* — `M-06` / Ley 1581 de 2012):**
   - **Mecanismo implementado:** Cero recolección de coordenadas GPS del reportante, pseudonimización irreversible `SHA-256` (`reporter_hash`) y exclusión total en serializers públicos (`tests/security/test_privacy_m06.py`).

---

## 3. Matriz de Trazabilidad Completa: Escenarios, Medidas, Código y Evidencias Automatizadas

| Escenario | ID Medida | Característica / Subcaracterística | Fórmula ($X = A/B$) | Umbral Aceptable | Meta Deseable | Resultado Actual (Corte 2) | Componente / Prueba que lo Verifica (Evidencia) |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **EC-02, EC-06** | **M-01** | Adecuación Funcional / Corrección Funcional | Casos de normalización y vigencia aprobados / Total ejecutados | $1.00$ | $1.00$ | **$1.00$ (100%)** | `core_domain/unit_normalizer.py`, `core_domain/validity_policy.py` — **E1:** `tests/unit/test_normalization_and_validity.py` |
| **EC-06** | **M-02** | Adecuación Funcional / Neutralidad de comparación | Comparaciones con orden estricto al criterio declarado y pautas distinguidas / Total evaluado | $1.00$ | $1.00$ | **$1.00$ (100%)** | `core_domain/neutral_comparator.py` — **E1:** `tests/unit/test_comparator_and_anomaly.py` y `tests/integration/test_api_flows.py` |
| **EC-01** | **M-03** | Capacidad de Interacción / Operabilidad | Registros completados en $\le 15\text{ s}$ / Intentos totales en prueba de usuarios | $\ge 0.80$ | $\ge 0.90$ | **Soportado por API ($< 20\text{ ms}$)** | `POST /api/v1/price-reports/` (payload mínimo de 3 campos) — **E2:** Protocolo de prueba con usuarios |
| **EC-01, EC-06** | **M-04** | Capacidad de Interacción / Inclusividad | Criterios WCAG 2.2 AA cumplidos / Criterios aplicables evaluados | $\ge 0.90$ | $1.00$ | **Soportado por mensajes autodescriptivos** | Etiquetas textuales explícitas (`warning_messages`, `user_feedback_message`) sin depender solo de color — **E6** |
| **EC-03** | **M-05** | Seguridad / Integridad y Credibilidad (25012) | Reportes anómalos detectados como no confiables / Total inyectados en set de prueba | $\ge 0.80$ | $\ge 0.90$ | **$1.00$ (10/10 = 100%)** | `core_domain/anomaly_detector.py` — **E4:** `TestAnomalyDetectorTDD.test_m05_anomalous_dataset_detection_rate_exceeds_threshold` |
| **EC-03** | **M-06** | Seguridad / Confidencialidad (Ley 1581) | Endpoints públicos sin GPS ni identidad del reportante / Total endpoints auditados | $1.00$ | $1.00$ | **$1.00$ (9/9 = 100%)** | `pricing/serializers.py` — **E4:** `tests/security/test_privacy_m06.py` |
| **EC-04** | **M-07** | Eficiencia de Desempeño / Comportamiento Temporal | Percentil 95 ($P_{95}$) del tiempo de respuesta de consulta bajo 500 VUs concurrentes | $\le 2000\text{ ms}$ | $\le 1000\text{ ms}$ | **Caché sub-10ms lista** | `ComparePricesQueryService` + Caché versionada — **E3:** `tests/load/k6_ec04_500_users.js` |
| **EC-05** | **M-08** | Mantenibilidad / Modificabilidad (Esfuerzo) | Esfuerzo real en horas-persona para integrar módulo comercial / Esfuerzo estimado | $\le 1.25$ | $\le 1.10$ | **Listo para Corte 3** | Contrato `PriceSourcePort` en `core_domain/ports.py` — **E5** |
| **EC-05** | **M-09** | Mantenibilidad / Estabilidad estructural del núcleo | Componentes preexistentes del núcleo modificados / Total componentes del núcleo | $\le 0.30$ | $\le 0.15$ | **$0.00$ demostrable en test** | Validado con `MockCommercialModuleAdapter` en `tests/integration/test_api_flows.py` — **E5** |
| **EC-05** | **M-010** | Mantenibilidad / Testeabilidad | Líneas del módulo de reglas de negocio ejecutadas por pruebas TDD / Líneas totales | $\ge 0.85$ | $\ge 0.95$ | **$0.99$ (99% cobertura)** | `pytest --cov=core_domain` (189/190 sentencias cubiertas) — **E1, E5** |
| **EC-01** | **M-11** | Capacidad de Interacción / Satisfacción | Puntaje medio en escala System Usability Scale (SUS) tras prueba del Corte 2 | $\ge 68$ | $\ge 80$ | **Instrumento listo** | Respaldado por respuestas autodescriptivas inmediatas de la API — **E2** |
