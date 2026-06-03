#!/usr/bin/env bash
#
# One-shot deploy of Mind Video to Google Cloud Run.
#
# Prereqs (once):
#   gcloud auth login
#   gcloud config set project <YOUR_PROJECT_ID>
#   ./deploy/setup.sh        # enables APIs, creates the repo + secrets
#
# Usage:
#   ./deploy/deploy.sh
#
# Override defaults with env vars:
#   GCP_REGION=europe-west1 SERVICE_NAME=mind-video ./deploy/deploy.sh
set -euo pipefail

PROJECT_ID="${GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${GCP_REGION:-me-west1}"          # me-west1 = Tel Aviv
SERVICE="${SERVICE_NAME:-mind-video}"
REPO="${AR_REPO:-mind-video}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "ERROR: no GCP project. Run: gcloud config set project <ID>" >&2
  exit 1
fi

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE}"

echo "==> Project : ${PROJECT_ID}"
echo "==> Region  : ${REGION}"
echo "==> Image   : ${IMAGE}:latest"

# Build + push via Cloud Build (no local Docker needed).
echo "==> Building image with Cloud Build..."
gcloud builds submit --tag "${IMAGE}:latest" .

# Deploy. See cloudbuild.yaml for why these flags matter.
echo "==> Deploying to Cloud Run..."
gcloud run deploy "${SERVICE}" \
  --image="${IMAGE}:latest" \
  --region="${REGION}" \
  --platform=managed \
  --allow-unauthenticated \
  --port=8080 \
  --cpu=2 \
  --memory=2Gi \
  --timeout=3600 \
  --no-cpu-throttling \
  --min-instances=1 \
  --max-instances=1 \
  --set-secrets=FAL_KEY=FAL_KEY:latest,ELEVENLABS_API_KEY=ELEVENLABS_API_KEY:latest,GOOGLE_API_KEY=GOOGLE_API_KEY:latest

echo "==> Done. URL:"
gcloud run services describe "${SERVICE}" --region="${REGION}" \
  --format='value(status.url)'
