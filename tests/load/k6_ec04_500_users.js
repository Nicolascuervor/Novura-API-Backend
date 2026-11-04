/**
 * Prueba de Carga Automatizada con k6 (Evidencia E3 - Escenario EC-04 y Medida M-07).
 * Escenario EC-04: En un fin de semana de quincena, 500 usuarios concurrentes consultan
 * comparaciones de precios en Armenia/Quindío.
 * Umbral aceptable M-07: P95 <= 2000 ms (2.0 s). Meta deseable: P95 <= 1000 ms (1.0 s).
 *
 * Ejecución:
 *   k6 run tests/load/k6_ec04_500_users.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export const options = {
  stages: [
    { duration: '15s', target: 100 }, // Calentamiento progresivo
    { duration: '30s', target: 500 }, // Pico de quincena: 500 usuarios concurrentes (EC-04)
    { duration: '15s', target: 0 },   // Enfriamiento
  ],
  thresholds: {
    // M-07: Percentil 95 <= 2000 ms (aceptable) y monitoreo de meta deseable <= 1000 ms
    http_req_duration: ['p(95)<=2000', 'p(90)<=1000'],
    // Fiabilidad (Disponibilidad en los picos): menos del 1% de fallos
    http_req_failed: ['rate<0.01'],
  },
};

export default function () {
  // Lectura intensiva: comparación neutral por unidad de medida (Arroz, Leche, Huevos)
  const productId = [1, 2, 3][Math.floor(Math.random() * 3)];
  const res = http.get(
    `${BASE_URL}/api/v1/products/${productId}/compare/?sort_by=UNIT_PRICE_ASC&municipality=Armenia`
  );

  check(res, {
    'status is 200 OK': (r) => r.status === 200,
    'contains ranked_results': (r) => r.body && r.body.includes('ranked_results'),
    'contains neutrality_statement (EC-06)': (r) => r.body && r.body.includes('neutrality_statement'),
  });

  sleep(0.3);
}
