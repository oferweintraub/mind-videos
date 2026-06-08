#!/usr/bin/env bash
#
# One-shot deploy of Mind Video to Google Cloud Run.
#
# Builds the image LOCALLY with Docker and pushes it straight to Artifact
# Registry, then deploys. This deliberately avoids `gcloud builds submit`
# (Cloud Build), which needs access to the gs://<project>_cloudbuild staging
# bucket — blocked here by org policy / missing serviceusage.services.use.
#
# Prereqs (once):
#   gcloud auth login
#   gcloud config set project <YOUR_PROJECT_ID>
#   ./deploy/setup.sh        # enables APIs, creates the repo + secrets
#   Docker Desktop running.
#
# Usage:
#   ./deploy/deploy.sh
#
# Override defaults with env vars:
#   GCP_REGION=europe-west1 SERVICE_NAME=mind-video ./deploy/deploy.sh
set -euo pipefail

# Repo root = parent of this script's dir, so the build source is correct no
# matter where you invoke this from (the Dockerfile lives at the repo root).
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

# Let Docker authenticate to Artifact Registry in this region (idempotent).
echo "==> Configuring Docker auth for ${REGION}-docker.pkg.dev..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# Build LOCALLY for linux/amd64 (Cloud Run's arch — required on Apple Silicon)
# and push straight to Artifact Registry. No Cloud Build, no staging bucket.
echo "==> Building image locally (linux/amd64)..."
docker build --platform linux/amd64 -t "${IMAGE}:latest" "${REPO_ROOT}"

echo "==> Pushing image to Artifact Registry..."
docker push "${IMAGE}:latest"

# Deploy. See cloudbuild.yaml for why these flags matter.
echo "==> Deploying to Cloud Run..."
gcloud run deploy "${SERVICE}" \
  --image="${IMAGE}:latest" \
  --region="${REGION}" \
  --platform=managed \
  --allow-unauthenticated \
  --service-account="${RUNTIME_SA_NAME:-mind-video-run}@${PROJECT_ID}.iam.gserviceaccount.com" \
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
