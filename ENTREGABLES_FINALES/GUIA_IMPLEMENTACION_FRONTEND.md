# Guía Técnica de Implementación para el Frontend — Pricecol (Nuvora)
## Integración del Panel de Moderación ("Comercios"), Flujo de Establecimientos e Historial de Precios de 90 Días (Corte 3)

Esta guía explica paso a paso al equipo de **Frontend** cómo conectar la interfaz con el **Backend API REST (`/api/v1/`)**, detallando los endpoints exactos, parámetros, estructuras JSON y las reglas de negocio y seguridad que debe tener en cuenta, especialmente para la pestaña **"Comercios"** del Panel de Moderación (vista en la captura) y la nueva gráfica de **Historial y Tendencia de 90 días (`A2`)**.

---

## 1. Pestaña "Comercios" en el Panel del Moderador

Como se observa en la interfaz del Moderador (*"Verifica la titularidad de los establecimientos nuevos y las solicitudes de corrección enviadas por los comercios"*), esta vista se compone de **dos bandejas** y un **contador general**.

### 1.1 Contadores rápidos para los badges de la pestaña (`0 pendientes`)
Para mostrar los contadores de elementos pendientes en las pestañas del Moderador sin descargar todas las listas:
* **Endpoint:** `GET /api/v1/moderation/dashboard-summary/`
* **Headers:** `Authorization: Bearer <access_token_moderador>`
* **Campos que debes leer del JSON de respuesta:**
  * **Reportes en revisión:** `data.pricing_and_moderation.flagged_pending_review`
  * **Establecimientos / Comercios nuevos pendientes:** `data.accounts.pending_verification_merchants`
  * **Solicitudes de corrección pendientes:** `data.pricing_and_moderation.pending_correction_requests`

---

### 1.2 Bandeja 1: "Establecimientos nuevos" (Verificación de titularidad de Comercios)

En nuestra arquitectura, cuando un comercio se registra (`role: "MERCHANT"`) o crea un establecimiento nuevo, su perfil inicia con estado de verificación pendiente o no verificado (`verification_status: "PENDING"` o `"UNVERIFIED"`). Hasta que el Moderador verifique su titularidad, cualquier precio que publique ese comercio se muestra como reporte comunitario (`COMMUNITY_OCCASIONAL`) para evitar suplantaciones (ej. alguien que se registre diciendo ser "Tienda D1" sin serlo).

#### A. Cómo listar los comercios/establecimientos pendientes de revisión
* **Endpoint:**  
  `GET /api/v1/moderation/accounts/?role=MERCHANT&verification_status=PENDING`  
  *(Tip para el Front: Si también quieres listar los que se registraron sin enviar solicitud formal aún, puedes consultar `?role=MERCHANT` y filtrar en el Front aquellos donde `is_verified === false` y `verification_status !== "REJECTED"`).*
* **Headers:** `Authorization: Bearer <access_token_moderador>`
* **Respuesta JSON de ejemplo:**
  ```json
  [
    {
      "id": 418293104,
      "user_id": 891023412,
      "username": "autoservicio_la_14",
      "email": "contacto@autoserviciola14.co",
      "last_login": "2026-11-26T14:20:00Z",
      "role": "MERCHANT",
      "managed_establishment": 12,
      "verified_reports_count": 0,
      "rejected_reports_count": 0,
      "is_suspended": false,
      "verification_status": "PENDING",
      "is_verified": false,
      "business_legal_name": "Autoservicio La 14 Armenia S.A.S.",
      "business_tax_id": "901.452.331-8",
      "verified_at": null,
      "created_at": "2026-11-25T18:10:00Z"
    }
  ]
  ```
* **Cómo obtener los datos del establecimiento asociado para mostrarlos en la tarjeta:**
  * Si `managed_establishment` tiene un ID (ej. `12`), o si quieres ver todos los establecimientos creados por ese comerciante (`user_id`), haz:
    * `GET /api/v1/establishments/?owner=891023412` (usando el `user_id` del comercio).

#### B. Cómo Aprobar (Verificar titularidad) o Rechazar desde el botón del Moderador
* **Endpoint:** `PATCH /api/v1/moderation/accounts/{id}/`
  * ⚠️ **¡CUIDADO (Error común en el Front)!** En la URL debes enviar el campo **`id`** del perfil devuelto en la lista (`418293104`), **NO** el `user_id` (`891023412`) ni el `managed_establishment` (`12`).
* **Headers:**
  * `Authorization: Bearer <access_token_moderador>`
  * `Content-Type: application/json`
* **Body JSON para APROBAR / VERIFICAR la titularidad:**
  ```json
  {
    "verification_status": "VERIFIED"
  }
  ```
