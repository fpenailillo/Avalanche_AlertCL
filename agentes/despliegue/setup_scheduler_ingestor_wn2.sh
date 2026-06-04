#!/usr/bin/env bash
# Configura Cloud Scheduler para disparar ingestor-wn2 diariamente a las 05:00 UTC
# (antes del orquestador de avalanchas que corre ~07:00 UTC).
#
# Ejecutar UNA VEZ tras el primer deploy de ingestor-wn2:
#   bash agentes/despliegue/setup_scheduler_ingestor_wn2.sh

set -euo pipefail

PROJECT_ID="climas-chileno"
REGION="us-central1"
JOB_NAME="ingestor-wn2"
SCHEDULER_NAME="trigger-ingestor-wn2-diario"
SCHEDULE="0 5 * * *"   # 05:00 UTC = 02:00 Santiago (CLT)
TIMEZONE="UTC"
SA="funciones-clima-sa@${PROJECT_ID}.iam.gserviceaccount.com"

echo "Creando/actualizando Cloud Scheduler: ${SCHEDULER_NAME}"

# Verificar si ya existe
if gcloud scheduler jobs describe "${SCHEDULER_NAME}" \
     --location="${REGION}" --project="${PROJECT_ID}" > /dev/null 2>&1; then
  echo "Ya existe, actualizando..."
  gcloud scheduler jobs update http "${SCHEDULER_NAME}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}" \
    --schedule="${SCHEDULE}" \
    --time-zone="${TIMEZONE}" \
    --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run" \
    --message-body='{}' \
    --oauth-service-account-email="${SA}"
else
  echo "Creando nuevo scheduler..."
  gcloud scheduler jobs create http "${SCHEDULER_NAME}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}" \
    --schedule="${SCHEDULE}" \
    --time-zone="${TIMEZONE}" \
    --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run" \
    --message-body='{}' \
    --oauth-service-account-email="${SA}"
fi

echo ""
echo "Scheduler configurado: ${SCHEDULER_NAME}"
echo "  Cron    : ${SCHEDULE} (${TIMEZONE})"
echo "  Job     : ${JOB_NAME} en ${REGION}"
echo ""
echo "Para disparar manualmente:"
echo "  gcloud scheduler jobs run ${SCHEDULER_NAME} --location=${REGION} --project=${PROJECT_ID}"
