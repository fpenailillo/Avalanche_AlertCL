#!/usr/bin/env bash
# Publicación desacoplada del boletín activo del frontend.
#
# El orquestador (orquestador-avalanchas, 08:00 UTC) publica boletin_activo.json
# al final del pipeline, pero cuando la corrida excede su task-timeout de 3600s
# muere ANTES de ese paso y el frontend queda congelado — aunque los boletines
# individuales ya están en clima.boletines_riesgo (se guardan zona por zona).
#
# Este job desacopla la publicación: exportar_boletin_activo.py reconstruye
# boletin_activo.json desde BigQuery y lo republica, sin depender de que el
# pipeline complete. Corre a las 10:30 UTC, ~30 min después de que el
# orquestador muere (~10:04 UTC), cuando todas las zonas ya están en BQ.
#
# Ejecutar UNA VEZ para crear/actualizar el job y su scheduler:
#   bash agentes/despliegue/setup_scheduler_boletin.sh

set -euo pipefail

PROJECT_ID="climas-chileno"
REGION="us-central1"
JOB_NAME="exportar-boletin-activo"
SCHEDULER_NAME="publicar-boletin-activo"
SCHEDULE="30 10 * * *"   # 10:30 UTC = 06:30 Santiago (CLT); ~30 min post-orquestador
TIMEZONE="UTC"
IMAGE="gcr.io/${PROJECT_ID}/snow-alert-agentes:latest"
SA="funciones-clima-sa@${PROJECT_ID}.iam.gserviceaccount.com"

echo "Creando/actualizando Cloud Run Job: ${JOB_NAME}"
if gcloud run jobs describe "${JOB_NAME}" \
     --region="${REGION}" --project="${PROJECT_ID}" > /dev/null 2>&1; then
  echo "Ya existe, actualizando..."
  ACCION="update"
else
  echo "Creando nuevo job..."
  ACCION="create"
fi

gcloud run jobs "${ACCION}" "${JOB_NAME}" \
  --image="${IMAGE}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --command=python \
  --args=agentes/scripts/exportar_boletin_activo.py \
  --service-account="${SA}" \
  --task-timeout=300 \
  --max-retries=1 \
  --memory=1Gi --cpu=1 \
  --set-env-vars=ID_PROYECTO="${PROJECT_ID}",DATASET_ID=clima,REGION="${REGION}"

echo ""
echo "Creando/actualizando Cloud Scheduler: ${SCHEDULER_NAME}"
URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run"

if gcloud scheduler jobs describe "${SCHEDULER_NAME}" \
     --location="${REGION}" --project="${PROJECT_ID}" > /dev/null 2>&1; then
  echo "Ya existe, actualizando..."
  gcloud scheduler jobs update http "${SCHEDULER_NAME}" \
    --location="${REGION}" --project="${PROJECT_ID}" \
    --schedule="${SCHEDULE}" --time-zone="${TIMEZONE}" \
    --uri="${URI}" --http-method=POST --message-body='{}' \
    --oauth-service-account-email="${SA}" --attempt-deadline=180s
else
  echo "Creando nuevo scheduler..."
  gcloud scheduler jobs create http "${SCHEDULER_NAME}" \
    --location="${REGION}" --project="${PROJECT_ID}" \
    --schedule="${SCHEDULE}" --time-zone="${TIMEZONE}" \
    --uri="${URI}" --http-method=POST --message-body='{}' \
    --oauth-service-account-email="${SA}" --attempt-deadline=180s
fi

echo ""
echo "Publicación desacoplada configurada:"
echo "  Job       : ${JOB_NAME} (${REGION})"
echo "  Scheduler : ${SCHEDULER_NAME} — ${SCHEDULE} (${TIMEZONE})"
echo ""
echo "Para disparar manualmente:"
echo "  gcloud run jobs execute ${JOB_NAME} --region=${REGION} --project=${PROJECT_ID}"