* **Body JSON para RECHAZAR la titularidad:**
  ```json
  {
    "verification_status": "REJECTED"
  }
  ```
* **Qué ocurre en el Backend al enviar `"VERIFIED"`:**
  1. `is_verified` pasa automáticamente a `true` y se guarda la fecha `verified_at`.
  2. Se registra automáticamente en la pestaña **"Bitácora de auditoría"** el evento `MERCHANT_VERIFICATION_CHANGED`.
  3. A partir de ese instante, los precios publicados por ese comercio en sus establecimientos reciben el sello oficial **`OFFICIAL_MERCHANT`**.

---

### 1.3 Bandeja 2: "Solicitudes de corrección" (Enviadas por los Comercios)

Esta bandeja cumple la **Consideración Ética 3 de la Guía (Equidad entre comercios)**: todo comercio tiene derecho a solicitar la corrección de información errónea sobre su negocio (nombre, barrio o dirección), y el Moderador la revisa y aprueba con un clic.

#### A. Cómo el Moderador lista las solicitudes de corrección pendientes
* **Endpoint:** `GET /api/v1/merchant/correction-requests/`
* **Headers:** `Authorization: Bearer <access_token_moderador>`
* **Respuesta JSON de ejemplo:**
  ```json
  [
    {
      "id": 5,
      "establishment": 4,
      "establishment_current_name": "Minimercado El Cafetal",
      "proposed_name": "Supermercado El Cafetal del Quindío",
      "proposed_neighborhood": "Laureles",
      "proposed_address": "Calle 21 Norte # 14-35",
      "justification": "Nos trasladamos dos locales más arriba en el mismo barrio y actualizamos razón comercial.",
      "status": "PENDING",
      "moderator_notes": "",
      "created_at": "2026-11-26T10:15:00Z",
      "resolved_at": null
    }
  ]
  ```
* **Qué debe tener en cuenta el Front:**
  * El endpoint devuelve el historial completo de solicitudes. Para la bandeja **"Solicitudes de corrección (pendientes)"**, filtra en el Frontend aquellas donde:
    ```javascript
    const pendingCorrections = data.filter(item => item.status === "PENDING");
    ```

#### B. Cómo el Moderador aprueba y aplica una solicitud de corrección
Cuando el Moderador hace clic en **"Aprobar y aplicar cambios"**:
* **Endpoint:** `POST /api/v1/moderation/correction-requests/{correction_id}/approve/`
  *(Donde `{correction_id}` es el `id` de la solicitud, por ejemplo `5`).*
* **Headers:**
  * `Authorization: Bearer <access_token_moderador>`
  * `Content-Type: application/json`
* **Body JSON (opcionalmente puede incluir una nota del moderador):**
  ```json
  {
    "moderator_notes": "Datos verificados y aplicados al directorio oficial."
  }
  ```
* **Qué hace el Backend automáticamente en una sola transacción:**
  1. Actualiza el nombre (`name`), barrio (`neighborhood`) y dirección (`address`) del establecimiento real en el catálogo con los valores propuestos (`proposed_name`, `proposed_neighborhood`, `proposed_address`).
  2. Cambia el estado de la solicitud a `"APPROVED"` y registra `resolved_at`.
  3. Invalida la caché del catálogo para que todos los usuarios vean los datos corregidos de inmediato.
  4. Escribe el evento `CORRECTION_REQUEST_RESOLVED` en la **Bitácora de auditoría**.

#### C. Cómo un Comercio (`MERCHANT`) envía una solicitud de corrección desde su portal
Para que aparezcan solicitudes en la bandeja del moderador, desde la vista de perfil del **Comercio (`MERCHANT`)** debes invocar:
* **Endpoint:** `POST /api/v1/merchant/correction-requests/`
* **Headers:** `Authorization: Bearer <access_token_comercio>`
* **Body JSON:**
  ```json
  {
    "establishment": 4,
    "proposed_name": "Supermercado El Cafetal del Quindío",
    "proposed_neighborhood": "Laureles",
    "proposed_address": "Calle 21 Norte # 14-35",
    "justification": "Actualización de dirección y nombre comercial."
  }
  ```
* ⚠️ **Regla de seguridad Anti-IDOR que el Front debe tener en cuenta:**
  * Un usuario con rol `MERCHANT` **solo puede enviar solicitudes para un establecimiento propio** (donde el establecimiento esté en `owned_establishment_ids` o sea su `managed_establishment` en `GET /api/v1/auth/me/`). Si envía el ID de otro comercio, el backend responderá `403 Forbidden`.

---

## 2. Implementación de la Gráfica de Historial y Tendencia de Precios de 90 Días (Ampliación Corte 3 — Opción A2 / `EC-08`)

