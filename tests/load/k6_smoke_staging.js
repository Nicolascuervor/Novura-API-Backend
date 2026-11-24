/**
 * Prueba de Humo Automatizada en Staging (Opción B2 — Escenario EC-12)
 * Herramienta: Grafana k6
 *
 * Se ejecuta automáticamente tras reconstruir desde cero el entorno de Staging en el pipeline CI/CD.
 * Verifica:
 * 1. Disponibilidad del servicio, caché Redis y Celery (`GET /api/v1/health/`).
 * 2. Comparación neutral normalizada de precios (`GET /api/v1/products/1/compare/` — EC-04 / EC-06).
 * 3. Historial y tendencia de precios de 90 días (`GET /api/v1/products/1/price-history/?days=90` — Opción A2 / EC-08).
 * 4. Privacidad por diseño (M-06 = 1.00): ausencia de `reporter_hash` en las respuestas públicas.
 */

import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 5,
  duration: "10s",
  thresholds: {
    http_req_duration: ["p(95)<1500"], // P95 <= 1.5s en prueba de humo de Staging
    http_req_failed: ["rate<0.01"],    // 0% de fallos tolerados para promover versión
    checks: ["rate==1.0"],             // 100% de los checks funcionales deben pasar
  },
};

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";

export default function () {
  // 1. Verificar Healthcheck del backend
  const healthRes = http.get(`${BASE_URL}/api/v1/health/`);
  check(healthRes, {
    "Healthcheck responde HTTP 200": (r) => r.status === 200,
    "Servicio reporta status ok": (r) => r.body && r.body.includes('"status": "ok"'),
  });

  // Obtener dinámicamente el primer producto activo del catálogo en Staging
  const productsRes = http.get(`${BASE_URL}/api/v1/products/`);
  let productId = __ENV.PRODUCT_ID || "1";
  if (productsRes.status === 200) {
    try {
      const parsed = JSON.parse(productsRes.body);
      if (parsed.results && parsed.results.length > 0) {
        productId = String(parsed.results[0].id);
      }
    } catch (_) {
      productId = "1";
    }
  }

  // 2. Verificar Comparador Neutral (EC-04 / EC-06)
  const cmpRes = http.get(
    `${BASE_URL}/api/v1/products/${productId}/compare/?sort_by=UNIT_PRICE_ASC`
  );
  check(cmpRes, {
    "Comparador responde HTTP 200": (r) => r.status === 200,
    "Incluye declaración de neutralidad": (r) =>
      r.body && r.body.includes("neutrality_statement"),
    "Sin exposición de reporter_hash (M-06)": (r) =>
      r.body && !r.body.includes("reporter_hash"),
  });

  // 3. Verificar Historial y Tendencia de 90 Días (Ampliación A2 / EC-08)
  const histRes = http.get(
    `${BASE_URL}/api/v1/products/${productId}/price-history/?days=90`
  );
  check(histRes, {
    "Historial de 90 días responde HTTP 200": (r) => r.status === 200,
    "Incluye series por establecimiento y declaración Ley 1581": (r) =>
      r.body &&
      r.body.includes("establishment_series") &&
      r.body.includes("privacy_statement"),
    "Historial sin exposición de reporter_hash (M-06)": (r) =>
      r.body && !r.body.includes("reporter_hash"),
  });

  sleep(0.3);
}
