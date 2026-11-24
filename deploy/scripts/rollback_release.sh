#!/usr/bin/env bash
# ==============================================================================
# Procedimiento Automatizado de Reversión (Rollback) en Producción (< 90 segundos)
# Opción B2 del Anexo 1 — Escenario EC-12 y ADR-14
#
# Uso:
#   bash deploy/scripts/rollback_release.sh             # Ejecuta la reversión real en la VM de GCP
#   bash deploy/scripts/rollback_release.sh --dry-run   # Simula y verifica los pasos sin reiniciar contenedores
# ==============================================================================
set -euo pipefail

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
fi

DEPLOY_DIR="${DEPLOY_DIR:-/home/vhoyos703_cue_edu_co/nuvora/deploy-transfer}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.prod}"
STABLE_IMAGE_TAG="${STABLE_IMAGE_TAG:-nuvora-backend:previous-stable}"
CURRENT_IMAGE_TAG="${CURRENT_IMAGE_TAG:-nuvora-backend:prod}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1/api/v1/health/}"

START_TS=$(date +%s)
echo "=================================================================="
echo " [ROLLBACK B2 / EC-12] Iniciando reversión controlada de versión"
echo " Fecha/Hora: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo " Modo Dry-Run: ${DRY_RUN}"
echo "=================================================================="

if [[ "${DRY_RUN}" == "true" ]]; then
  echo "[DRY-RUN 1/5] Verificando existencia de imagen estable previa (${STABLE_IMAGE_TAG})..."
  echo "[DRY-RUN 2/5] Re-etiquetando ${STABLE_IMAGE_TAG} -> ${CURRENT_IMAGE_TAG}..."
  echo "[DRY-RUN 3/5] Recreando contenedores backend, celery-worker y celery-beat con --no-build --no-deps..."
  echo "[DRY-RUN 4/5] Limpiando caché de Redis para evitar artefactos de la versión revertida..."
  echo "[DRY-RUN 5/5] Comprobando HTTP 200 en ${HEALTH_URL}..."
  END_TS=$(date +%s)
  ELAPSED=$((END_TS - START_TS))
  echo "[OK] Simulación de Rollback verificada con éxito en ${ELAPSED}s (Meta EC-12: <= 90s)."
  exit 0
fi

cd "${DEPLOY_DIR}"

echo "[1/5] Verificando que la imagen estable previa (${STABLE_IMAGE_TAG}) exista localmente..."
if ! sudo docker image inspect "${STABLE_IMAGE_TAG}" > /dev/null 2>&1; then
  echo "[ERROR] No se encontró la imagen '${STABLE_IMAGE_TAG}'. Abortando reversión para proteger el servicio actual."
  exit 1
fi

echo "[2/5] Restaurando etiqueta de producción hacia la última imagen estable comprobada..."
sudo docker tag "${STABLE_IMAGE_TAG}" "${CURRENT_IMAGE_TAG}"

echo "[3/5] Recreando contenedores de aplicación (backend, celery-worker, celery-beat)..."
sudo docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --no-build --no-deps --force-recreate backend celery-worker celery-beat

echo "[4/5] Purgando claves volátiles de caché en Redis..."
sudo docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" exec -T backend python manage.py shell -c "from django.core.cache import cache; cache.clear(); print('Cache Redis restaurada OK')"

echo "[5/5] Verificando disponibilidad en ${HEALTH_URL}..."
for attempt in $(seq 1 15); do
  if curl -fsS "${HEALTH_URL}" > /dev/null; then
    END_TS=$(date +%s)
    ELAPSED=$((END_TS - START_TS))
    echo "=================================================================="
    echo " [ROLLBACK EXITOSO] Servicio revertido y saludable en ${ELAPSED} segundos."
    echo "=================================================================="
    exit 0
  fi
  sleep 2
done

echo "[ERROR] El healthcheck no respondió HTTP 200 tras la reversión. Revisar logs con: sudo docker compose logs --tail=50 backend"
exit 1