Para la entrega final del Corte 3 implementamos el motor de **Historial y Tendencia de Precios de hasta 90 días con comparación multi-establecimiento en la misma gráfica**.

### 2.1 Endpoint y parámetros de consulta
* **Endpoint:** `GET /api/v1/products/{product_id}/price-history/`
  *(Público: no requiere token JWT para que cualquier consumidor pueda ver la gráfica).*
* **Query Parameters soportados:**
  * `days` *(opcional, entero de `1` a `90`, por defecto `90`)*: Ventana de días hacia atrás (puedes poner un selector en la UI de `30 días`, `60 días`, `90 días`).
  * `establishment_id` *(opcional, entero)*: Filtra el historial para una sola tienda.
  * `establishment_ids` *(opcional, string separado por comas, ej. `1,2,3`)*: **Permite comparar 2 o más tiendas en la misma gráfica** (extensión opcional de `A2` que implementamos completa).
  * `include_low_confidence` *(opcional, booleano `true` | `false`, por defecto `true`)*: Permite incluir u ocultar con un *toggle/switch* en la UI los puntos que tuvieron variación atípica moderada (`LOW_CONFIDENCE`).

### 2.2 Ejemplo de llamada y estructura JSON de respuesta
**Llamada:**  
`GET /api/v1/products/1/price-history/?days=90&establishment_ids=1,2`

**Respuesta (`200 OK`):**
```json
{
  "product_id": 1,
  "product_name": "Arroz Blanco",
  "window_days": 90,
  "cutoff_start_at": "2026-08-28T15:00:00Z",
  "evaluated_at": "2026-11-26T15:00:00Z",
  "privacy_statement": "Serie histórica anonimizada conforme a la Ley 1581 de 2012 (M-06 = 1.00): ningún punto permite identificar qué reportante registró cada precio.",
  "total_points": 6,
  "excluded_out_of_window_count": 0,
  "excluded_anomalous_count": 1,
  "establishment_series": [
    {
      "establishment_id": 1,
      "establishment_name": "Tienda D1 Armenia Centro",
      "reference_unit_label": "100g",
      "points_count": 3,
      "first_normalized_price": "440.00",
      "latest_normalized_price": "410.00",
      "min_normalized_price": "410.00",
      "max_normalized_price": "450.00",
      "avg_normalized_price": "433.33",
      "variation_amount": "-30.00",
      "variation_percentage": "-6.82",
      "trend_direction": "DOWN",
      "points": [
        {
          "report_id": 101,
          "establishment_id": 1,
          "establishment_name": "Tienda D1 Armenia Centro",
          "presentation_id": 1,
          "presentation_name": "Bolsa 500g",
          "reported_at": "2026-10-01T10:00:00Z",
          "raw_price": "2200.00",
          "normalized_ref_price": "440.00",
          "reference_unit_label": "100g",
          "source_type": "OFFICIAL_MERCHANT",
          "reliability_status": "VERIFIED",
          "validity_status": "SUPERSEDED",
          "confidence_score": "0.98",
          "is_promotional": false,
          "promotion_description": null,
          "requires_warning": false
        },
        {
          "report_id": 115,
          "establishment_id": 1,
          "establishment_name": "Tienda D1 Armenia Centro",
          "presentation_id": 1,
          "presentation_name": "Bolsa 500g",
          "reported_at": "2026-11-20T14:30:00Z",
          "raw_price": "2050.00",
          "normalized_ref_price": "410.00",
          "reference_unit_label": "100g",
          "source_type": "COMMUNITY_FREQUENT",
          "reliability_status": "VERIFIED",
          "validity_status": "VALID",
          "confidence_score": "0.92",
          "is_promotional": true,
          "promotion_description": "Descuento de quincena",
          "requires_warning": false
        }
      ]
    }
  ]
}
```

### 2.3 Qué cosas debe tener en cuenta el Frontend al pintar esta gráfica
1. **Usar `normalized_ref_price` en el eje Y de la gráfica:**
   * Para que la gráfica compare de forma justa presentaciones distintas (ej. bolsa de 450g vs. bolsa de 500g), grafica `Number(point.normalized_ref_price)` en el eje Y (indicando en el eje `Precio por ${series.reference_unit_label}`, ej. `COP por 100g`) y muestra el `raw_price` y `presentation_name` en el *tooltip* al pasar el mouse.
2. **Múltiples líneas en un mismo gráfico (`establishment_series`):**
   * Cada objeto dentro del arreglo `establishment_series` es **una línea de un color distinto** en el gráfico (Chart.js / Recharts / ApexCharts), identificada por `series.establishment_name`.
3. **Tarjetas de resumen de tendencia (`trend_direction` y `variation_percentage`):**
   * `trend_direction` viene calculado desde el backend con tres valores posibles:
     * `"DOWN"` (Bajó de precio &rarr; mostrar flecha hacia abajo en **verde**, beneficioso para el consumidor).
     * `"UP"` (Subió de precio &rarr; mostrar flecha hacia arriba en **rojo/ámbar**).
     * `"STABLE"` (Sin cambio &rarr; mostrar insignia **gris/azul** `"Estable 0.00%"`).
4. **Distinción visual del origen y confiabilidad de cada punto (`EC-08`):**
   * En el *tooltip* de cada punto de la gráfica muestra:
     * **Fuente (`source_type`):**
       * `"OFFICIAL_MERCHANT"` &rarr; *"Precio oficial del comercio"*
       * `"COMMUNITY_FREQUENT"` / `"COMMUNITY_OCCASIONAL"` &rarr; *"Reporte ciudadano"*
       * `"PUBLIC_REFERENCE"` &rarr; *"Referencia SIPSA-DANE"*
     * **Advertencia de baja confianza (`requires_warning === true`):** Si un punto trae `requires_warning: true` (`reliability_status: "LOW_CONFIDENCE"`), píntalo con un borde punteado o ícono de alerta amarilla indicando *"Variación atípica pendiente de confirmación"*.
     * **Transparencia antifraude:** Muestra debajo de la gráfica una nota pequeña con `excluded_anomalous_count`: *"Se excluyeron automáticamente {excluded_anomalous_count} reportes anómalos para proteger la veracidad de la tendencia"*.

---

## 3. Cinco Reglas Transversales que el Frontend Siempre Debe Tener en Cuenta

1. **Login minimalista + Consulta de perfil (`/api/v1/auth/login/` y `/api/v1/auth/me/`):**
   * Por seguridad (Principio de Minimización de Datos OWASP / Ley 1581), `POST /api/v1/auth/login/` recibe `{"email": "...", "password": "..."}` y devuelve **únicamente** `{"access": "...", "refresh": "..."}`.
   * Inmediatamente después del login, el Front debe llamar a `GET /api/v1/auth/me/` con el header `Authorization: Bearer <access>` para conocer el `role` (`CONSUMER`, `REPORTER`, `MERCHANT`, `MODERATOR`), `is_verified`, `managed_establishment` y `owned_establishment_ids`.
2. **Subida de imágenes (`multipart/form-data` y validación binaria):**
   * Todos los endpoints que reciben fotos (`evidence_image` en `/api/v1/price-reports/`, `profile_image` en `/api/v1/auth/me/avatar/`, `logo_image` en `/api/v1/establishments/{id}/image/`, `product_image` en `/api/v1/products/{id}/`) validan los **magic bytes reales** del archivo.
   * Solo se aceptan imágenes reales **`JPEG`, `PNG` o `WEBP` de máximo 5 MB**. Cuando envíes `FormData` desde `fetch` o `axios`, **no fuerces manualmente el header `Content-Type: multipart/form-data`** para que el navegador agregue automáticamente el `boundary`.
3. **Neutralidad obligatoria en Comparación y Promociones (`GET /api/v1/products/{id}/compare/`):**
   * La respuesta trae dos arreglos separados:
     * `ranked_results`: Lista principal ordenada estrictamente por `sort_by` (`UNIT_PRICE_ASC`, `RAW_PRICE_ASC`, `FRESHNESS_DESC`).
     * `promotional_highlights_separated`: Lista de promociones vigentes.
   * **Regla ética y de evaluación (`EC-06`):** En el Frontend **siempre** debe mostrarse una etiqueta visible (`"Promoción"` / `"Contenido promocional"`) cuando `item.is_promotional === true`, y nunca debe reordenarse la tabla principal para poner promociones de primeras si su precio por unidad base no es el más bajo.
4. **Filtros de Establecimientos por Métodos de Pago y Propiedad (`GET /api/v1/establishments/`):**
   * Para el panel de un Comercio (`MERCHANT`), usa `GET /api/v1/establishments/?mine=true` para obtener únicamente las tiendas que le pertenecen.
   * Para filtrar tiendas por medios de pago (ej. Nequi, Bre-B, Efectivo), usa `GET /api/v1/establishments/?payment_method=nequi,bre_b` y consulta el catálogo de íconos disponibles en `GET /api/v1/payment-methods/`.
5. **Manejo de errores estándar del Backend:**
   * Los errores de validación o negocio devuelven JSON con la llave `detail` (ej. `{"detail": "Mensaje claro para mostrar en toast/alerta"}`) o errores por campo (`{"raw_price": ["..."]}`). Muestra siempre `error.response?.data?.detail` cuando esté presente.
